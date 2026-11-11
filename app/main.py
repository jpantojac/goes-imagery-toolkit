#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# File: main.py
# Author: Julian Pantoja Clavijo <julianpc.dev@gmail.com>
# Description: Script para procesamiento, calibración y generación de imágenes satelitales GOES-16/19
# License: MIT
#
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
import numpy as np
import matplotlib.pyplot as plt
from libs.cpt_convert import loadCPT
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle
try:
    import colors.colors as colors
except (ImportError, ModuleNotFoundError):
    colors = None
import time
import requests
from bs4 import BeautifulSoup
import urllib3
from typing import Optional, List, Union
from PIL import Image
import matplotlib
try:
    from metpy.plots import colortables
except (ImportError, ModuleNotFoundError):
    colortables = None
import yaml



# Configuración inicial de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


# Cargar configuración desde YAML
def load_config(config_path=None):
    """
    Carga la configuración desde un archivo YAML.
    
    Args:
        config_path (str, optional): Ruta al archivo de configuración.

    Returns:
        dict: Diccionario con los valores de configuración.
    """
    if config_path is None:
        cand_path = os.path.join(SCRIPT_DIR, "config.yaml")
        config_path = cand_path if os.path.exists(cand_path) else "config.yaml"
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"No se encontró el archivo de configuración: {config_path}")
    except Exception as e:
        raise RuntimeError(f"Error al leer el archivo de configuración: {e}")

config = load_config()

# Configuraciones generales
basePath = config.get('paths', {}).get('base', '')
if not basePath or basePath.strip() in [".", ""]:
    basePath = SCRIPT_DIR

institucion         = config['general']['institucion']
generateTiff        = config['general']['generateTiff']
channels            = config['satelite']['channels']
channelsIdeam       = config['satelite']['channels_ideam']
archivo_registro    = config['general']['archivo_registro']
base_url            = config['satelite']['base_url']
satellite           = config['satelite']['satellite']

# Globales
dsatellite = satellite.replace('G','goes')
ncFile = None
fechas_julianas = []


def R2BT(radiance: np.ndarray, channel: str) -> np.ndarray:
    """
    Convierte radiancia a temperatura de brillo (°C) para bandas térmicas (ej. C13).

    Args:
        radiance (np.ndarray): Arreglo de radiancia del sensor GOES.
        channel (str): Canal del sensor (por ejemplo, 'C13').

    Returns:
        np.ndarray: Temperatura de brillo en grados Celsius.
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

def R2BT_WV_visual(rad, channel):
    """
    Normalización visual para las bandas de Vapor de Agua.
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
    Convierte radiancia a reflectancia para bandas visibles/infrarrojo cercano (ej. C02),
    con corrección gamma.

    Args:
        radiance (np.ndarray): Datos de radiancia del sensor GOES.
        channel (str): Canal correspondiente a la banda visible (por ejemplo, 'C02').

    Returns:
        np.ndarray: Reflectancia ajustada con corrección gamma (0..1).
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

def create_folder(ruta, clean=False):
    """
    Crea una carpeta en la ruta especificada o limpia su contenido si ya existe.

    Args:
        ruta (str): Ruta donde se creará la carpeta.
        clean (bool, optional): Si es True, elimina el contenido si la carpeta ya existe. Por defecto es False.

    Returns:
        bool: True si la operación fue exitosa, False si ocurrió un error.
    """
    try:
        if os.path.exists(ruta):
            if clean:
                # Eliminar contenido de la carpeta
                for filename in os.listdir(ruta):
                    file_path = os.path.join(ruta, filename)
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                logging.debug("Contenido de la carpeta eliminado: %s", ruta)
        else:
            # Crear carpeta si no existe
            os.makedirs(ruta)
            logging.debug("Carpeta creada: %s", ruta)
        return True
    except Exception as e:
        logging.error("Error al gestionar carpeta %s: %s", ruta, e)
        return False

