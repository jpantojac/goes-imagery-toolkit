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
    from urllib3.util.retry import Retry
    from requests.adapters import HTTPAdapter
except (ImportError, ModuleNotFoundError):
    requests = None
    BeautifulSoup = None
    Retry = None
    HTTPAdapter = None

import urllib3
from typing import Optional, List, Union, Callable, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

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

import tempfile
try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

class SingleInstanceLock:
    """
    Guarantees mutual exclusion across pipeline executions using kernel-level
    file locking (flock on POSIX, msvcrt on Windows) to prevent overlapping
    cron runs or concurrent worker conflicts.
    """
    def __init__(self, lockfile_path: Optional[str] = None):
        if lockfile_path is None:
            lockfile_path = os.path.join(tempfile.gettempdir(), "goes_pipeline_execution.lock")
        self.lockfile_path = lockfile_path
        self.fp = None

    def acquire(self) -> bool:
        try:
            if fcntl is not None:
                self.fp = open(self.lockfile_path, "w")
                fcntl.flock(self.fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.fp.write(f"{os.getpid()}\n")
                self.fp.flush()
                return True
            elif msvcrt is not None:
                self.fp = open(self.lockfile_path, "r+") if os.path.exists(self.lockfile_path) else open(self.lockfile_path, "w+")
                msvcrt.locking(self.fp.fileno(), msvcrt.LK_NBLCK, 1)
                self.fp.seek(0)
                self.fp.truncate()
                self.fp.write(f"{os.getpid()}\n")
                self.fp.flush()
                return True
            else:
                self.fp = open(self.lockfile_path, "w")
                self.fp.write(f"{os.getpid()}\n")
                self.fp.flush()
                return True
        except (IOError, BlockingIOError, PermissionError, OSError):
            if self.fp is not None:
                try:
                    self.fp.close()
                except Exception:
                    pass
                self.fp = None
            return False

    def release(self) -> None:
        if self.fp is not None:
            try:
                if fcntl is not None:
                    fcntl.flock(self.fp.fileno(), fcntl.LOCK_UN)
                elif msvcrt is not None:
                    try:
                        self.fp.seek(0)
                        msvcrt.locking(self.fp.fileno(), msvcrt.LK_UNLCK, 1)
                    except Exception:
                        pass
                self.fp.close()
                if os.path.exists(self.lockfile_path):
                    os.remove(self.lockfile_path)
            except Exception:
                pass
            self.fp = None

    @classmethod
    def get_running_pid(cls, lockfile_path: Optional[str] = None) -> Optional[int]:
        if lockfile_path is None:
            lockfile_path = os.path.join(tempfile.gettempdir(), "goes_pipeline_execution.lock")
        if os.path.exists(lockfile_path):
            try:
                with open(lockfile_path, "r") as f:
                    content = f.read().strip()
                    if content.isdigit():
                        return int(content)
            except Exception:
                pass
        return None

    @classmethod
    def stop_running_instance(cls, lockfile_path: Optional[str] = None) -> bool:
        pid = cls.get_running_pid(lockfile_path)
        if pid is not None and pid != os.getpid():
            try:
                import signal
                os.kill(pid, signal.SIGTERM)
                logging.info(f"Sent SIGTERM to running pipeline daemon (PID {pid}).")
                time.sleep(0.5)
                if lockfile_path is None:
                    lockfile_path = os.path.join(tempfile.gettempdir(), "goes_pipeline_execution.lock")
                if os.path.exists(lockfile_path):
                    try:
                        os.remove(lockfile_path)
                    except Exception:
                        pass
                return True
            except ProcessLookupError:
                logging.info(f"Process {pid} was already terminated. Cleaned stale lock.")
                if lockfile_path is None:
                    lockfile_path = os.path.join(tempfile.gettempdir(), "goes_pipeline_execution.lock")
                if os.path.exists(lockfile_path):
                    os.remove(lockfile_path)
                return True
            except Exception as e:
                logging.error(f"Could not stop process {pid}: {e}")
                return False
        return False

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
satellite           = sat_section.get('satellite', "auto")

def resolve_satellite(date_str: str, override_sat: Optional[str] = None) -> Tuple[str, str]:
    """
    Resolves the operational GOES satellite identifier ('G16' or 'G19') and AWS bucket name
    ('goes16' or 'goes19') based on the target observation date or an explicit CLI/config override.

    Operational Transition Timeline:
        - Prior to April 7, 2025: GOES-East is GOES-16 ('G16' / 'noaa-goes16').
        - From April 7, 2025 onwards: GOES-East is GOES-19 ('G19' / 'noaa-goes19').

    Args:
        date_str (str): Target observation date in 'YYYYMMDD' format.
        override_sat (Optional[str], optional): Explicit satellite code ('G16', 'G19', 'auto', etc.). Defaults to None.

    Returns:
        Tuple[str, str]: (satellite_code, goes_download_name), e.g. ('G16', 'goes16') or ('G19', 'goes19').
    """
    sat_cand = override_sat if override_sat is not None else _cfg_get('satellite', 'satellite', default='auto')
    sat_str = str(sat_cand).strip()

    if sat_str.lower() != 'auto':
        sat_upper = sat_str.upper()
        if sat_upper.startswith('G'):
            dsat = 'goes' + sat_upper[1:]
            return sat_upper, dsat.lower()
        if sat_str.lower().startswith('goes'):
            code = 'G' + sat_str.lower().replace('goes', '')
            return code, sat_str.lower()
        return sat_upper, sat_str.lower()

    # Automatic temporal resolution based on GOES-East operational transition (April 7, 2025)
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        if dt < datetime(2025, 4, 7):
            return "G16", "goes16"
        else:
            return "G19", "goes19"
    except Exception:
        return "G19", "goes19"

# Globales
dsatellite = satellite.replace('G','goes') if satellite != 'auto' else 'goes19'
ncFile = None
fechas_julianas = []


def R2BT(radiance: np.ndarray, channel: str, coeffs: Optional[dict] = None) -> np.ndarray:
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
        coeffs (Optional[dict], optional): Sensor Planck coefficients dictionary.

    Returns:
        np.ndarray: Calibrated Brightness Temperature array in degrees Celsius (°C).

    Raises:
        KeyError: If the specified channel is not a supported thermal infrared band.
    """
    BT_COEFFS = {
        'C07': {'fk1': 200248.0,  'fk2': 3685.87,  'bc1': 0.48985, 'bc2': 0.99931},
        'C08': {'fk1': 50451.5,   'fk2': 2327.96,  'bc1': 1.71389, 'bc2': 0.99631},
        'C09': {'fk1': 35620.4,   'fk2': 2072.92,  'bc1': 0.29884, 'bc2': 0.99929},
        'C10': {'fk1': 30210.0,   'fk2': 1962.16,  'bc1': 0.05458, 'bc2': 0.99986},
        'C11': {'fk1': 19441.3,   'fk2': 1694.05,  'bc1': 0.13691, 'bc2': 0.99962},
        'C12': {'fk1': 13519.8,   'fk2': 1500.86,  'bc1': 0.09101, 'bc2': 0.99971},
        'C13': {'fk1': 10860.4,   'fk2': 1395.19,  'bc1': 0.07481, 'bc2': 0.99975},
        'C14': {'fk1': 8500.63,   'fk2': 1285.78,  'bc1': 0.21051, 'bc2': 0.99925},
        'C15': {'fk1': 6489.46,   'fk2': 1175.13,  'bc1': 0.22448, 'bc2': 0.99913},
        'C16': {'fk1': 5084.62,   'fk2': 1083.35,  'bc1': 0.06004, 'bc2': 0.99975},
    }

    if coeffs is None:
        coeffs = BT_COEFFS[channel]
    fk1 = coeffs['fk1']
    fk2 = coeffs['fk2']
    bc1 = coeffs['bc1']
    bc2 = coeffs['bc2']

    rad_valid = np.maximum(radiance, 1e-4) if np is not None else radiance
    T = (fk2 / (np.log((fk1 / rad_valid) + 1)) - bc1) / bc2
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

def R2RT(
    radiance: np.ndarray,
    channel: str,
    d2: float = 1.0,
    day_julian: Optional[int] = None
) -> np.ndarray:
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
        d2 (float, optional): Normalized Sun-Earth distance squared. Defaults to 1.0.
        day_julian (Optional[int], optional): Day of year for exact astronomical distance.

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

    if channel not in Esun:
        raise ValueError(f"Constante Esun no definida para el canal {channel}")

    if day_julian is not None and np is not None:
        # Exact astronomical Earth-Sun distance squared
        d = 1.0 - 0.0167 * np.cos(2.0 * np.pi * (day_julian - 3) / 365.0)
        dist_sq = float(d ** 2)
    else:
        dist_sq = d2

    ref = (radiance * np.pi * dist_sq) / Esun[channel]
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
    for fecha in dates:
        fecha_dt = datetime.strptime(fecha, "%Y%m%d")
        fecha_juliana = fecha_dt.strftime("%j")
        if fecha_juliana not in fechas_julianas:
            fechas_julianas.append(fecha_juliana)

    for fecha in fechas_julianas:
        create_folder(os.path.join(basePath, config['paths']['input'], fecha), False)
        create_folder(os.path.join(basePath, config['paths']['output'], fecha), False)

def _progress_download_file(
    URL: str,
    name_file: str,
    path_out: str,
    retries: int = 10,
    backoff: float = 0.2,
    size_format: str = 'Decimal',
    show_download_progress: bool = True,
    overwrite_file: bool = False
) -> None:
    """
    Downloads a remote NetCDF file from NOAA S3, logging thread-safe percentage
    and a visual progress bar milestones for concurrent worker threads.

    Args:
        URL (str): Remote S3 HTTP/HTTPS URL.
        name_file (str): Output filename.
        path_out (str): Destination folder path.
        retries (int, optional): Connection retries. Defaults to 10.
        backoff (float, optional): Exponential backoff factor. Defaults to 0.2.
        size_format (str, optional): 'Decimal' (MB = 1e6 B) or 'Binary'. Defaults to 'Decimal'.
        show_download_progress (bool, optional): Kept for signature compatibility with GOES.download.
        overwrite_file (bool, optional): If True, redownloads existing files. Defaults to False.
    """
    if requests is None:
        raise RuntimeError("The 'requests' package is required for downloading satellite files.")

    ch_label = "CH"
    for tag in ("-M6C", "-M3C", "-M4C", "-C", "_M6C", "_M3C", "_M4C", "_C"):
        if tag in name_file:
            ch_label = "C" + name_file.split(tag)[1][:2]
            break

    session = requests.Session()
    if Retry is not None and HTTPAdapter is not None:
        retries_config = Retry(total=retries, backoff_factor=backoff, status_forcelist=[500, 502, 503, 504])
        session.mount('http://', HTTPAdapter(max_retries=retries_config))
        session.mount('https://', HTTPAdapter(max_retries=retries_config))

    full_target_path = os.path.join(path_out, name_file)
    req = session.get(URL, stream=True)
    content_length = req.headers.get('content-length')
    total_size = int(content_length) if content_length else 0
    dsize = 1000 * 1000 if size_format == 'Decimal' else 1024 * 1024

    if os.path.isfile(full_target_path) and not overwrite_file:
        if total_size > 0 and os.path.getsize(full_target_path) == total_size:
            logging.info(f"[{ch_label}] File already exists locally: {name_file}")
            return

    os.makedirs(path_out, exist_ok=True)
    downloaded = 0
    last_milestone = -1
    bar_width = 15

    total_mb_str = f"{total_size / dsize:.1f} MB" if total_size > 0 else "unknown size"
    logging.info(f"[{ch_label}] Ingesting {name_file} ({total_mb_str})...")

    with open(full_target_path, 'wb') as output_file:
        for chunk in req.iter_content(chunk_size=128 * 1024):
            if chunk:
                output_file.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    pct = (downloaded / total_size) * 100.0
                    milestone = int(pct // 10) * 10
                    if milestone > last_milestone and milestone in (10, 20, 30, 40, 50, 60, 70, 80, 90, 100):
                        filled = int(round(bar_width * downloaded / total_size))
                        bar_str = '=' * filled + (' ' * (bar_width - filled))
                        logging.info(
                            f"[{ch_label}] [{bar_str}] {pct:5.1f}% "
                            f"({downloaded / dsize:.1f}/{total_size / dsize:.1f} MB)"
                        )
                        last_milestone = milestone

    if total_size == 0 or last_milestone < 100:
        bar_str = '=' * bar_width
        logging.info(f"[{ch_label}] [{bar_str}] 100.0% ({downloaded / dsize:.1f} MB) - Download complete")

# Install progress tracking hook into GOES package if present
if GOES is not None:
    try:
        import GOES.downloads.download_data as _goes_dd
        _goes_dd.download_file = _progress_download_file
    except Exception as _hook_err:
        logging.debug(f"Could not hook GOES download_file: {_hook_err}")

def _download_channel_slot(
    ch: Union[str, int],
    date: str,
    hour: str,
    minute: str,
    dsat: str,
    output_dir: str
) -> List[str]:
    """
    Downloads or resolves a single GOES ABI spectral channel file for a specific observation slot.

    First verifies if a locally matching file already exists in output_dir (cache hit).
    If absent, queries NOAA AWS S3 via GOES.download with strict temporal boundaries.

    Args:
        ch (Union[str, int]): Spectral channel identifier (e.g. '01', 1, '13').
        date (str): Date in 'YYYYMMDD' format.
        hour (str): UTC hour in 'HH' format.
        minute (str): UTC minute in 'MM' format.
        dsat (str): GOES satellite string (e.g. 'goes19').
        output_dir (str): Destination directory for NetCDF files.

    Returns:
        List[str]: List of resolved local NetCDF file paths (empty list if download failed).
    """
    ch_str = f"{int(ch):02d}"
    fecha_dt = datetime.strptime(date, "%Y%m%d")
    fecha_hora = datetime.strptime(f"{date}-{hour}{minute}00", '%Y%m%d-%H%M%S')
    nueva_fecha_hora = min(
        fecha_hora + timedelta(minutes=5),
        fecha_hora.replace(minute=55, second=0)
    )
    dateend = nueva_fecha_hora.strftime('%Y%m%d-%H%M00')
    prefix_match = f"s{fecha_dt.strftime('%Y%j')}{hour}{minute}"
    ch_tag = f"C{ch_str}"

    # 1. Local cache hit check (avoids redundant S3 queries)
    if os.path.exists(output_dir):
        existing = [
            os.path.join(output_dir, f) for f in os.listdir(output_dir)
            if f.endswith('.nc') and prefix_match in f and ch_tag in f
        ]
        if existing:
            logging.info(
                f"[Cache Hit] Channel {ch_str} already exists locally: {os.path.basename(existing[0])}"
            )
            return existing

    # 2. Query and download from NOAA S3 via GOES
    flist = []
    if GOES is not None:
        max_query_attempts = 3
        for attempt in range(1, max_query_attempts + 1):
            try:
                flist = GOES.download(
                    dsat,
                    'ABI-L1b-RadF',
                    DateTimeIni=f"{date}-{hour}{minute}00",
                    DateTimeFin=dateend,
                    channel=[ch_str],
                    path_out=output_dir,
                    show_download_progress=False
                )
                if flist:
                    break
            except FileNotFoundError as fnf_err:
                logging.warning(f"S3 remote directory not found for channel {ch_str} ({date} {hour}:{minute} UTC): {fnf_err}")
                break
            except Exception as dl_err:
                if attempt < max_query_attempts:
                    logging.debug(f"[Retry {attempt}/{max_query_attempts}] Querying S3 for channel {ch_str}: {dl_err}")
                    time.sleep(1.5)
                else:
                    logging.warning(f"Error querying GOES data for channel {ch_str} ({date} {hour}:{minute} UTC): {dl_err}")

    if flist:
        return flist

    # 3. Fallback disk check in case file was saved without returning path
    if os.path.exists(output_dir):
        existing = [
            os.path.join(output_dir, f) for f in os.listdir(output_dir)
            if f.endswith('.nc') and prefix_match in f and ch_tag in f
        ]
        if existing:
            return existing

    return []

def _build_download_tasks(
    dates: List[str],
    hours: List[str],
    minutes: List[str],
    satellite_override: Optional[str] = None,
    target_channels: Optional[List[str]] = None
) -> List[tuple]:
    """
    Constructs the sequence of download task specifications for each channel and timestamp,
    dynamically resolving the operational satellite (G16 vs G19) for each target date.

    Args:
        dates (List[str]): List of observation dates in 'YYYYMMDD' format.
        hours (List[str]): List of UTC hours in 'HH' format.
        minutes (List[str]): List of UTC minutes in 'MM' format.
        satellite_override (Optional[str], optional): Explicit satellite identifier. Defaults to None.
        target_channels (Optional[List[str]], optional): Subset of spectral channels. Defaults to None.

    Returns:
        List[tuple]: List of task parameter tuples (ch, date, hour, minute, dsat, output_dir).
    """
    tasks = []
    active_chs = target_channels if target_channels is not None else channels
    for date in dates:
        sat_code, dsat = resolve_satellite(date, satellite_override)
        fecha_dt = datetime.strptime(date, "%Y%m%d")
        fecha_juliana = fecha_dt.strftime("%j")
        output = os.path.join(basePath, config['paths']['input'], fecha_juliana).rstrip(os.sep) + os.sep
        for hour in hours:
            for minute in minutes:
                for ch in active_chs:
                    tasks.append((ch, date, hour, minute, dsat, output))
    return tasks

def download_and_pipeline(
    dates: List[str],
    hours: List[str],
    minutes: List[str],
    on_file_ready: Optional[Callable[[str], None]] = None,
    satellite: Optional[str] = None,
    target_channels: Optional[List[str]] = None
) -> List[str]:
    """
    Concurrent multi-threaded downloader with asynchronous producer-consumer pipelining.

    Retrieves requested GOES spectral channels in parallel using ThreadPoolExecutor.
    If on_file_ready is provided and pipeline overlap is enabled in config.yaml, completed
    files are immediately dispatched to on_file_ready (e.g. processImage) so network I/O
    and CPU image rendering overlap seamlessly.

    Args:
        dates (List[str]): List of target observation dates in 'YYYYMMDD' format.
        hours (List[str]): List of UTC target hours in 'HH' format (00-23).
        minutes (List[str]): List of target minutes in 'MM' format (00-59).
        on_file_ready (Optional[Callable[[str], None]], optional): Callback executed as soon
            as an individual NetCDF file is ready on disk. Defaults to None.
        satellite (Optional[str], optional): Explicit satellite override (G16, G19, auto). Defaults to None.

    Returns:
        List[str]: Complete list of all downloaded or resolved NetCDF file paths.
    """
    max_workers_cfg = _cfg_get('performance', 'max_download_workers', default=4)
    try:
        max_workers = int(max_workers_cfg) if max_workers_cfg else 4
    except (ValueError, TypeError):
        max_workers = 4

    overlap_cfg = _cfg_get('performance', 'enable_pipeline_overlap', default=True)
    enable_overlap = bool(overlap_cfg) if overlap_cfg is not None else True

    tasks = _build_download_tasks(dates, hours, minutes, satellite_override=satellite, target_channels=target_channels)
    if not tasks:
        return []

    fulllist = []
    pool_workers = min(max_workers, len(tasks))
    active_chs_len = len(target_channels) if target_channels is not None else len(channels)
    logging.info(
        f"Starting download of {len(tasks)} file(s) across {active_chs_len} channel(s) "
        f"with {pool_workers} concurrent worker(s) (overlap={enable_overlap})."
    )

    futures_map = {}
    with ThreadPoolExecutor(max_workers=pool_workers) as executor:
        for ch, date, hour, minute, dsat, output_dir in tasks:
            fut = executor.submit(_download_channel_slot, ch, date, hour, minute, dsat, output_dir)
            futures_map[fut] = (ch, date, hour, minute)

        for fut in as_completed(futures_map):
            ch, date, hour, minute = futures_map[fut]
            try:
                files = fut.result()
                if files:
                    for aFile in files:
                        fulllist.append(aFile)
                        if enable_overlap and on_file_ready is not None:
                            try:
                                on_file_ready(aFile)
                            except Exception as proc_err:
                                logging.error(f"Error processing file {aFile} in pipeline: {proc_err}")
            except Exception as err:
                logging.error(f"Download task failed for Channel {ch} ({date} {hour}:{minute}): {err}")

    return fulllist

def download(
    dates: List[str],
    hours: List[str],
    minutes: List[str],
    satellite: Optional[str] = None,
    target_channels: Optional[List[str]] = None
) -> List[str]:
    """
    Retrieves NOAA GOES Level 1b Radiance (ABI-L1b-RadF) NetCDF files from AWS S3.

    Wrapper over download_and_pipeline maintaining backward compatibility for legacy callers.

    Args:
        dates (List[str]): List of target observation dates in 'YYYYMMDD' format.
        hours (List[str]): List of UTC target hours in 'HH' format (00-23).
        minutes (List[str]): List of target minutes in 'MM' format (00-59).
        satellite (Optional[str], optional): Explicit satellite identifier (G16, G19, auto). Defaults to None.
        target_channels (Optional[List[str]], optional): Target channel subset. Defaults to None.

    Returns:
        List[str]: List of filesystem paths to the downloaded or resolved NetCDF files.
    """
    kwargs = {"on_file_ready": None}
    if satellite is not None:
        kwargs["satellite"] = satellite
    if target_channels is not None:
        kwargs["target_channels"] = target_channels
    return download_and_pipeline(dates, hours, minutes, **kwargs)                

def auto_date(
    source: str,
    label: bool = False,
    watermark: Optional[str] = None,
    overwrite: bool = False,
    family: Optional[str] = None,
    borders: bool = True,
    max_dim: Optional[int] = None,
    satellite: Optional[str] = None,
    target_channels: Optional[List[str]] = None
) -> None:
    """
    Executes near-real-time automated observation retrieval and product generation.

    Args:
        source (str): Satellite data source identifier ('aws' or 'ideam').
        label (bool, optional): If True, renders title bar, colorbar, and metadata. Defaults to False.
        watermark (Optional[str], optional): Custom institution or attribution watermark. Defaults to None.
        overwrite (bool, optional): If True, forces product re-generation. Defaults to False.
        family (Optional[str], optional): Colormap enhancement family ('default' or 'noaa'). Defaults to None.
        borders (bool, optional): If True, draws administrative borders / croquis. Defaults to True.
        max_dim (Optional[int], optional): Max pixel dimension or 0 for uncompressed native. Defaults to None.
        satellite (Optional[str], optional): Explicit satellite override (G16, G19, auto). Defaults to None.
        target_channels (Optional[List[str]], optional): Target channel subset. Defaults to None.
    """
    logging.info("Automated generation mode started")
    if source == 'aws':
        source_AWS(label, watermark=watermark, overwrite=overwrite, family=family, borders=borders, max_dim=max_dim, satellite=satellite, target_channels=target_channels)
    elif source == "ideam":
        source_IDEAM(label, watermark=watermark, overwrite=overwrite, family=family, borders=borders, max_dim=max_dim)
    else:
        logging.error(f"Unknown data source: {source}. Supported: aws | ideam")

def run_daemon_loop(
    source: str,
    interval_minutes: int = 10,
    label: bool = False,
    watermark: Optional[str] = None,
    overwrite: bool = False,
    family: Optional[str] = None,
    borders: bool = True,
    max_dim: Optional[int] = None,
    satellite: Optional[str] = None,
    target_channels: Optional[List[str]] = None
) -> None:
    """
    Runs a continuous, non-overlapping automation daemon loop.
    Executes sequentially on every observation interval, calculating the exact wait time
    until the next NOAA satellite scan is published.
    """
    logging.info(
        f"[Daemon Started] Running automated observation scheduler every {interval_minutes}m "
        f"(source: {source}, channels: {target_channels or 'configured'})."
    )
    while True:
        cycle_start = time.time()
        logging.info("[Daemon Cycle] Starting scheduled observation download & processing...")
        try:
            if source == 'aws':
                source_AWS(
                    label=label,
                    watermark=watermark,
                    overwrite=overwrite,
                    family=family,
                    borders=borders,
                    max_dim=max_dim,
                    satellite=satellite,
                    target_channels=target_channels
                )
            elif source == 'ideam':
                source_IDEAM(
                    label=label,
                    watermark=watermark,
                    overwrite=overwrite,
                    family=family,
                    borders=borders,
                    max_dim=max_dim
                )
        except Exception as e:
            logging.error(f"[Daemon Cycle Error] Exception during generation: {e}")

        # NOAA publishes Full Disk scans ~2-3 min after scan start.
        now = time.time()
        sec_in_block = now % (interval_minutes * 60)
        # Target :03, :13, :23, :33, :43, :53 UTC
        delay = (interval_minutes * 60) - sec_in_block + 180
        if delay > (interval_minutes * 60):
            delay -= (interval_minutes * 60)
        if delay < 30:
            delay += (interval_minutes * 60)

        next_run_dt = datetime.now() + timedelta(seconds=delay)
        elapsed = time.time() - cycle_start
        logging.info(
            f"[Daemon Cycle Done] Execution took {elapsed:.1f}s. "
            f"Sleeping {delay:.0f}s until next satellite slot ({next_run_dt.strftime('%H:%M:%S')})..."
        )
        time.sleep(delay)

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

def source_IDEAM(
    label: bool = False,
    watermark: Optional[str] = None,
    overwrite: bool = False,
    family: Optional[str] = None,
    borders: bool = True,
    max_dim: Optional[int] = None
) -> None:
    """
    Scrapes and retrieves the most recent Level 1b imagery from the IDEAM regional HTTP archive.

    Args:
        label (bool, optional): If True, renders metadata, colorbar, and title banner. Defaults to False.
        watermark (Optional[str], optional): Custom watermark or attribution string. Defaults to None.
        overwrite (bool, optional): If True, forces product re-generation. Defaults to False.
        family (Optional[str], optional): Colormap enhancement family ('default' or 'noaa'). Defaults to None.
        borders (bool, optional): If True, draws administrative borders / croquis. Defaults to True.
        max_dim (Optional[int], optional): Max pixel dimension or 0 for uncompressed native. Defaults to None.
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
        processImage(aFile, label=label, watermark=watermark, overwrite=overwrite, family=family, borders=borders, max_dim=max_dim)
    
    write_latest_downloaded(ultima_descarga)

def source_AWS(
    label: bool = False,
    watermark: Optional[str] = None,
    overwrite: bool = False,
    family: Optional[str] = None,
    borders: bool = True,
    max_dim: Optional[int] = None,
    satellite: Optional[str] = None,
    target_channels: Optional[List[str]] = None
) -> None:
    """
    Retrieves and processes the most recent GOES observation slot from NOAA's public AWS S3 bucket.

    Computes the timestamp of the latest available 10-minute scan, creates required directories,
    downloads the active spectral channels, and triggers image/raster production.

    Args:
        label (bool, optional): If True, renders metadata, colorbar, and title banner. Defaults to False.
        watermark (Optional[str], optional): Custom watermark or attribution string. Defaults to None.
        overwrite (bool, optional): If True, forces product re-generation. Defaults to False.
        family (Optional[str], optional): Colormap enhancement family ('default' or 'noaa'). Defaults to None.
        borders (bool, optional): If True, draws administrative borders / croquis. Defaults to True.
        max_dim (Optional[int], optional): Max pixel dimension or 0 for uncompressed native. Defaults to None.
        satellite (Optional[str], optional): Explicit satellite identifier (G16, G19, auto). Defaults to None.
        target_channels (Optional[List[str]], optional): Target channel subset. Defaults to None.
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

    overlap_cfg = _cfg_get('performance', 'enable_pipeline_overlap', default=True)
    enable_overlap = bool(overlap_cfg) if overlap_cfg is not None else True

    if enable_overlap:
        flist = download_and_pipeline(
            dates, hours, minutes,
            on_file_ready=lambda f: processImage(
                f, label=label, watermark=watermark, overwrite=overwrite, family=family, borders=borders, max_dim=max_dim
            ),
            satellite=satellite,
            target_channels=target_channels
        )
    else:
        flist = download(dates, hours, minutes, satellite=satellite, target_channels=target_channels)
        if flist:
            for aFile in flist:
                processImage(aFile, label=label, watermark=watermark, overwrite=overwrite, family=family, borders=borders, max_dim=max_dim)

    if not flist:
        logging.warning("No files were downloaded. The requested scan may not yet be published on NOAA S3.")
        return

def manual_date(
    dates: List[str],
    hours: List[str],
    minutes: List[str],
    lat: Optional[Union[float, List[float]]] = None,
    lon: Optional[Union[float, List[float]]] = None,
    label: bool = False,
    bullseye: bool = True,
    watermark: Optional[str] = None,
    overwrite: bool = False,
    family: Optional[str] = None,
    borders: bool = True,
    max_dim: Optional[int] = None,
    satellite: Optional[str] = None,
    target_channels: Optional[List[str]] = None
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
        overwrite (bool, optional): If True, forces product re-generation. Defaults to False.
        family (Optional[str], optional): Colormap enhancement family ('default' or 'noaa'). Defaults to None.
        borders (bool, optional): If True, draws administrative borders / croquis. Defaults to True.
        max_dim (Optional[int], optional): Max pixel dimension or 0 for uncompressed native. Defaults to None.
        satellite (Optional[str], optional): Explicit satellite identifier (G16, G19, auto). Defaults to None.
        target_channels (Optional[List[str]], optional): Target channel subset. Defaults to None.
    """
    prepare_folders(dates)

    overlap_cfg = _cfg_get('performance', 'enable_pipeline_overlap', default=True)
    enable_overlap = bool(overlap_cfg) if overlap_cfg is not None else True

    if enable_overlap:
        flist = download_and_pipeline(
            dates, hours, minutes,
            on_file_ready=lambda f: processImage(
                f, lat=lat, lon=lon, label=label, bullseye=bullseye, watermark=watermark, overwrite=overwrite, family=family, borders=borders, max_dim=max_dim
            ),
            satellite=satellite,
            target_channels=target_channels
        )
    else:
        flist = download(dates, hours, minutes, satellite=satellite, target_channels=target_channels)
        if flist:
            for aFile in flist:
                processImage(
                    aFile, lat, lon, label=label, bullseye=bullseye, watermark=watermark, overwrite=overwrite, family=family, borders=borders, max_dim=max_dim
                )

    if not flist:
        logging.warning("No files were downloaded for the specified dates and times.")
        return

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

def resolve_colormap_and_limits(
    band: int,
    family: Optional[str] = None,
    base_path: str = ""
) -> Tuple[Any, float, float]:
    """
    Resolves the colormap and physical dynamic range [clim_min, clim_max] for a given ABI band
    based on the configured enhancement family ('default' or 'noaa').

    Priority lookup:
    1. If family is specified (e.g. 'noaa' or 'default'):
       - Checks `app/colors/{family}/ch{band:02d}.cpt`
       - Checks `app/colors/ch{band:02d}_{family}.cpt`
    2. Fallback to root `app/colors/ch{band:02d}.cpt`
    3. Legacy fallback (colors.rainbow for C13, WV_red_black for C08-10, grey255 for C01-06, etc.)

    Args:
        band (int): Spectral channel number (1 to 16).
        family (Optional[str], optional): Enhancement family identifier. Defaults to None.
        base_path (str, optional): Base project directory path. Defaults to "".

    Returns:
        Tuple[Any, float, float]: (colormap, clim_min, clim_max)
    """
    if family is None:
        family = _cfg_get('colors', 'family', 'enhancement_family', default='default')
    norm_family = str(family).strip().lower()
    c16_color_enabled = bool(_cfg_get('colors', 'c16_color_enhanced', 'c16_enhanced', default=False))

    # Dynamic limits per family
    if norm_family == 'noaa':
        if band <= 6:
            clim_min, clim_max = 0.0, 1.0
        elif band == 7:
            clim_min, clim_max = -90.0, 130.0
        elif 8 <= band <= 10:
            clim_min, clim_max = -90.0, 20.0
        elif 11 <= band <= 15:
            clim_min, clim_max = -110.0, 55.0
        else:  # Band 16
            if c16_color_enabled:
                clim_min, clim_max = -110.0, 55.0
            else:
                clim_min, clim_max = -120.0, 50.0
    else:
        # Default family limits
        if band <= 6:
            clim_min, clim_max = 0.0, 1.0
        elif band == 7:
            clim_min, clim_max = -90.0, 130.0
        elif 8 <= band <= 10:
            clim_min, clim_max = -85.0, -30.0
        else:
            clim_min, clim_max = -90.0, 50.0

    colors_dir = os.path.join(base_path, config['paths']['colors'])

    # Default family preservation for Band 13: Oklahoma Convective Rainbow
    if norm_family == 'default' and band == 13 and colors and hasattr(colors, 'rainbow'):
        return colors.rainbow, clim_min, clim_max

    # Priority lookup candidates
    candidates = []
    if band == 16 and c16_color_enabled:
        candidates.extend([
            os.path.join(colors_dir, norm_family, "ch16_bd.cpt"),
            os.path.join(colors_dir, "ch16_bd.cpt"),
            os.path.join(colors_dir, norm_family, "ch13.cpt"),
        ])
    candidates.extend([
        os.path.join(colors_dir, norm_family, f"ch{band:02d}.cpt"),
        os.path.join(colors_dir, f"ch{band:02d}_{norm_family}.cpt"),
        os.path.join(colors_dir, f"ch{band:02d}.cpt"),
    ])

    for cand in candidates:
        if os.path.exists(cand):
            cpt_dict = loadCPT(cand)
            if cpt_dict is not None and LinearSegmentedColormap is not None:
                cpt_cmap = LinearSegmentedColormap(f'cpt_ch{band:02d}_{norm_family}', cpt_dict)
                # In default family, WV palettes (8-10) were historically inverted
                if norm_family != 'noaa' and 8 <= band <= 10:
                    cpt_cmap = cpt_cmap.reversed()
                return cpt_cmap, clim_min, clim_max

    # Legacy fallbacks
    cmap = None
    if band <= 6:
        cpt = loadCPT(os.path.join(colors_dir, "grey255.cpt"))
        cmap = LinearSegmentedColormap('cpt', cpt) if (cpt and LinearSegmentedColormap) else 'gray'
    elif band == 7:
        cpt = loadCPT(os.path.join(colors_dir, "thermal.cpt"))
        cmap = LinearSegmentedColormap('cpt', cpt) if (cpt and LinearSegmentedColormap) else 'inferno'
    elif 8 <= band <= 10:
        cpt = loadCPT(os.path.join(colors_dir, "WV_red_black.cpt"))
        cmap = LinearSegmentedColormap('cpt', cpt).reversed() if (cpt and LinearSegmentedColormap) else 'viridis'
    elif band == 13:
        cmap = colors.rainbow if (colors and hasattr(colors, 'rainbow')) else 'rainbow'
    else:
        cmap = colors.rainbow if (colors and hasattr(colors, 'rainbow')) else 'rainbow'

    return cmap, clim_min, clim_max

def processImage(
    aFile: str,
    lat: Optional[Union[float, List[float]]] = None,
    lon: Optional[Union[float, List[float]]] = None,
    label: bool = False,
    bullseye: bool = True,
    watermark: Optional[str] = None,
    overwrite: bool = False,
    family: Optional[str] = None,
    borders: bool = True,
    max_dim: Optional[int] = None
) -> None:
    """
    Executes the scientific cartographic and raster processing pipeline for a GOES ABI NetCDF file.

    Workflow:
        1. Output Cache Validation: Checks if rendered products (.png, .tif) already exist,
           skipping CPU-intensive remapping when overwrite=False.
        2. Metadata Extraction: Parses observation timestamp, spatial resolution, and band properties.
        3. Geostationary Reprojection: Remaps raw geostationary perspective grid to Equirectangular (WGS84).
        4. Physical Calibration: Inverts Planck function for thermal IR or computes gamma-enhanced solar reflectance.
        5. Dynamic Memory Bounding: Constrains maximum dimensions via Lanczos spatial resampling.
        6. Vector Overlays: Renders national borders, department boundaries, waypoints, and range rings.
        7. Cartographic Publishing:
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
        overwrite (bool, optional): If True, re-renders products even if they exist. Defaults to False.
        family (Optional[str], optional): Colormap enhancement family ('default' or 'noaa'). Defaults to None.
        borders (bool, optional): If True, draws administrative borders / croquis. Defaults to True.
        max_dim (Optional[int], optional): Max pixel dimension or 0 for uncompressed native. Defaults to None.

    Returns:
        None
    """
    if matplotlib is not None:
        matplotlib.rcParams['figure.dpi'] = 100

    Start = (aFile[aFile.find("_s")+2:aFile.find("_e")])

    Band = get_band(aFile, True)
    BandString = get_band(aFile, False)
    if Band is None or BandString is None:
        logging.warning("No se pudo identificar la banda para el archivo %s", aFile)
        return

    Wavelenghts = ['[]', '[0.47 μm]', '[0.64 μm]', '[0.865 μm]', '[1.378 μm]', '[1.61 μm]', '[2.25 μm]', '[3.90 μm]', '[6.19 μm]', '[6.95 μm]', '[7.34 μm]', '[8.50 μm]', '[9.61 μm]', '[10.35 μm]', '[11.20 μm]', '[12.30 μm]', '[13.30 μm]']

    year = int(Start[0:4])
    dayjulian = int(Start[4:7])
    dayjulianstring = Start[4:7]
    hour = Start[7:9]
    minute = Start[9:11]

    dayconventional = datetime(int(year), 1, 1) + timedelta(days=int(dayjulian) - 1)
    timestamp_str = f"{dayconventional.strftime('%Y%m%d')}{hour}{minute}"

    outFolder = os.path.join(basePath, config['paths']['output'], dayjulianstring, "C" + BandString)
    expected_image_out = os.path.join(outFolder, f"{timestamp_str}.png")
    expected_tif_out = os.path.join(outFolder, f"{timestamp_str}.tif")

    # Fast output cache check: skip remapping and rendering if products already exist
    if not overwrite and os.path.exists(expected_image_out):
        if not generateTiff or os.path.exists(expected_tif_out):
            latest_folder = os.path.join(basePath, "latest")
            latest_png = os.path.join(latest_folder, f"latestC{BandString}.png")
            latest_pgw = os.path.join(latest_folder, f"latestC{BandString}.pgw")
            expected_pgw_out = os.path.join(outFolder, f"{timestamp_str}.pgw")
            create_folder(latest_folder)
            try:
                shutil.copyfile(expected_image_out, latest_png)
                if os.path.exists(expected_pgw_out):
                    shutil.copyfile(expected_pgw_out, latest_pgw)
            except Exception as e:
                logging.debug("Could not copy cached image to latest: %s", e)
            logging.info(
                f"[Cache Hit] Image products already exist for Channel {BandString} "
                f"({timestamp_str}.png). Skipping remapping and rendering."
            )
            return

    date = dayconventional.strftime('%d-%b-%Y')
    time = Start[7:9] + ":" + Start[9:11] + " UTC"

    if Band <= 6:
        Unit = "Reflectance"
    else:
        Unit = "Brightness Temperature [°C]"

    file_sat = dsatellite.upper().replace("GOES", "GOES-")
    a_base = os.path.basename(aFile).upper()
    if "_G16_" in a_base or "_G16." in a_base or "GOES16" in a_base:
        file_sat = "GOES-16"
    elif "_G19_" in a_base or "_G19." in a_base or "GOES19" in a_base:
        file_sat = "GOES-19"
    elif "_G18_" in a_base or "GOES18" in a_base:
        file_sat = "GOES-18"
    elif "_G17_" in a_base or "GOES17" in a_base:
        file_sat = "GOES-17"

    Title = file_sat + " Band " + str(Band) + " " + Wavelenghts[int(Band)] + " " + Unit + " " + date + "  " + time
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

    target_max_dim = max_dim if max_dim is not None else int(_cfg_get('plotting', 'max_dimension', 'max_dim', default=2048))
    if target_max_dim > 0 and (data.shape[1] > target_max_dim or data.shape[0] > target_max_dim):
        scale = min(target_max_dim / data.shape[1], target_max_dim / data.shape[0])
        new_width = int(data.shape[1] * scale)
        new_height = int(data.shape[0] * scale)
        #print(f"Resizing data from {data.shape} to ({new_height}, {new_width})")
        resample_filter = getattr(getattr(Image, 'Resampling', None), 'LANCZOS', getattr(Image, 'LANCZOS', Image.BILINEAR))
        data = np.array(Image.fromarray(data.astype(np.float32)).resize((new_width, new_height), resample_filter))
    #print(f"Adjusted data shape: {data.shape}")

    planck_coeffs = None
    if 'planck_fk1' in ncImage.variables:
        try:
            planck_coeffs = {
                'fk1': float(ncImage.variables['planck_fk1'][:]),
                'fk2': float(ncImage.variables['planck_fk2'][:]),
                'bc1': float(ncImage.variables['planck_bc1'][:]),
                'bc2': float(ncImage.variables['planck_bc2'][:]),
            }
        except Exception:
            planck_coeffs = None

    norm_family = str(family if family is not None else _cfg_get('colors', 'family', 'enhancement_family', default='default')).strip().lower()

    channel_str = f"C{Band:02d}"
    if Band <= 6:
        data = R2RT(data, channel_str, day_julian=dayjulian)
    elif 8 <= Band <= 10:
        if norm_family == 'default':
            data = R2BT_WV_visual(data, channel_str)
        else:
            data = R2BT(data, channel_str, coeffs=planck_coeffs)
    else:
        data = R2BT(data, channel_str, coeffs=planck_coeffs)

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
    cpt_cmap, clim_min, clim_max = resolve_colormap_and_limits(Band, family=family, base_path=basePath)
    im.set_cmap(cpt_cmap)
    im.set_clim(clim_min, clim_max)

    ax.set_xlim(0, data.shape[1])
    ax.set_ylim(0, data.shape[0])

    def lonlat_to_norm(lon, lat, extent, data_shape):
        lon_range = extent[2] - extent[0]
        lat_range = extent[3] - extent[1]
        x_norm = (lon - extent[0]) / lon_range * data_shape[1]
        y_norm = (lat - extent[1]) / lat_range * data_shape[0]
        return x_norm, y_norm

    draw_borders = borders and bool(_cfg_get('plotting', 'show_borders', default=True))
    draw_departments = draw_borders and bool(_cfg_get('plotting', 'show_departments', default=True))
    draw_countries = draw_borders and bool(_cfg_get('plotting', 'show_countries', default=True))

    if draw_departments:
        dpto_shape = _cfg_get('shapes', 'departments', 'departamentos', default='MGN_DPTO_POLITICO')
        dpto_layer = _cfg_get('shapes', 'departments_layer', 'departamentos_layer', default='MGN_DPTO_POLITICO')
        shapefile_path = os.path.join(basePath, config['paths']['shapes'], dpto_shape)
        try:
            bmap.readshapefile(shapefile_path, dpto_layer, drawbounds=False)
            for shape in getattr(bmap, dpto_layer, []):
                x = [point[0] for point in shape]
                y = [point[1] for point in shape]
                x_norm = [(lon_pt - extent[0]) / (extent[2] - extent[0]) * data.shape[1] for lon_pt in x]
                y_norm = [(lat_pt - extent[1]) / (extent[3] - extent[1]) * data.shape[0] for lat_pt in y]
                ax.plot(x_norm, y_norm, color='white', linewidth=0.6, zorder=2)
        except Exception as e:
            logging.debug("Could not plot department shapefile: %s", e)

    if draw_countries:
        country_shape = _cfg_get('shapes', 'countries', 'paises', default='ne_10m_admin_0_countries/ne_10m_admin_0_countries')
        country_layer = _cfg_get('shapes', 'countries_layer', 'paises_layer', default='countries')
        country_shapefile_path = os.path.join(basePath, config['paths']['shapes'], country_shape)
        try:
            bmap.readshapefile(country_shapefile_path, country_layer, drawbounds=False)
            for shape in getattr(bmap, country_layer, []):
                x = [point[0] for point in shape]
                y = [point[1] for point in shape]
                x_norm = [(lon_pt - extent[0]) / (extent[2] - extent[0]) * data.shape[1] for lon_pt in x]
                y_norm = [(lat_pt - extent[1]) / (extent[3] - extent[1]) * data.shape[0] for lat_pt in y]
                ax.plot(x_norm, y_norm, color='white', linewidth=0.6, zorder=2)
        except Exception as e:
            logging.debug("Could not plot countries shapefile: %s", e)

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
    plt.close(fig)

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
        required=False,
        default=None,
        help='Execution mode: auto | manual'
    )
    parser.add_argument(
        '--source', '--fuente',
        dest='source',
        type=str,
        required=False,
        default='aws',
        help='Data source: aws | ideam (default: aws)'
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
    parser.add_argument(
        '--overwrite', '--force',
        dest='overwrite',
        type=lambda x: str(x).lower() in ('true', '1', 'yes'),
        default=bool(_cfg_get('general', 'overwrite', 'overwrite_images', default=False)),
        help='Force re-generation of products even if they already exist in output/ (True/False)'
    )
    parser.add_argument(
        '--family', '--palette', '--enhancement',
        dest='family',
        type=str,
        default=str(_cfg_get('colors', 'family', 'enhancement_family', default='default')),
        help="Colormap enhancement family ('default' or 'noaa'). Defaults to 'default'."
    )
    parser.add_argument(
        '--c16-enhanced', '--c16-color',
        dest='c16_enhanced',
        type=lambda x: str(x).lower() in ('true', '1', 'yes'),
        default=bool(_cfg_get('colors', 'c16_color_enhanced', 'c16_enhanced', default=False)),
        help='Display Band 16 (CO2) with convective color enhancement instead of grayscale (True/False)'
    )
    parser.add_argument(
        '--borders', '--croquis',
        dest='borders',
        type=lambda x: str(x).lower() in ('true', '1', 'yes'),
        default=bool(_cfg_get('plotting', 'show_borders', default=True)),
        help='Draw vector administrative boundaries (departments and countries / croquis) (True/False)'
    )
    parser.add_argument(
        '--max-dim', '--resolution-px',
        dest='max_dim',
        type=int,
        default=None,
        help='Max pixel dimension for output image (e.g. 1024, 2048, 4096, or 0 for native resolution). Defaults to config value.'
    )
    parser.add_argument(
        '--satellite', '--sat',
        dest='satellite',
        type=str,
        default=None,
        help='Target GOES satellite (G16, G19, or auto). Defaults to auto (G16 before April 7, 2025, G19 after).'
    )
    parser.add_argument(
        '--channels', '--canales',
        dest='channels',
        type=str,
        default=None,
        help='Target ABI channel(s) comma-separated (e.g. 02,08,13 or C02,C08,C13). Defaults to configured channels in config.yaml.'
    )
    parser.add_argument(
        '--daemon',
        dest='daemon',
        action='store_true',
        default=False,
        help='Run in persistent daemon mode, executing observation cycles every N minutes without termination.'
    )
    parser.add_argument(
        '--interval', '--intervalo',
        dest='interval',
        type=int,
        default=10,
        help='Cadence interval in minutes for daemon mode (default: 10).'
    )
    parser.add_argument(
        '--stop',
        dest='stop',
        action='store_true',
        default=False,
        help='Stop any active background pipeline daemon or process using the lockfile PID.'
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

    if args.stop:
        stopped = SingleInstanceLock.stop_running_instance()
        if stopped:
            logging.info("Pipeline daemon successfully stopped.")
            sys.exit(0)
        else:
            logging.warning("No active pipeline daemon was found running.")
            sys.exit(0)

    if not args.mode:
        logging.error("Execution mode (--mode or --tipo) is required. Use: auto | manual (or pass --stop to terminate a daemon)")
        parser.print_help()
        sys.exit(1)

    logging.info("Execution mode: %s", args.mode)

    target_channels = None
    if args.channels:
        try:
            target_channels = [f"{int(c.strip().lstrip('cC')):02d}" for c in args.channels.split(',') if c.strip()]
        except ValueError:
            logging.error("Invalid channel format in --channels. Must be numbers like 02,08,13 or C02,C08,C13.")
            sys.exit(1)

    lock = SingleInstanceLock()
    if not lock.acquire():
        logging.warning(
            "[Overlap Prevention] Another instance of the pipeline is currently running. "
            "Exiting gracefully to prevent duplicate downloads and resource contention."
        )
        sys.exit(0)

    try:
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
                    watermark=args.watermark,
                    overwrite=args.overwrite,
                    family=args.family,
                    borders=args.borders,
                    max_dim=args.max_dim,
                    satellite=args.satellite,
                    target_channels=target_channels
                )

        elif args.mode == "auto":
            if args.daemon:
                run_daemon_loop(
                    args.source,
                    interval_minutes=args.interval,
                    label=args.label,
                    watermark=args.watermark,
                    overwrite=args.overwrite,
                    family=args.family,
                    borders=args.borders,
                    max_dim=args.max_dim,
                    satellite=args.satellite,
                    target_channels=target_channels
                )
            else:
                auto_date(
                    args.source,
                    args.label,
                    watermark=args.watermark,
                    overwrite=args.overwrite,
                    family=args.family,
                    borders=args.borders,
                    max_dim=args.max_dim,
                    satellite=args.satellite,
                    target_channels=target_channels
                )

        else:
            logging.error('Unknown execution mode: %s. Use: manual | auto', args.mode)
            parser.print_help()
            sys.exit(1)
    finally:
        lock.release()    
# Punto de entrada del script
if __name__ == "__main__":
    main()
