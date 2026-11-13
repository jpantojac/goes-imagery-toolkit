#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GOES-16/19 Advanced Baseline Imager (ABI) Imagery Toolkit
==========================================================

An academic and operational Earth Observation pipeline for automated data ingestion,
radiometric calibration, spatial reprojection, and cartographic visualization of
NOAA GOES-R series (GOES-16 and GOES-19) Level 1b Radiance (RadF) products.

Physical Principles & Calibrations Implemented:
-----------------------------------------------
1. Inversion of Planck Radiation Equation (Bands 07 - 16):
   Converts measured spectral radiances (mW / [m^2 * sr * (cm^-1)]) into effective
   Brightness Temperatures (T_B in Celsius) using sensor-specific calibration
   coefficients (fk1, fk2, bc1, bc2) defined in the NOAA ABI PUG Volume 3:
     T = fk2 / ln(fk1 / L_lambda + 1)
     T_B = [(T - bc1) / bc2] - 273.15

2. Top-of-Atmosphere (TOA) Solar Reflectance (Bands 01 - 06):
   Calibrates visible and near-infrared channels using solar spectral irradiance constants
   (Esun), normalized Sun-Earth distance, and gamma square-root enhancement:
     R = (pi * L_lambda * d^2) / Esun
     R_gamma = sqrt(clip(R, 0, 1))

3. Geostationary to Equirectangular (WGS84 EPSG:4326) Reprojection:
   High-performance spatial remapping via GDAL coordinate transformations and
   perspective projection height parameters.

4. Cartographic Composition & GIS Export:
   - High-resolution PNGs with scientific CPT colormaps and cartographic boundaries.
   - ESRI Worldfiles (.pgw) encoding affine 6-parameter pixel transformations.
   - Calibrated 16-bit GeoTIFF rasters (T_B * 100 scaled integers) with LZW compression.