def prepare_folders(dates):
    """
    Prepara las carpetas de entrada y salida para las fechas especificadas.

    Args:
        dates (List[str]): Lista de fechas en formato 'YYYYMMDD'.
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

def download(dates,hours,minutes):
    """
    Descarga archivos de radiancia GOES para fechas y horarios específicos.

    Args:
        dates (List[str]): Lista de fechas en formato 'YYYYMMDD'.
        hours (List[str]): Lista de horas en formato 'HH'.
        minutes (List[str]): Lista de minutos en formato 'MM'.

    Returns:
        List[str]: Lista de rutas de archivos descargados.
    """
    fulllist = []
    # Iterar sobre los valores del array
    for date in dates:
        for hour in hours:
            for minute in minutes:
                #print('entra:' +date + ' ' + hour + ' ' + minute)
                fecha_hora = datetime.strptime(date+"-"+hour+minute+'00', '%Y%m%d-%H%M%S')
                # Sumar 5 minutos
                nueva_fecha_hora = fecha_hora + timedelta(minutes=10)
                dateend = nueva_fecha_hora.strftime('%Y%m%d-%H%M%S')
                #descargar a la carpeta juliana
                fecha_dt = datetime.strptime(date, "%Y%m%d")
                fecha_juliana = fecha_dt.strftime("%j")
                output = (os.path.join(basePath, config['paths']['input'], fecha_juliana).rstrip(os.sep)+ os.sep)
                #print(output)
                #print(date+"-"+hour+minute+'00')
                #print(dateend)
                flist = GOES.download(dsatellite, 'ABI-L1b-RadF',
                            DateTimeIni = date+"-"+hour+minute+'00', 
                            DateTimeFin = dateend, 
                            channel = channels, 
                            path_out=output)
                fulllist += flist
    return fulllist                

def auto_date(fuente, label, watermark=None):
    """
    Ejecuta la generación automática de imágenes satelitales según la fuente especificada.

    Args:
        fuente (str): Fuente de los datos ('aws' o 'ideam').
        label (bool): Si es True, añade etiquetas e información adicional en la imagen.
        watermark (Optional[str]): Texto de marca de agua o institución opcional.
    """
    logging.info("Auto generation")
    if fuente == 'aws':
        source_AWS(label, watermark=watermark)
    elif fuente == "ideam":
        source_IDEAM(label, watermark=watermark)
    else:
        logging.info('Fuente no encontrada. aws|ideam')

# Función para descargar el archivo
def donwload_file(url, nombre_archivo):
    """
    Descarga un archivo desde una URL y lo guarda en la carpeta correspondiente.

    Args:
        url (str): URL del archivo a descargar.
        nombre_archivo (str): Nombre del archivo a guardar.
    """
    logging.info(f"Descargando {nombre_archivo} desde {url}...")
    response = requests.get(url, verify=False)
    Start = (nombre_archivo[nombre_archivo.find("_s")+2:nombre_archivo.find("_e")])

    dayjulianstring = Start[4:7] 
    create_folder(os.path.join(basePath,config['paths']['input'],dayjulianstring),False)   
    directorio_descargas = os.path.join(basePath,config['paths']['input'],dayjulianstring)
    with open(os.path.join(directorio_descargas, nombre_archivo), 'wb') as f:
        f.write(response.content)
    logging.info(f"Descarga completada: {nombre_archivo}")

# Función para escribir el archivo de registro de la última descarga
def write_latest_downloaded(ultima_descarga):
    """
    Escribe en un archivo de texto el registro de las últimas descargas por canal.

    Args:
        ultima_descarga (dict): Diccionario con el nombre del canal como clave y el nombre del archivo descargado como valor.
    """
    with open(archivo_registro, 'w') as f:
        for canal, archivo in ultima_descarga.items():
            f.write(f"{canal}={archivo}\n")

def source_IDEAM(label):
    """
    Descarga los archivos más recientes disponibles desde la fuente IDEAM y procesa las imágenes.

    Args:
        label (bool): Si es True, añade etiquetas e información adicional en la imagen.
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

def source_AWS(label, watermark=None):
    """
    Descarga y procesa datos satelitales GOES desde AWS, correspondientes a 10 minutos antes del tiempo actual.

    Args:
        label (bool): Si es True, añade etiquetas e información adicional en la imagen.
        watermark (Optional[str]): Texto de marca de agua o institución opcional.
    """
    #logging.info(label)
    utc = time.gmtime()
    tenMinutesAgo = time.time() - ( 60 * 10 )
    utcTenMinutesAgo = time.gmtime(tenMinutesAgo)
    # Obtener los minutos de utcTenMinutesAgo
    current_minutes = utcTenMinutesAgo.tm_min
    # Redondear hacia abajo al múltiplo de 10 más cercano
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

    #print(year+month+day+' '+hour+' '+minute)
    dates=[]
    hours=[]
    minutes=[]
    dates.append(year+month+day)
    hours.append(hour)
    minutes.append(minute)
    prepare_folders(dates)
    flist = download(dates,hours,minutes)

    for aFile in flist:
        processImage(aFile, label=label, watermark=watermark)

def manual_date(dates, hours, minutes, lat, lon, label, bullseye=True, watermark=None):
    """
    Ejecuta la generación manual de imágenes satelitales para fechas y horarios específicos.

    Args:
        dates (List[str]): Lista de fechas en formato 'YYYYMMDD'.
        hours (List[str]): Lista de horas en formato 'HH'.
        minutes (List[str]): Lista de minutos en formato 'MM'.
        lat (Union[float, List[float], None]): Latitud(es) del marcador a resaltar.
        lon (Union[float, List[float], None]): Longitud(es) del marcador a resaltar.
        label (bool): Si es True, muestra etiquetas e información adicional en la imagen.
        watermark (Optional[str]): Texto de marca de agua o institución opcional.
    """
    global fechas_julianas
    prepare_folders(dates)
    flist = download(dates,hours,minutes)
          
    for aFile in flist:
        processImage(aFile, lat, lon, label=label, bullseye=bullseye, watermark=watermark)

def get_band(nombre_archivo,isString):
    """
    Extrae el número de banda desde el nombre del archivo.

    Args:
        nombre_archivo (str): Nombre del archivo satelital.
        isString (bool): Si es True, devuelve el número como entero; de lo contrario, como cadena.

    Returns:
        Union[int, str, None]: Número de banda, o None si no se puede extraer.
    """
    inicio = nombre_archivo.find("M4C") if "M4C" in nombre_archivo else nombre_archivo.find("M6C")
    fin = nombre_archivo.find("_"+satellite)
    if inicio != -1 and fin != -1:
        if isString == True:
            salida = int(nombre_archivo[inicio+3:fin])
        else:
            salida = nombre_archivo[inicio+3:fin]    
        return salida
    return None

def get_bounding_box(lat, lon, radius_miles=100):
    """
    Calcula una caja delimitadora (bounding box) alrededor de un punto geográfico.

    Args:
        lat (float): Latitud del punto central.
        lon (float): Longitud del punto central.
        radius_miles (float, optional): Radio de la caja en millas. Por defecto es 100.

    Returns:
        List[float]: Lista [oeste, sur, este, norte] que representa la bounding box.
    """
    # Convert miles to degrees (approximate)
    miles_to_deg = 1 / 69.0  # 1 degree ≈ 69 miles
    radius_deg = radius_miles * miles_to_deg

    # Calculate the bounding box
    south = lat - radius_deg
    north = lat + radius_deg
    west = lon - radius_deg
    east = lon + radius_deg

    return [west, south, east, north]