Author: Julian Pantoja Clavijo <julianpc.dev@gmail.com>
License: MIT
Repository: https://github.com/jpantojac/goes-imagery-toolkit
"""
import os
import sys
import warnings

# Suprimir warnings específicos
warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# Asegurar que el directorio del script esté en el sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    from osgeo import gdal, osr
    gdal.PushErrorHandler('CPLQuietErrorHandler')
except (ImportError, ModuleNotFoundError):
    gdal = None
    osr = None

try:
    from libs.remap import remap
except (ImportError, ModuleNotFoundError):
    remap = None

try:
    from mpl_toolkits.basemap import Basemap
except (ImportError, ModuleNotFoundError):
    Basemap = None

import argparse  
import logging   
import ast
import shutil
from datetime import datetime, timedelta
try:
    import GOES
except (ImportError, ModuleNotFoundError):
    GOES = None
try:
    from netCDF4 import Dataset
except (ImportError, ModuleNotFoundError):
    Dataset = None
try:
    import numpy as np
except (ImportError, ModuleNotFoundError):
    np = None

try:
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.patches import Rectangle
except (ImportError, ModuleNotFoundError):
    matplotlib = None
    plt = None
    LinearSegmentedColormap = None
    Rectangle = None

try:
    from libs.cpt_convert import loadCPT
except (ImportError, ModuleNotFoundError):
    loadCPT = None

try:
    import colors.colors as colors
except (ImportError, ModuleNotFoundError):
    colors = None

import time

try:
    import requests
    from bs4 import BeautifulSoup
except (ImportError, ModuleNotFoundError):
    requests = None
    BeautifulSoup = None

import urllib3
from typing import Optional, List, Union

try:
    from PIL import Image
except (ImportError, ModuleNotFoundError):
    Image = None

try:
    from metpy.plots import colortables
except (ImportError, ModuleNotFoundError):
    colortables = None

try:
    import yaml
except (ImportError, ModuleNotFoundError):
    yaml = None



# Configuración inicial de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


# Load project configuration from YAML
def load_config(config_path: Optional[str] = None) -> dict:
    """
    Loads project configuration from a YAML file.

    Args:
        config_path (Optional[str], optional): Path to the configuration YAML file.
            If None, defaults to 'config.yaml' located in the script directory.

    Returns:
        dict: Parsed configuration dictionary containing runtime settings,
            paths, spectral channel definitions, and GIS parameters.
    """
    if yaml is None:
        return {}
    if config_path is None:
        cand_path = os.path.join(SCRIPT_DIR, "config.yaml")
        config_path = cand_path if os.path.exists(cand_path) else "config.yaml"
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file) or {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        logging.warning(f"Error reading configuration file: {e}")
        return {}

config = load_config()

def _cfg_get(section: str, *keys: str, default=None):
    """
    Safely retrieves a configuration key from a section, supporting both
    standard English keys and legacy Spanish aliases for backward compatibility.

    Args:
        section (str): Name of the configuration section in config.yaml.
        *keys (str): Candidate keys to query sequentially.
        default (Any, optional): Fallback value if no candidate key matches.

    Returns:
        Any: Value of the first matched key, or default if none exist.
    """
    sec = config.get(section, {}) if isinstance(config, dict) else {}
    for k in keys:
        if k in sec:
            return sec[k]
    return default

# Configuraciones generales / General settings
basePath = config.get('paths', {}).get('base', '')
if not basePath or basePath.strip() in [".", ""]:
    basePath = SCRIPT_DIR

institucion         = _cfg_get('general', 'institution', 'institucion', default='Open Satellite Project')
generateTiff        = _cfg_get('general', 'generate_tiff', 'generateTiff', default=True)
archivo_registro    = _cfg_get('general', 'registry_file', 'archivo_registro', default='ultima_descarga.txt')

sat_section         = config.get('satellite', config.get('satelite', {}))
channels            = sat_section.get('channels', ["01", "09", "13"])
channelsIdeam       = sat_section.get('channels_ideam', ["C01", "C09", "C13"])
base_url            = sat_section.get('base_url', "https://bart.ideam.gov.co/ospa/sensores/pasivos/satelite/GOES19/RAW/")
satellite           = sat_section.get('satellite', "G19")

# Globales
dsatellite = satellite.replace('G','goes')
ncFile = None
fechas_julianas = []


def R2BT(radiance: np.ndarray, channel: str) -> np.ndarray:
    """
    Inverts the Planck radiation function to convert spectral radiance into
    calibrated Brightness Temperature (T_B in Celsius) for thermal infrared bands.

    Mathematical Formulation:
        1. Effective Planckian temperature in Kelvin:
           T = fk2 / (ln(fk1 / radiance + 1))
        2. Linear spectral response correction and Celsius conversion:
           T_B = [(T - bc1) / bc2] - 273.15

    Coefficients (fk1, fk2, bc1, bc2) are derived from the NOAA ABI Level 1b
    Product Definition and Users' Guide (PUG) Volume 3.

    Args:
        radiance (np.ndarray): Spectral radiance array measured by the ABI sensor
            in mW / (m^2 * sr * cm^-1).
        channel (str): ABI spectral channel identifier (e.g. 'C07', 'C13').

    Returns:
        np.ndarray: Calibrated Brightness Temperature array in degrees Celsius (°C).

    Raises:
        KeyError: If the specified channel is not a supported thermal infrared band.
    """
    BT_COEFFS = {
    'C07': {'fk1': 607.76,   'fk2': 121.27,  'bc1': 0.50251, 'bc2': 1.00121},
    'C08': {'fk1': 1349.07,  'fk2': 215.47,  'bc1': 0.44789, 'bc2': 0.99947},
    'C09': {'fk1': 3334.57,  'fk2': 479.29,  'bc1': 0.37735, 'bc2': 0.99905},
    'C10': {'fk1': 5191.21,  'fk2': 774.89,  'bc1': 0.28547, 'bc2': 0.99959},
    'C11': {'fk1': 11896.29, 'fk2': 1788.17, 'bc1': 0.12072, 'bc2': 0.99978},
    'C12': {'fk1': 8052.82,  'fk2': 1228.61, 'bc1': 0.13377, 'bc2': 0.99979},
    'C13': {'fk1': 10736.40, 'fk2': 1389.86, 'bc1': 0.13445, 'bc2': 0.99955},
    'C14': {'fk1': 7776.19,  'fk2': 1111.95, 'bc1': 0.13637, 'bc2': 0.99975},
    'C15': {'fk1': 6806.27,  'fk2': 992.03,  'bc1': 0.14449, 'bc2': 0.99982},
    'C16': {'fk1': 5364.31,  'fk2': 829.59,  'bc1': 0.11557, 'bc2': 0.99985},
    }

    coeffs = BT_COEFFS[channel]
    fk1 = coeffs['fk1']
    fk2 = coeffs['fk2']
    bc1 = coeffs['bc1']
    bc2 = coeffs['bc2']
    
    T = (fk2 / (np.log((fk1 / radiance) + 1)) - bc1) / bc2
    TC = T - 273.15
    return TC

def R2BT_WV_visual(rad: np.ndarray, channel: str) -> np.ndarray:
    """
    Applies dynamic range radiometric normalization for tropospheric water vapor bands
    (ABI Bands 08, 09, 10).

    Normalizes radiances across empirical meteorological bounds and scales them
    into an effective temperature range [-80°C, -20°C] for optimal visual contrast
    of synoptic moisture structures, jet streams, and atmospheric vorticity.

    Args:
        rad (np.ndarray): Spectral radiance array for water vapor channels.
        channel (str): ABI channel identifier ('C08', 'C09', or 'C10').

    Returns:
        np.ndarray: Normalized brightness temperature proxy for visual cartography.

    Raises:
        ValueError: If the channel is not an ABI water vapor channel.
    """
    if channel == 'C08':
        rmin, rmax = 0.5, 25.0
        tmin, tmax = -80.0, -30.0
    elif channel == 'C09':
        rmin, rmax = 0.5, 19.0
        tmin, tmax = -80.0, -20.0
    elif channel == 'C10':
        rmin, rmax = 1.0, 30.0
        tmin, tmax = -80.0, -10.0
    else:
        raise ValueError("Canal WV no soportado")

    rad_clipped = np.clip(rad, rmin, rmax)
    tb = tmin + (rad_clipped - rmin) * (tmax - tmin) / (rmax - rmin)
    return tb

def R2RT(radiance: np.ndarray, channel: str) -> np.ndarray:
    """
    Converts solar spectral radiance into Top-of-Atmosphere (TOA) bidirectional
    reflectance factor (R) with non-linear display gamma enhancement.

    Mathematical Formulation:
        1. Reflectance factor:
           R = (pi * radiance * d^2) / Esun
        2. Bounds clipping:
           R_clipped = clip(R, 0.0, 1.0)
        3. Gamma square-root transformation (gamma = 0.5):
           R_gamma = sqrt(R_clipped)

    Args:
        radiance (np.ndarray): Solar radiance measured by the ABI sensor in
            mW / (m^2 * sr * cm^-1).
        channel (str): Reflective channel identifier ('C01' through 'C06').

    Returns:
        np.ndarray: Gamma-corrected reflectance array bounded in [0.0, 1.0].

    Raises:
        ValueError: If Esun constant is not defined for the requested channel.
    """
    Esun = {
        'C01': 2041.962,   # Banda 1, 0.47 µm
        'C02': 1622.088,   # Banda 2, 0.64 µm
        'C03': 953.1772,   # Banda 3, 0.86 µm
        'C04': 355.0144,   # Banda 4, 1.37 µm
        'C05': 239.109,    # Banda 5, 1.6 µm
        'C06': 76.0102     # Banda 6, 2.2 µm
    }

    d2 = 0.3  # Distancia Sol-Tierra normalizada (ajuste simplificado)
    if channel in Esun:
        ref = (radiance * np.pi * d2) / Esun[channel]
    else:
        raise ValueError(f"Constante Esun no definida para el canal {channel}")
    
    ref = np.maximum(ref, 0.0)
    ref = np.minimum(ref, 1.0)
    ref_gamma = np.sqrt(ref)
    return ref_gamma 

def create_folder(ruta: str, clean: bool = False) -> bool:
    """
    Ensures a directory exists on the filesystem, optionally purging existing contents.

    Args:
        ruta (str): Target directory path.
        clean (bool, optional): If True and directory exists, removes all files
            and subdirectories inside it. Defaults to False.

    Returns:
        bool: True if directory is prepared successfully, False on error.
    """
    try:
        if os.path.exists(ruta):
            if clean:
                for filename in os.listdir(ruta):
                    file_path = os.path.join(ruta, filename)
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                logging.debug("Contenido de la carpeta eliminado: %s", ruta)
        else:
            os.makedirs(ruta)
            logging.debug("Carpeta creada: %s", ruta)
        return True
    except Exception as e:
        logging.error("Error al gestionar carpeta %s: %s", ruta, e)
        return False

def prepare_folders(dates: List[str]) -> None:
    """
    Prepares input and output directory structures indexed by Julian day (day of year).

    Args:
        dates (List[str]): List of date strings in 'YYYYMMDD' format.
    """
    global fechas_julianas
    #global basePath 
    #basePath = os.getcwd()
    # Itera sobre las fechas y conviértelas a formato juliano
    for fecha in dates:
        fecha_dt = datetime.strptime(fecha, "%Y%m%d")
        fecha_juliana = fecha_dt.strftime("%j")  # %j es el formato para el día del año
        fechas_julianas.append(fecha_juliana)

    for fecha in fechas_julianas:
        create_folder(os.path.join(basePath,config['paths']['input'],fecha),False)    
        create_folder(os.path.join(basePath,config['paths']['output'],fecha),False)    

def download(dates: List[str], hours: List[str], minutes: List[str]) -> List[str]:
    """
    Retrieves NOAA GOES Level 1b Radiance (ABI-L1b-RadF) NetCDF files from AWS S3.

    Queries hourly cloud storage prefixes with minute-level precision, enforcing
    temporal bounds to prevent S3 prefix overshoot. Automatically falls back
    to pre-existing local files if already downloaded in previous sessions.

    Args:
        dates (List[str]): List of target observation dates in 'YYYYMMDD' format.
        hours (List[str]): List of UTC target hours in 'HH' format (00-23).
        minutes (List[str]): List of target minutes in 'MM' format (00-59).

    Returns:
        List[str]: List of filesystem paths to the downloaded or resolved NetCDF files.
    """
    fulllist = []
    for date in dates:
        for hour in hours:
            for minute in minutes:
                fecha_hora = datetime.strptime(date+"-"+hour+minute+'00', '%Y%m%d-%H%M%S')
                # Stay strictly within the requested slot with 00 seconds so GOES.download
                # does not overshoot by 1 hour due to second-precision comparisons.
                nueva_fecha_hora = min(
                    fecha_hora + timedelta(minutes=5),
                    fecha_hora.replace(minute=55, second=0)
                )
                dateend = nueva_fecha_hora.strftime('%Y%m%d-%H%M00')
                fecha_dt = datetime.strptime(date, "%Y%m%d")
                fecha_juliana = fecha_dt.strftime("%j")
                output = (os.path.join(basePath, config['paths']['input'], fecha_juliana).rstrip(os.sep)+ os.sep)
                flist = []
                try:
                    flist = GOES.download(dsatellite, 'ABI-L1b-RadF',
                                DateTimeIni = date+"-"+hour+minute+'00', 
                                DateTimeFin = dateend, 
                                channel = channels, 
                                path_out=output)
                except FileNotFoundError as fnf_err:
                    logging.warning(f"S3 remote directory not found for {date} {hour}:{minute} UTC: {fnf_err}")
                except Exception as dl_err:
                    logging.warning(f"Error querying GOES data for {date} {hour}:{minute} UTC: {dl_err}")

                if flist:
                    fulllist += flist
                elif os.path.exists(output):
                    # Fallback: check if files were already downloaded in this slot
                    prefix_match = f"s{fecha_dt.strftime('%Y%j')}{hour}{minute}"
                    existing = [
                        os.path.join(output, f) for f in os.listdir(output)
                        if f.endswith('.nc') and prefix_match in f
                    ]
                    if existing:
                        logging.info(f"Using {len(existing)} pre-downloaded files from {output} for {date} {hour}:{minute}")
                        fulllist += existing
    return fulllist                

def auto_date(source: str, label: bool = False, watermark: Optional[str] = None) -> None:
    """
    Executes near-real-time automated observation retrieval and product generation.

    Args:
        source (str): Satellite data source identifier ('aws' or 'ideam').
        label (bool, optional): If True, renders title bar, colorbar, and metadata. Defaults to False.
        watermark (Optional[str], optional): Custom institution or attribution watermark. Defaults to None.
    """
    logging.info("Automated generation mode started")
    if source == 'aws':
        source_AWS(label, watermark=watermark)
    elif source == "ideam":
        source_IDEAM(label, watermark=watermark)
    else:
        logging.error(f"Unknown data source: {source}. Supported: aws | ideam")

def download_file(url: str, nombre_archivo: str) -> None:
    """
    Downloads a remote binary file via HTTP/HTTPS into the corresponding Julian day folder.

    Args:
        url (str): Remote URL endpoint.
        nombre_archivo (str): Target filename to persist locally.
    """
    logging.info(f"Downloading {nombre_archivo} from {url}...")
    response = requests.get(url, verify=False)
    Start = (nombre_archivo[nombre_archivo.find("_s")+2:nombre_archivo.find("_e")])

    dayjulianstring = Start[4:7] 
    create_folder(os.path.join(basePath, config['paths']['input'], dayjulianstring), False)   
    directorio_descargas = os.path.join(basePath, config['paths']['input'], dayjulianstring)
    with open(os.path.join(directorio_descargas, nombre_archivo), 'wb') as f:
        f.write(response.content)
    logging.info(f"Download complete: {nombre_archivo}")

# Alias for backward compatibility
donwload_file = download_file

def write_latest_downloaded(ultima_descarga: dict) -> None:
    """
    Persists the state registry of the most recent downloaded files per channel.

    Args:
        ultima_descarga (dict): Key-value mapping of channel name to latest filename.
    """
    with open(archivo_registro, 'w') as f:
        for canal, archivo in ultima_descarga.items():
            f.write(f"{canal}={archivo}\n")

def read_latest_downloaded() -> dict:
    """
    Reads the state registry tracking the latest downloaded files per channel.

    Returns:
        dict: Dictionary mapping channel names to their latest downloaded filename.
    """
    if os.path.exists(archivo_registro):
        with open(archivo_registro, 'r') as f:
            resultado = {}
            for line in f:
                line = line.strip()
                if '=' in line:
                    clave, valor = line.split('=', 1)
                    resultado[clave] = valor
            return resultado
    return {}

def source_IDEAM(label: bool = False, watermark: Optional[str] = None) -> None:
    """
    Scrapes and retrieves the most recent Level 1b imagery from the IDEAM regional HTTP archive.

    Args:
        label (bool, optional): If True, renders metadata, colorbar, and title banner. Defaults to False.
        watermark (Optional[str], optional): Custom watermark or attribution string. Defaults to None.
    """
    # Obtener el contenido de la página
    response = requests.get(base_url, verify=False)
    soup = BeautifulSoup(response.text, 'html.parser')
    # Leer la última descarga realizada
    ultima_descarga = read_latest_downloaded()
    # Procesar los archivos en la página
    archivos_encontrados = {canal: [] for canal in channelsIdeam}
        
    # Filtrar los archivos correspondientes a los canales C02, C09, C13 y que terminen en .nc
    for link in soup.find_all('a'):
        nombre_archivo = link.get('href')
        if (
            nombre_archivo.endswith('.nc') and  # Solo archivos .nc
            any(canal in nombre_archivo for canal in channelsIdeam)  # Que contengan el canal
        ):
            canal = next(canal for canal in channelsIdeam if canal in nombre_archivo)
            archivos_encontrados[canal].append(nombre_archivo)

    archivos_descargados = []        
    for canal, archivos in archivos_encontrados.items():
        if archivos:
            archivos.sort(reverse=True)  # Ordenar de más reciente a más antiguo
            archivo_mas_reciente = archivos[0]

            Start = (archivo_mas_reciente[archivo_mas_reciente.find("_s")+2:archivo_mas_reciente.find("_e")])
            dayjulianstring = Start[4:7] 
            # Construir el path completo para el archivo descargado
            archivo_path_completo = os.path.join(basePath,config['paths']['input'],dayjulianstring,archivo_mas_reciente)

            if archivo_mas_reciente != ultima_descarga.get(canal):
                archivo_url = base_url + archivo_mas_reciente
                donwload_file(archivo_url, archivo_mas_reciente)  # Descarga el archivo

                ultima_descarga[canal] = archivo_mas_reciente  # Actualizar la última descarga
                archivos_descargados.append(archivo_path_completo)  # Añadir el path completo al array
                logging.info(f"Archivo descargado: {archivo_mas_reciente}")
            else:
                logging.info(f"La imagen más reciente para {canal} ({archivo_mas_reciente}) ya fue descargada.")

    for aFile in archivos_descargados:
        processImage(aFile, label=label, watermark=watermark)
    
    write_latest_downloaded(ultima_descarga)

# Función para leer el archivo de registro de la última descarga
def read_latest_downloaded():
    """
    Lee el archivo de registro de las últimas descargas realizadas.

    Returns:
        dict: Diccionario con el canal como clave y el nombre del último archivo descargado como valor.
    """
    if os.path.exists(archivo_registro):
        with open(archivo_registro, 'r') as f:
            resultado = {}
            for line in f:
                line = line.strip()
                if '=' in line:  # Verificar que la línea tenga el formato esperado
                    clave, valor = line.split('=', 1)  # Solo hacer split en el primer '='
                    resultado[clave] = valor
            return resultado
    return {}

def source_AWS(label: bool = False, watermark: Optional[str] = None) -> None:
    """
    Retrieves and processes the most recent GOES observation slot from NOAA's public AWS S3 bucket.

    Computes the timestamp of the latest available 10-minute scan, creates required directories,
    downloads the active spectral channels, and triggers image/raster production.

    Args:
        label (bool, optional): If True, renders metadata, colorbar, and title banner. Defaults to False.
        watermark (Optional[str], optional): Custom watermark or attribution string. Defaults to None.
    """
    utc = time.gmtime()
    tenMinutesAgo = time.time() - ( 60 * 10 )
    utcTenMinutesAgo = time.gmtime(tenMinutesAgo)
    current_minutes = utcTenMinutesAgo.tm_min
    rounded_minutes = (current_minutes // 10) * 10

    utcTenMinutesAgoRounded = time.struct_time((utcTenMinutesAgo.tm_year,
                                            utcTenMinutesAgo.tm_mon,
                                            utcTenMinutesAgo.tm_mday,
                                            utcTenMinutesAgo.tm_hour,
                                            rounded_minutes,
                                            0,  # Segundos a 0
                                            utcTenMinutesAgo.tm_wday,
                                            utcTenMinutesAgo.tm_yday,
                                            utcTenMinutesAgo.tm_isdst))

    year = time.strftime('%Y',utcTenMinutesAgoRounded)
    month = time.strftime('%m',utcTenMinutesAgoRounded) 
    day = time.strftime('%d',utcTenMinutesAgoRounded)
    hour = time.strftime('%H',utcTenMinutesAgoRounded)
    minute = time.strftime('%M',utcTenMinutesAgoRounded)
    julian = time.strftime('%j',utcTenMinutesAgoRounded) 
    logging.info(time.strftime('%m/%d/%Y, %H:%M:%S',utcTenMinutesAgoRounded))

    dates=[]
    hours=[]
    minutes=[]
    dates.append(year+month+day)
    hours.append(hour)
    minutes.append(minute)
    prepare_folders(dates)
    flist = download(dates,hours,minutes)

    if not flist:
        logging.warning("No files were downloaded. The requested scan may not yet be published on NOAA S3.")
        return

    for aFile in flist:
        processImage(aFile, label=label, watermark=watermark)

def manual_date(
    dates: List[str],
    hours: List[str],
    minutes: List[str],
    lat: Optional[Union[float, List[float]]] = None,
    lon: Optional[Union[float, List[float]]] = None,
    label: bool = False,
    bullseye: bool = True,
    watermark: Optional[str] = None
) -> None:
    """
    Orchestrates manual, targeted satellite imagery generation for specific timestamps and coordinates.

    Args:
        dates (List[str]): List of dates in 'YYYYMMDD' format.
        hours (List[str]): List of UTC hours in 'HH' format (00-23).
        minutes (List[str]): List of minutes in 'MM' format (00-59).
        lat (Optional[Union[float, List[float]]]): Target latitude(s) for visual emphasis.
        lon (Optional[Union[float, List[float]]]): Target longitude(s) for visual emphasis.
        label (bool, optional): If True, renders title bar, colorbar, and metadata. Defaults to False.
        bullseye (bool, optional): If True, renders concentric nautical mile distance rings.
            If False, plots numbered waypoints (P1, P2, ...). Defaults to True.
        watermark (Optional[str], optional): Custom watermark or attribution string. Defaults to None.
    """
    global fechas_julianas
    prepare_folders(dates)
    flist = download(dates,hours,minutes)

    if not flist:
        logging.warning("No files were downloaded for the specified dates and times.")
        return
          
    for aFile in flist:
        processImage(aFile, lat, lon, label=label, bullseye=bullseye, watermark=watermark)

def get_band(nombre_archivo: str, isString: bool) -> Union[int, str, None]:
    """
    Extracts the ABI spectral channel identifier from a standard GOES NetCDF filename.

    Supports NOAA GOES-R naming conventions across all satellites (G16, G17, G18, G19)
    and scan modes (M3, M4, M6).

    Args:
        nombre_archivo (str): GOES NetCDF filename.
        isString (bool): If True, returns channel number as integer.
            If False, returns 2-character zero-padded string (e.g. '01', '13').

    Returns:
        Union[int, str, None]: Extracted channel identifier, or None if extraction fails.
    """
    inicio = nombre_archivo.find("M4C") if "M4C" in nombre_archivo else nombre_archivo.find("M6C")
    fin = nombre_archivo.find("_G", inicio)
    if fin == -1:
        fin = nombre_archivo.find("_"+satellite, inicio)
    if inicio != -1 and fin != -1:
        if isString == True:
            salida = int(nombre_archivo[inicio+3:fin])
        else:
            salida = nombre_archivo[inicio+3:fin]    
        return salida
    return None

def get_bounding_box(lat: float, lon: float, radius_miles: float = 100) -> List[float]:
    """
    Calculates an equirectangular bounding box centered on a geographic coordinate.

    Approximates great-circle distance using nautical-mile to degree conversion
    (1 deg ≈ 60 NM / 69 statute miles).

    Args:
        lat (float): Center latitude in decimal degrees.
        lon (float): Center longitude in decimal degrees.
        radius_miles (float, optional): Half-width radius in nautical or statute miles. Defaults to 100.

    Returns:
        List[float]: Bounding box coordinates formatted as [west, south, east, north].
    """
    miles_to_deg = 1 / 69.0  # 1 degree ≈ 69 miles
    radius_deg = radius_miles * miles_to_deg

    south = lat - radius_deg
    north = lat + radius_deg
    west = lon - radius_deg
    east = lon + radius_deg

    return [west, south, east, north]

def processImage(aFile: str, lat: Optional[Union[float, List[float]]] = None, lon: Optional[Union[float, List[float]]] = None, label: bool = False, bullseye: bool = True, watermark: Optional[str] = None) -> None:
    """
    Executes the scientific cartographic and raster processing pipeline for a GOES ABI NetCDF file.

    Workflow:
        1. Metadata Extraction: Parses observation timestamp, spatial resolution, and band properties.
        2. Geostationary Reprojection: Remaps raw geostationary perspective grid to Equirectangular (WGS84).
        3. Physical Calibration: Inverts Planck function for thermal IR or computes gamma-enhanced solar reflectance.
        4. Dynamic Memory Bounding: Constrains maximum dimensions via Lanczos spatial resampling.
        5. Vector Overlays: Renders national borders, department boundaries, waypoints, and range rings.
        6. Cartographic Publishing:
           - Visual PNG image with calibrated CPT colormaps and metadata banner.
           - ESRI Worldfile (.pgw) specifying affine transformation parameters.
           - 16-bit GeoTIFF raster (T_B * 100 scaled integer) with LZW compression.

    Args:
        aFile (str): NetCDF filename or absolute path to process.
        lat (Optional[Union[float, List[float]]], optional): Target latitude(s). Defaults to None.
        lon (Optional[Union[float, List[float]]], optional): Target longitude(s). Defaults to None.
        label (bool, optional): If True, adds colorbar, scale, and metadata footer. Defaults to False.
        bullseye (bool, optional): If True, draws concentric nautical-mile range rings. Defaults to True.
        watermark (Optional[str], optional): Custom institution or attribution banner. Defaults to None.

    Returns:
        None
    """
    matplotlib.rcParams['figure.dpi'] = 100
    #print(f"Matplotlib default DPI after setting: {matplotlib.rcParams['figure.dpi']}")

    Start = (aFile[aFile.find("_s")+2:aFile.find("_e")])

    Band = get_band(aFile, True)
    BandString = get_band(aFile, False)

    Wavelenghts = ['[]', '[0.47 μm]', '[0.64 μm]', '[0.865 μm]', '[1.378 μm]', '[1.61 μm]', '[2.25 μm]', '[3.90 μm]', '[6.19 μm]', '[6.95 μm]', '[7.34 μm]', '[8.50 μm]', '[9.61 μm]', '[10.35 μm]', '[11.20 μm]', '[12.30 μm]', '[13.30 μm]']

    year = int(Start[0:4])
    dayjulian = int(Start[4:7])
    dayjulianstring = Start[4:7]

    dayconventional = datetime(int(year), 1, 1) + timedelta(days=int(dayjulian) - 1)
    date = dayconventional.strftime('%d-%b-%Y')

    time = Start[7:9] + ":" + Start[9:11] + " UTC"

    if Band <= 6:
        Unit = "Reflectance"
    else:
        Unit = "Brightness Temperature [°C]"

    Title = dsatellite.upper().replace("GOES", "GOES-") + " Band " + str(Band) + " " + Wavelenghts[int(Band)] + " " + Unit + " " + date + "  " + time
    Institution = watermark if watermark is not None else institucion

    if os.path.exists(aFile):
        aImage = aFile
    else:
        aFileName = os.path.basename(aFile)
        aImage = os.path.join(basePath, config['paths']['input'], dayjulianstring, aFileName)
    ncImage = Dataset(aImage, 'r')
    time_coverage_start = ncImage.time_coverage_start

    geo_extent = ncImage.variables['geospatial_lat_lon_extent']
    min_lon = float(geo_extent.geospatial_westbound_longitude)
    max_lon = float(geo_extent.geospatial_eastbound_longitude)
    min_lat = float(geo_extent.geospatial_southbound_latitude)
    max_lat = float(geo_extent.geospatial_northbound_latitude)

    H = ncImage.variables['goes_imager_projection'].perspective_point_height
    x1 = ncImage.variables['x_image_bounds'][0] * H
    x2 = ncImage.variables['x_image_bounds'][1] * H
    y1 = ncImage.variables['y_image_bounds'][1] * H
    y2 = ncImage.variables['y_image_bounds'][0] * H

    if lat is not None and lon is not None:
        # Asegurar que sean listas
        lats = [lat] if isinstance(lat, (float, int)) else lat
        lons = [lon] if isinstance(lon, (float, int)) else lon
        
        if len(lats) > 1:
            # Calcular extent que abarque todos los puntos
            min_lat_p = min(lats)
            max_lat_p = max(lats)
            min_lon_p = min(lons)
            max_lon_p = max(lons)
            
            # Usar el radio configurado como margen desde los extremos
            miles_to_deg = 1 / 69.0
            radius_deg = config['plotting']['radius_nautical_miles'] * miles_to_deg
            
            extent = [min_lon_p - radius_deg, min_lat_p - radius_deg, max_lon_p + radius_deg, max_lat_p + radius_deg]
        else:
            extent = get_bounding_box(lats[0], lons[0], radius_miles=config['plotting']['radius_nautical_miles'])
            
        resolution = config['plotting']['resolution_zoomed']
        DPI = 100
    else:
        #extent = [-100.0, -14.0, -50.0, 30.0]
        extent = config['plotting']['extent_default']
        extent = [float(x) for x in extent] # por si las dudas
        resolution = config['plotting']['resolution_full']
        DPI = 100

    lon_range = extent[2] - extent[0]

    grid = remap(aImage, extent, resolution, x1, y1, x2, y2)
    data = grid.ReadAsArray()
    #print(f"Initial data shape: {data.shape}")

    max_dim = 1024
    if data.shape[1] > max_dim or data.shape[0] > max_dim:
        scale = min(max_dim / data.shape[1], max_dim / data.shape[0])
        new_width = int(data.shape[1] * scale)
        new_height = int(data.shape[0] * scale)
        #print(f"Resizing data from {data.shape} to ({new_height}, {new_width})")
        resample_filter = getattr(getattr(Image, 'Resampling', None), 'LANCZOS', getattr(Image, 'LANCZOS', Image.BILINEAR))
        data = np.array(Image.fromarray(data.astype(np.float32)).resize((new_width, new_height), resample_filter))
    #print(f"Adjusted data shape: {data.shape}")

    channel_str = f"C{Band:02d}"
    if Band <= 6:
        data = R2RT(data, channel_str)
    elif Band > 7 and Band < 11:
        data = R2BT_WV_visual(data, channel_str)
    else:
        data = R2BT(data, channel_str)

    #print(f"Sample data values after processing (first 5x5): {data[:5, :5]}")
    data_stats = [data.min(), data.max(), data.mean(), data.std()]
    #print(f"Data stats after processing (min, max, mean, stddev): {data_stats}")

    ncImage.close()
    ncImage = None

    multiplier = 1 if lat is not None and lon is not None else 1
    pixel_width = (data.shape[1] / float(DPI) * multiplier) * DPI
    pixel_height = (data.shape[0] / float(DPI) * multiplier) * DPI
    #print(f"Pre-scaling pixel dimensions: ({pixel_width}x{pixel_height})")

    max_pixels = 65536
    scale_factor = 1.0
    if pixel_width > max_pixels or pixel_height > max_pixels:
        scale_factor = min(max_pixels / pixel_width, max_pixels / pixel_height)
        #print(f"Image dimensions ({pixel_width}x{pixel_height}) exceed limit. Scaling down by factor {scale_factor:.2f}")

    target_width = min(32768 / DPI, data.shape[1] / float(DPI) * multiplier * scale_factor)
    target_height = min(32768 / DPI, data.shape[0] / float(DPI) * multiplier * scale_factor)
    final_figsize = (target_width, target_height)
    final_pixel_width = final_figsize[0] * DPI
    final_pixel_height = final_figsize[1] * DPI
    #print(f"Final figsize: {final_figsize}, Final pixel dimensions: ({final_pixel_width}x{final_pixel_height})")

    # Enforce exact dimensions matching data.shape
    fig = plt.figure(figsize=(data.shape[1]/DPI, data.shape[0]/DPI), frameon=False, dpi=DPI)
    fig.set_size_inches(data.shape[1]/DPI, data.shape[0]/DPI, forward=True)
    fig.set_dpi(DPI)

    ax = plt.Axes(fig, [0., 0., 1., 1.])
    ax.set_axis_off()
    fig.add_axes(ax)

    bmap = Basemap(llcrnrlon=extent[0], llcrnrlat=extent[1], urcrnrlon=extent[2], urcrnrlat=extent[3], epsg=4326, resolution='i', ax=ax)

    x_min, y_min = bmap(extent[0], extent[1])
    x_max, y_max = bmap(extent[2], extent[3])
    #print(f"Projected extent: {x_min}, {x_max}, {y_min}, {y_max}")

    norm_extent = [0, data.shape[1], 0, data.shape[0]]

    data_for_png = data  # Use the original data array

    im = ax.imshow(data_for_png, origin='upper', extent=norm_extent, interpolation='bilinear', aspect='equal', zorder=1)
    colors_dir = os.path.join(basePath, config['paths']['colors'])
    if Band <= 6:
        cpt = loadCPT(os.path.join(colors_dir, "grey255.cpt"))
        cpt_convert = LinearSegmentedColormap('cpt', cpt)
        im.set_cmap(cpt_convert)
        im.set_clim(0, 1)
    elif Band == 7:
        cpt = loadCPT(os.path.join(colors_dir, "thermal.cpt"))
        cpt_convert = LinearSegmentedColormap('cpt', cpt)
        im.set_cmap(cpt_convert)
        im.set_clim(-112.15, 56.85)
    elif Band > 7 and Band < 11:
        cpt = loadCPT(os.path.join(colors_dir, "WV_red_black.cpt"))
        cpt_convert = LinearSegmentedColormap('cpt', cpt)
        cpt_convert_reversed = cpt_convert.reversed()
        im.set_cmap(cpt_convert_reversed)
        im.set_clim(-85, -30)
    elif Band > 10:
        im.set_cmap(colors.rainbow)
        im.set_clim(-90, 50)

    ax.set_xlim(0, data.shape[1])
    ax.set_ylim(0, data.shape[0])

    def lonlat_to_norm(lon, lat, extent, data_shape):
        lon_range = extent[2] - extent[0]
        lat_range = extent[3] - extent[1]
        x_norm = (lon - extent[0]) / lon_range * data_shape[1]
        y_norm = (lat - extent[1]) / lat_range * data_shape[0]
        return x_norm, y_norm

    dpto_shape = _cfg_get('shapes', 'departments', 'departamentos', default='MGN_DPTO_POLITICO')
    dpto_layer = _cfg_get('shapes', 'departments_layer', 'departamentos_layer', default='MGN_DPTO_POLITICO')
    shapefile_path = os.path.join(basePath, config['paths']['shapes'], dpto_shape)
    bmap.readshapefile(shapefile_path, dpto_layer, drawbounds=False)

    for shape in getattr(bmap, dpto_layer, []):
        x = [point[0] for point in shape]
        y = [point[1] for point in shape]
        x_norm = [(lon - extent[0]) / (extent[2] - extent[0]) * data.shape[1] for lon in x]
        y_norm = [(lat - extent[1]) / (extent[3] - extent[1]) * data.shape[0] for lat in y]
        ax.plot(x_norm, y_norm, color='white', linewidth=0.6, zorder=2)

    country_shape = _cfg_get('shapes', 'countries', 'paises', default='ne_10m_admin_0_countries/ne_10m_admin_0_countries')
    country_layer = _cfg_get('shapes', 'countries_layer', 'paises_layer', default='countries')
    country_shapefile_path = os.path.join(basePath, config['paths']['shapes'], country_shape)
    bmap.readshapefile(country_shapefile_path, country_layer, drawbounds=False)

    for shape in getattr(bmap, country_layer, []):
        x = [point[0] for point in shape]
        y = [point[1] for point in shape]
        x_norm = [(lon - extent[0]) / (extent[2] - extent[0]) * data.shape[1] for lon in x]
        y_norm = [(lat - extent[1]) / (extent[3] - extent[1]) * data.shape[0] for lat in y]
        ax.plot(x_norm, y_norm, color='white', linewidth=0.6, zorder=2)

    if lat is not None and lon is not None:
        # Asegurar que sean listas para iterar
        lats_plot = [lat] if isinstance(lat, (float, int)) else lat
        lons_plot = [lon] if isinstance(lon, (float, int)) else lon
        
        # Dibujar marcadores para todos los puntos
        for idx, (p_lat, p_lon) in enumerate(zip(lats_plot, lons_plot)):
            x_norm, y_norm = lonlat_to_norm(p_lon, p_lat, extent, data.shape)
            msize = 2 if bullseye else 4
            ax.plot(x_norm, y_norm, 'ro', markersize=msize, zorder=3)
            if not bullseye:
                ax.text(x_norm, y_norm + data.shape[0]*0.015, f'P{idx+1}', color='white', fontsize=9, ha='center', va='bottom', zorder=4, bbox=dict(facecolor='black', alpha=0.5, pad=1))

        # Lógica de anillos
        show_rings = config['plotting'].get('show_rings', True)
        if show_rings and bullseye:
            ring_mode = config['plotting'].get('ring_mode', 'individual')
            
            # Decidir el centro de los anillos
            points_for_rings = []
            if ring_mode == 'centroid' and len(lats_plot) > 1:
                center_lat = sum(lats_plot) / len(lats_plot)
                center_lon = sum(lons_plot) / len(lons_plot)
                points_for_rings = [(center_lat, center_lon)]
            else:
                points_for_rings = list(zip(lats_plot, lons_plot))

            for r_lat, r_lon in points_for_rings:
                x_norm_r, y_norm_r = lonlat_to_norm(r_lon, r_lat, extent, data.shape)
                
                nm_to_deg = 1 / 60.045
                radius_10_nm = 10 * nm_to_deg
                radius_20_nm = 20 * nm_to_deg
                radius_30_nm = 30 * nm_to_deg

                radius_10_norm = radius_10_nm / lon_range * data.shape[1]
                radius_20_norm = radius_20_nm / lon_range * data.shape[1]
                radius_30_norm = radius_30_nm / lon_range * data.shape[1]

                circle_10 = plt.Circle((x_norm_r, y_norm_r), radius_10_norm, facecolor='none', edgecolor='red', linewidth=1, zorder=3)
                circle_20 = plt.Circle((x_norm_r, y_norm_r), radius_20_norm, facecolor='none', edgecolor='red', linewidth=1, zorder=3)
                circle_30 = plt.Circle((x_norm_r, y_norm_r), radius_30_norm, facecolor='none', edgecolor='red', linewidth=1, zorder=3)
                ax.add_patch(circle_10)
                ax.add_patch(circle_20)
                ax.add_patch(circle_30)

                label_offset_x = data.shape[1] * 0.01
                x_10_label = x_norm_r + radius_10_norm + label_offset_x
                x_20_label = x_norm_r + radius_20_norm + label_offset_x
                x_30_label = x_norm_r + radius_30_norm + label_offset_x
                
                # labels de anillos
                ax.text(x_10_label, y_norm_r, '10', color='yellow', fontsize=8, ha='left', va='center', zorder=4, bbox=dict(facecolor='black', alpha=0.5))
                ax.text(x_20_label, y_norm_r, '20', color='yellow', fontsize=8, ha='left', va='center', zorder=4, bbox=dict(facecolor='black', alpha=0.5))
                ax.text(x_30_label, y_norm_r, '30', color='yellow', fontsize=8, ha='left', va='center', zorder=4, bbox=dict(facecolor='black', alpha=0.5))

    if label:
        img_width = data.shape[1]
        img_height = data.shape[0]

        # Altura fija y proporcional de la barra inferior según el ancho de la imagen
        # Si el ancho es estrecho (< 700 px), se usan 2 renglones para que no colisionen el Título y la Institución
        is_compact = img_width < 700
        bar_height_px = 60 if is_compact else 48

        # Barra negra en el borde inferior con zorder adecuado
        ax.add_patch(Rectangle((0, 0), img_width, bar_height_px, alpha=1, zorder=2, facecolor='black'))

        # Barra de color horizontal posicionada en la parte superior del contenedor negro
        cbar_h = 10 / img_height
        cbar_bottom = (bar_height_px - 24) / img_height
        cbar_ax = fig.add_axes([0.0, cbar_bottom, 1.0, cbar_h])
        cb = fig.colorbar(im, cax=cbar_ax, orientation='horizontal')
        cb.outline.set_visible(False)
        cb.ax.tick_params(width=0)
        cb.ax.xaxis.set_ticks_position('top')
        cb.ax.xaxis.set_label_position('top')
        label_size = 5 if is_compact else 6
        cb.ax.tick_params(axis='x', colors='yellow', labelsize=label_size, pad=-8, labelbottom=False, labeltop=True)

        # Ubicación del texto en la sección inferior de la barra negra
        if is_compact:
            title_fsize = config['plotting'].get('title_font_size_zoomed', 7.5)
            inst_fsize = config['plotting'].get('institution_font_size_zoomed', 7.5)
            # Renglón superior: Título del producto satelital
            ax.text(img_width * 0.02, 24, Title, horizontalalignment='left', verticalalignment='center', color='white', size=title_fsize, zorder=4)
            # Renglón inferior: Institución / Marca de agua (solo si está definida)
            if Institution and str(Institution).strip():
                ax.text(img_width * 0.02, 10, str(Institution).strip(), horizontalalignment='left', verticalalignment='center', color='white', size=inst_fsize, zorder=4)
        else:
            title_fsize = config['plotting'].get('title_font_size_zoomed', 8) if lat is not None and lon is not None else config['plotting'].get('title_font_size_full', 9)
            inst_fsize = config['plotting'].get('institution_font_size_zoomed', 8) if lat is not None and lon is not None else config['plotting'].get('institution_font_size_full', 9)
            text_y = 11
            ax.text(img_width * 0.02, text_y, Title, horizontalalignment='left', verticalalignment='center', color='white', size=title_fsize, zorder=4)
            if Institution and str(Institution).strip():
                ax.text(img_width * 0.98, text_y, str(Institution).strip(), horizontalalignment='right', verticalalignment='center', color='white', size=inst_fsize, zorder=4)
        

    date = (datetime.strptime(time_coverage_start, '%Y-%m-%dT%H:%M:%S.%fZ'))
    imageName = date.strftime('%Y%m%d%H%M') + ".png"
    outFolder = os.path.join(basePath, config['paths']['output'], dayjulianstring, "C" + BandString)
    create_folder(outFolder)
    imageOut = os.path.join(outFolder, imageName)
    logging.info("Imagen generada: %s", imageOut)

    fig_width_px = fig.get_figwidth() * fig.dpi
    fig_height_px = fig.get_figheight() * fig.dpi

    # Save with exact dimensions
    plt.savefig(imageOut, dpi=DPI, pad_inches=0)

    outFolder = os.path.join(basePath, "latest")
    create_folder(outFolder)
    imageOut_latest = os.path.join(outFolder, "latestC" + BandString + ".png")
    logging.debug("Imagen latest: %s", imageOut_latest)
    plt.savefig(imageOut_latest, dpi=DPI, pad_inches=0)

    # Calculate resolutions based on the full data shape
    resl_x = abs(extent[3] - extent[1]) / (data.shape[0] -1)  # Latitude resolution
    resl_y = abs(extent[2] - extent[0]) / (data.shape[1] -1)  # Longitude resolution

    # Adjust origin to center of bottom-left pixel
    lonO = extent[0] - (resl_y / 2)  # Shift to center of first pixel
    latS = extent[1] + (resl_x / 2) - resl_x # Shift to center of first pixel

    # Calculate top latitude for .pgw (bottom-left convention)
    latN = latS + (data.shape[0] - 1) * resl_x

    # Generate navigation string for .pgw
    navigation = f"{resl_y}\n0\n0\n{-resl_x}\n{lonO}\n{latS + (data.shape[0] - 1) * resl_x}"

    imageName = date.strftime('%Y%m%d%H%M') + ".pgw"
    outFolder = os.path.join(basePath, config['paths']['output'], dayjulianstring, "C" + BandString)
    pgwOut = os.path.join(outFolder, imageName)
    with open(pgwOut, 'w') as f:
        f.write(navigation)

    imageName = "latestC" + BandString + ".pgw"
    outFolder = os.path.join(basePath, "latest")
    pgwLatest = os.path.join(outFolder, imageName)
    with open(pgwLatest, 'w') as f:
        f.write(navigation)

    if generateTiff:
        imageName = date.strftime('%Y%m%d%H%M') + ".tif"
        outFolder = os.path.join(basePath, config['paths']['output'], dayjulianstring, "C" + BandString)
        imageOut = os.path.join(outFolder, imageName)
        driver = gdal.GetDriverByName('GTiff')
        try:
            # Scale data to 2 decimal places (multiply by 100) and convert to Int16
            data_scaled = np.round(data * 100).astype(np.int16)  # e.g., 12.34 becomes 1234
            #data_scaled = np.round(data).astype(np.int16)  # e.g., 12.34 becomes 12
            data_flipped = np.flipud(data_scaled)

            out_ds = driver.Create(imageOut, data.shape[1], data.shape[0], 1, gdal.GDT_Int16, options=['COMPRESS=LZW'])
            if out_ds is None:
                raise Exception("Failed to create TIFF dataset")
            
            resl_x = abs(extent[3] - extent[1]) / data.shape[0]
            resl_y = abs(extent[2] - extent[0]) / data.shape[1]
            lonO = extent[0]
            latS = extent[1]
            geotransform = (lonO, resl_y, 0, latS, 0, resl_x)
            out_ds.SetGeoTransform(geotransform)

            out_ds.SetProjection('EPSG:4326')

            band = out_ds.GetRasterBand(1)
            band.WriteArray(data_flipped)
            band.SetDescription('Brightness Temperature [°C * 100]')  # Indicate scaling in description
            band.SetNoDataValue(-9999)  # Matches Int16 range
            band.FlushCache()

            stats = band.ComputeStatistics(0)
            #print(f"TIFF stats (min, max, mean, stddev): {stats}")

            logging.info(f"TIFF generated successfully: {imageOut}")
        except Exception as e:
            logging.error(f"Error generating TIFF: {e}")
        finally:
            out_ds = None
            driver = None

    #if generateTiff:
    #    print(f"Grid type: {type(grid)}")       

def validate_date(date_str: str) -> Optional[str]:
    """
    Validates that an observation date adheres to the ISO 8601 calendar format 'YYYYMMDD'.

    Args:
        date_str (str): Date string to validate.

    Returns:
        Optional[str]: Sanitized date string if valid, or None if validation fails.
    """
    try:
        datetime.strptime(date_str, '%Y%m%d')
        return date_str
    except ValueError:
        logging.error(f"Fecha inválida: {date_str}. Debe ser YYYYMMDD")
        return None

def validate_time(time_str: str) -> Optional[str]:
    """
    Validates that a 2-digit hour or minute string is an integer within [00, 59].

    Args:
        time_str (str): Time component string (HH or MM).

    Returns:
        Optional[str]: Validated 2-digit zero-padded time string, or None if invalid.
    """
    if len(time_str) != 2 or not time_str.isdigit() or not (0 <= int(time_str) <= 59):
        logging.error(f"Hora/minuto inválido: {time_str}. Debe tener 2 dígitos (00-59).")
        return None
    return time_str

def validate_lat(lat: Optional[float]) -> Optional[float]:
    """
    Validates that a geographic latitude is within the spherical domain [-90.0, 90.0].

    Args:
        lat (Optional[float]): Candidate latitude in decimal degrees.

    Returns:
        Optional[float]: Validated latitude float, or None if out of bounds or absent.
    """
    if lat is None:
        return None
    if -90.0 <= lat <= 90.0:
        return lat
    else:
        logging.error("Latitud debe estar entre -90 y 90.")
        return None

def validate_lon(lon: Optional[float]) -> Optional[float]:
    """
    Validates that a geographic longitude is within the spherical domain [-180.0, 180.0].

    Args:
        lon (Optional[float]): Candidate longitude in decimal degrees.

    Returns:
        Optional[float]: Validated longitude float, or None if out of bounds or absent.
    """
    if lon is None:
        return None
    if -180.0 <= lon <= 180.0:
        return lon
    else:
        logging.error("Longitud debe estar entre -180 y 180.")
        return None

def build_parser() -> argparse.ArgumentParser:
    """
    Constructs the CLI argument parser with support for standard English flags
    and backward-compatible Spanish aliases.

    Returns:
        argparse.ArgumentParser: Configured command-line argument parser.
    """
    parser = argparse.ArgumentParser(
        description='GOES-16/19 Satellite Imagery Processing & Visualization Toolkit'
    )
    parser.add_argument(
        '--mode', '--tipo',
        dest='mode',
        type=str,
        required=True,
        help='Execution mode: auto | manual'
    )
    parser.add_argument(
        '--source', '--fuente',
        dest='source',
        type=str,
        required=True,
        help='Data source: aws | ideam'
    )
    parser.add_argument(
        '--date', '--dates', '--fecha',
        dest='date',
        type=str,
        help='Date(s) in YYYYMMDD format, comma-separated (e.g. 20240929,20240930)'
    )
    parser.add_argument(
        '--hours', '--horas',
        dest='hours',
        type=str,
        help='UTC hour(s) in HH format, comma-separated (e.g. 01,02,12)'
    )
    parser.add_argument(
        '--minutes', '--minutos',
        dest='minutes',
        type=str,
        help='Minute(s) in MM format, comma-separated (e.g. 00,30)'
    )
    parser.add_argument(
        '--lat',
        dest='lat',
        type=str,
        help='Target latitude(s) comma-separated (-90 to 90)'
    )
    parser.add_argument(
        '--lon',
        dest='lon',
        type=str,
        help='Target longitude(s) comma-separated (-180 to 180)'
    )
    parser.add_argument(
        '--label',
        dest='label',
        type=lambda x: x.lower() == 'true',
        default=False,
        help='Render title bar, colorbar and metadata (True/False)'
    )
    parser.add_argument(
        '--bullseye',
        dest='bullseye',
        type=lambda x: x.lower() == 'true',
        default=True,
        help='Draw concentric range rings around target coordinates (True/False)'
    )
    parser.add_argument(
        '--watermark', '--institution', '--institucion',
        dest='watermark',
        type=str,
        default=None,
        help='Custom watermark or attribution label on the bottom bar'
    )
    return parser

def main(argv: Optional[List[str]] = None) -> None:
    """
    Main entry point for command-line parsing and pipeline execution.

    Parses command-line arguments, validates dates, hours, minutes, and geographic
    coordinates, and branches into either manual targeted processing or automated
    near-real-time streaming.

    Args:
        argv (Optional[List[str]], optional): List of CLI argument tokens.
            If None, defaults to sys.argv[1:].
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.info("Execution mode: %s", args.mode)

    if args.mode == "manual":
        if args.date is None:
            logging.error('Manual mode requires the --date (or --fecha) parameter (e.g. --date=20240929)')
            parser.print_help()
            sys.exit(1)
        elif args.hours is None:
            logging.error('Manual mode requires the --hours (or --horas) parameter (e.g. --hours=11,12)')
            parser.print_help()
            sys.exit(1)
        elif args.minutes is None:
            logging.error('Manual mode requires the --minutes (or --minutos) parameter (e.g. --minutes=00,30)')
            parser.print_help()
            sys.exit(1)
        else:
            # Validar lista de fechas
            dates = [d.strip() for d in args.date.split(',')]
            validated_dates = [d for d in map(validate_date, dates) if d is not None]
            if len(validated_dates) < len(dates):
                logging.error("One or more dates are invalid. Please use YYYYMMDD format.")
                sys.exit(1)

            # Validar horas
            hours = [h.strip() for h in args.hours.split(',')]
            validated_hours = [h for h in map(validate_time, hours) if h is not None]
            if len(validated_hours) < len(hours):
                logging.error("One or more hours are invalid. Must be 2-digit numbers (00-23).")
                sys.exit(1)

            # Validar minutos
            minutes = [m.strip() for m in args.minutes.split(',')]
            validated_minutes = [m for m in map(validate_time, minutes) if m is not None]
            if len(validated_minutes) < len(minutes):
                logging.error("One or more minutes are invalid. Must be 2-digit numbers (00-59).")
                sys.exit(1)

            # Procesar latitud y longitud
            lats = []
            lons = []
            
            if args.lat is not None:
                try:
                    lats = [float(x.strip()) for x in args.lat.split(',')]
                    validated_lats = [validate_lat(l) for l in lats]
                    if None in validated_lats:
                        logging.error("One or more latitudes are invalid. Must be between -90 and 90.")
                        sys.exit(1)
                    lats = validated_lats
                except ValueError:
                    logging.error("Invalid latitude format. Must be a number or comma-separated numbers.")
                    sys.exit(1)

            if args.lon is not None:
                try:
                    lons = [float(x.strip()) for x in args.lon.split(',')]
                    validated_lons = [validate_lon(l) for l in lons]
                    if None in validated_lons:
                        logging.error("One or more longitudes are invalid. Must be between -180 and 180.")
                        sys.exit(1)
                    lons = validated_lons
                except ValueError:
                    logging.error("Invalid longitude format. Must be a number or comma-separated numbers.")
                    sys.exit(1)

            # Verificar que tengan la misma longitud si ambos están presentes
            if lats and lons and len(lats) != len(lons):
                logging.error("Latitude and longitude counts must match.")
                sys.exit(1)

            final_lat = lats if lats else None
            final_lon = lons if lons else None

            # Continuar con proceso manual
            manual_date(
                validated_dates,
                validated_hours,
                validated_minutes,
                final_lat,
                final_lon,
                args.label,
                args.bullseye,
                watermark=args.watermark
            )

    elif args.mode == "auto":
        auto_date(args.source, args.label, watermark=args.watermark)

    else:
        logging.error('Unknown execution mode: %s. Use: manual | auto', args.mode)
        parser.print_help()
        sys.exit(1)    
# Punto de entrada del script
if __name__ == "__main__":
    main()