def processImage(aFile: str, lat: Optional[Union[float, List[float]]] = None, lon: Optional[Union[float, List[float]]] = None, label: bool = False, bullseye: bool = True, watermark: Optional[str] = None) -> None:
    """
    Procesa un archivo NetCDF de GOES para generar una imagen satelital georreferenciada.

    Realiza el remapeo de datos, conversión a reflectancia o temperatura de brillo,
    aplica el colormap correspondiente, sobrepone formas geográficas y genera archivos
    PNG y TIFF con sus archivos auxiliares de georreferenciación (.pgw).

    Args:
        aFile (str): Ruta del archivo NetCDF a procesar.
        lat (Optional[Union[float, List[float]]], optional): Latitud(es) del punto de interés.
        lon (Optional[Union[float, List[float]]], optional): Longitud(es) del punto de interés.
        label (bool, optional): Si es True, añade título, escala de colores y nombre de la institución en la imagen. Por defecto es False.
        bullseye (bool, optional): Si es True, dibuja anillos concéntricos alrededor del punto/centroide.
        watermark (Optional[str], optional): Texto o institución para la marca de agua inferior. Si es None, toma el valor de config.yaml.

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
    Institution = watermark if watermark is not None else config.get('general', {}).get('institucion', '')

    aImage = os.path.join(basePath, config['paths']['input'], dayjulianstring, aFile)
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
        data = np.array(Image.fromarray(data.astype(np.float32)).resize((new_width, new_height), Image.Resampling.LANCZOS))
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

    shapefile_path = os.path.join(basePath, config['paths']['shapes'],config['shapes']['departamentos'])
    bmap.readshapefile(shapefile_path, config['shapes']['departamentos_layer'], drawbounds=False)

    #print(f"Number of shapes loaded: {len(bmap.MGN_DPTO_POLITICO)}")
    #if len(bmap.MGN_DPTO_POLITICO) > 0:
    #    print(f"Sample shape (first 5 points): {bmap.MGN_DPTO_POLITICO[0][:5]}")

    for shape in bmap.MGN_DPTO_POLITICO:
        x = [point[0] for point in shape]
        y = [point[1] for point in shape]
        x_norm = [(lon - extent[0]) / (extent[2] - extent[0]) * data.shape[1] for lon in x]
        y_norm = [(lat - extent[1]) / (extent[3] - extent[1]) * data.shape[0] for lat in y]
        ax.plot(x_norm, y_norm, color='white', linewidth=0.6, zorder=2)

    country_shapefile_path = os.path.join(basePath, config['paths']['shapes'],config['shapes']['paises'])
    bmap.readshapefile(country_shapefile_path, config['shapes']['paises_layer'], drawbounds=False)

    #print(f"Number of country shapes loaded: {len(bmap.countries)}")
    #if len(bmap.countries) > 0:
    #    print(f"Sample country shape (first 5 points): {bmap.countries[0][:5]}")

    for shape in bmap.countries:
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

def validate_date(date_str):
    """
    Valida que una fecha esté en formato YYYYMMDD.
    
    Args:
        date_str (str): Fecha a validar
        
    Returns:
        str: Fecha válida o None si es inválida
    """
    try:
        datetime.strptime(date_str, '%Y%m%d')
        return date_str
    except ValueError:
        logging.error(f"Fecha inválida: {date_str}. Debe ser YYYYMMDD")
        return None

def validate_time(time_str):
    """
    Valida que una hora/minuto sea un número de dos dígitos.
    
    Args:
        time_str (str): Hora o minuto a validar
        
    Returns:
        str: Valor válido o None si es inválido
    """
    if len(time_str) != 2 or not time_str.isdigit():
        logging.error(f"Hora/minuto inválido: {time_str}. Debe tener 2 dígitos.")
        return None
    return time_str

def validate_lat(lat):
    """
    Valida que la latitud esté en rango (-90 a 90) o sea None.
    
    Args:
        lat (float): Latitud proporcionada
        
    Returns:
        float: Latitud válida o None si es inválida
    """
    if lat is None:
        return None
    if -90 <= lat <= 90:
        return lat
    else:
        logging.error("Latitud debe estar entre -90 y 90.")
        return None

def validate_lon(lon):
    """
    Valida que la longitud esté en rango (-180 a 180) o sea None.
    
    Args:
        lon (float): Longitud proporcionada
        
    Returns:
        float: Longitud válida o None si es inválida
    """
    if lon is None:
        return None
    if -180 <= lon <= 180:
        return lon
    else:
        logging.error("Longitud debe estar entre -180 y 180.")
        return None

def main():
    """
    Función principal que se encarga de recibir los parámetros de ejecucion y ejecutar el proceso de generación de imágenes.

    Returns:
        null: No retorna argumentos.
    """
    parser = argparse.ArgumentParser(description='Script para procesamiento de imágenes satelitales del GOES-19')
    parser.add_argument('--tipo', type=str, required=True, help='Tipo de ejecucion: auto/manual')
    parser.add_argument('--fecha', type=str, help='Lista de fechas en formato YYYYMMDD separadas por comas (ej: 20240507)')
    parser.add_argument('--horas', type=str, help='Horas en formato HH separadas por comas (ej: 01,02)')
    parser.add_argument('--minutos', type=str, help='Minutos en formato MM separados por comas (ej: 00,10)')
    parser.add_argument('--fuente', type=str, required=True, help='Fuente de los datos: aws | ideam')
    parser.add_argument('--lat', type=str, help='Latitud(es) del marcador separadas por comas (entre -90 y 90)')
    parser.add_argument('--lon', type=str, help='Longitud(es) del marcador separadas por comas (entre -180 y 180)')
    parser.add_argument('--label', type=lambda x: x.lower() == 'true', default=False, help='Mostrar etiquetas y barra de color (True/False)')
    parser.add_argument('--bullseye', type=lambda x: x.lower() == 'true', default=True, help='Mostrar anillos alrededor de los puntos (True/False)')
    parser.add_argument('--watermark', '--institucion', type=str, default=None, help='Texto o marca de agua personalizada para la barra inferior')

    args = parser.parse_args()

    logging.info("Modo de ejecución: %s", args.tipo)

    if args.tipo == "manual":
        if args.fecha is None:
            logging.error('Para generar imágenes de tipo "manual" se requiere el parámetro --fecha=20220101,20220102')
            parser.print_help()
            sys.exit(1)
        elif args.horas is None:
            logging.error('Para generar imágenes de tipo "manual" se requiere el parámetro --horas=01,02')
            parser.print_help()
            sys.exit(1)
        elif args.minutos is None:
            logging.error('Para generar imágenes de tipo "manual" se requiere el parámetro --minutos=00,10')
            parser.print_help()
            sys.exit(1)
        else:
            # Validar lista de fechas
            dates = args.fecha.split(',')
            validated_dates = [d for d in map(validate_date, dates) if d is not None]
            if len(validated_dates) < len(dates):
                logging.error("Una o más fechas son inválidas. Usa formato YYYYMMDD.")
                sys.exit(1)

            # Validar horas
            hours = args.horas.split(',')
            validated_hours = [h for h in map(validate_time, hours) if h is not None]
            if len(validated_hours) < len(hours):
                logging.error("Una o más horas son inválidas. Deben ser números de 2 dígitos.")
                sys.exit(1)

            # Validar minutos
            minutes = args.minutos.split(',')
            validated_minutes = [m for m in map(validate_time, minutes) if m is not None]
            if len(validated_minutes) < len(minutes):
                logging.error("Uno o más minutos son inválidos. Deben ser números de 2 dígitos.")
                sys.exit(1)

            # Procesar latitud y longitud (pueden ser uno o varios valores)
            lats = []
            lons = []
            
            if args.lat is not None:
                try:
                    lats = [float(x.strip()) for x in args.lat.split(',')]
                    validated_lats = [validate_lat(l) for l in lats]
                    if None in validated_lats:
                        logging.error("Una o más latitudes son inválidas. Deben estar entre -90 y 90.")
                        sys.exit(1)
                    lats = validated_lats
                except ValueError:
                    logging.error("Formato de latitud inválido. Debe ser un número o lista de números separados por comas.")
                    sys.exit(1)

            if args.lon is not None:
                try:
                    lons = [float(x.strip()) for x in args.lon.split(',')]
                    validated_lons = [validate_lon(l) for l in lons]
                    if None in validated_lons:
                        logging.error("Una o más longitudes son inválidas. Deben estar entre -180 y 180.")
                        sys.exit(1)
                    lons = validated_lons
                except ValueError:
                    logging.error("Formato de longitud inválido. Debe ser un número o lista de números separados por comas.")
                    sys.exit(1)

            # Verificar que tengan la misma longitud si ambos están presentes
            if lats and lons and len(lats) != len(lons):
                logging.error("La cantidad de latitudes y longitudes debe ser la misma.")
                sys.exit(1)

            # Si se proporcionó solo uno, usar el valor como flotante (o lista de un elemento)
            # manual_date ahora espera listas o None
            final_lat = lats if lats else None
            final_lon = lons if lons else None

            # Continuar con proceso manual
            manual_date(validated_dates, validated_hours, validated_minutes, final_lat, final_lon, args.label, args.bullseye, watermark=args.watermark)

    elif args.tipo == "auto":
        auto_date(args.fuente, args.label, watermark=args.watermark)

    else:
        logging.error('Tipo de ejecución desconocido. Usa: manual|auto')
        parser.print_help()
        sys.exit(1)    
# Punto de entrada del script
if __name__ == "__main__":
    main()
