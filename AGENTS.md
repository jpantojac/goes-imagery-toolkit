# 🤖 AI Agent Guidelines (AGENTS.md)

Este archivo proporciona contexto y directrices para los asistentes o agentes de Inteligencia Artificial que operen sobre el proyecto **GOES Imagery Toolkit** (`SatelliteProducts`). Su propósito es definir cómo el Agente debe interpretar las instrucciones en lenguaje natural y traducirlas a ejecuciones de código o scripts de forma autónoma y correcta.

## 1. Contexto y Sentido del Proyecto

**GOES Imagery Toolkit** es un pipeline de teledetección desarrollado para procesar, calibrar y visualizar imágenes satelitales provenientes de los satélites **GOES-16 y GOES-19** (NOAA ABI L1b). Las imágenes se descargan desde fuentes como AWS Open Data (S3 público de NOAA) o el repositorio regional del IDEAM y se procesan para producir:

- Imágenes PNG con diferentes paletas calibradas (escala de grises reflectiva, térmico, vapor de agua troposférico, etc.).
- Archivos georreferenciados ESRI Worldfile (`.pgw`) y rásteres GeoTIFF (`.tif`) para software GIS (QGIS, ArcGIS).
- Mapas que pueden contener marcadores geográficos (coordenadas lat/lon), waypoints tácticos o anillos concéntricos náuticos (bullseyes).

El núcleo ejecutable de este proyecto recae en el script `app/main.py`.

## 2. Traducción de Lenguaje Natural a CLI (Funcionalidades)

Cuando recibas una petición en lenguaje natural, debes estructurar los parámetros solicitados y ejecutar `app/main.py` desde la raíz del proyecto. **Se prefieren los nombres de parámetros en inglés**, aunque el sistema admite alias en español por retrocompatibilidad.

### 💡 Ejemplo de Instrucción de Usuario:
> *"Genera las imágenes satelitales día 26/05/2026 desde las 0000Z hasta las 0600Z cada 30 minutos para centro en SKCG activa la opcion de label y coordenadas con centro en SKCG"*

### 🧠 Razonamiento Esperado del Agente:
1. **Fecha (`--date` / `--fecha`)**: El usuario indicó `26/05/2026`. Debe formatearse a formato `YYYYMMDD` -> `--date=20260526`
2. **Horas (`--hours` / `--horas`)**: "desde las 0000Z hasta las 0600Z". Debes expandir este rango a horas individuales separadas por coma -> `--hours=00,01,02,03,04,05,06`
3. **Minutos (`--minutes` / `--minutos`)**: "cada 30 minutos". Implica los minutos 00 y 30 -> `--minutes=00,30`
4. **Coordenadas de Centro (`--lat`, `--lon`)**: El usuario indica el código ICAO **SKCG** (Aeropuerto de Corozal / Las Brujas, Colombia). El Agente debe deducir o buscar las coordenadas (Latitud: `9.333`, Longitud: `-75.283`) y pasarlas como parámetros -> `--lat=9.333 --lon=-75.283`
5. **Opciones Adicionales (`--label`)**: "activa la opción de label" -> `--label=true`
6. **Modo (`--mode` / `--tipo`)**: Al ser un procesamiento para una fecha/hora específicas, corresponde al modo manual -> `--mode="manual"`

### 💻 Comando Resultante que el Agente debe ejecutar:
```bash
python app/main.py \
  --source="aws" \
  --mode="manual" \
  --date=20260526 \
  --hours=00,01,02,03,04,05,06 \
  --minutes=00,30 \
  --lat=9.333 \
  --lon=-75.283 \
  --label=true
```

## 3. Resumen de Parámetros de `main.py`

| Parámetro (Inglés) | Alias (Español) | Descripción | Ejemplo |
|:---|:---|:---|:---|
| `--mode` | `--tipo` | Modo de ejecución: `"manual"` (fechas específicas) o `"auto"` (tiempo real) | `--mode="manual"` |
| `--source` | `--fuente` | Fuente de datos: `"aws"` (defecto / NOAA S3) o `"ideam"` | `--source="aws"` |
| `--date` | `--fecha`, `--dates` | Fecha(s) en formato `YYYYMMDD` | `--date=20250523` |
| `--hours` | `--horas` | Hora(s) en formato `HH` (separadas por coma) | `--hours=13,14,15` |
| `--minutes` | `--minutos` | Minuto(s) en formato `MM` (separados por coma) | `--minutes=00,30` |
| `--lat` | | Latitudes para marcadores (soporta varias separadas por coma) | `--lat=4.711,9.333` |
| `--lon` | | Longitudes para marcadores (soporta varias separadas por coma) | `--lon=-74.072,-75.283` |
| `--label` | | Define si se muestran título, etiquetas y barra de color (`true`/`false`) | `--label=true` |
| `--bullseye` | | Anillos concéntricos (`true`) o marcadores numerados P1, P2 (`false`) | `--bullseye=true` |
| `--watermark` | `--institution`, `--institucion` | Texto personalizado de atribución en la barra inferior | `--watermark="My Lab"` |
| `--overwrite` | `--force` | Fuerza la regeneración de productos incluso si ya existen en output/ (`true`/`false`) | `--overwrite=true` |
| `--family` | `--palette`, `--enhancement` | Familia de realces de color: `"default"` (Oklahoma en C13, WV regional) o `"noaa"` (paletas oficiales goes.noaa.gov) | `--family="noaa"` |
| `--c16-enhanced` | `--c16-color` | Activa realce convectivo BD a color en Canal 16 en lugar de escala de grises (`true`/`false`) | `--c16-enhanced=true` |

## 4. Directrices Finales para el Agente
- **Códigos ICAO / Topónimos**: Siempre que el usuario provea una ciudad, departamento o código ICAO (ej. SKCG, SKBO, etc.), es tu responsabilidad como Agente traducir ese identificador a sus coordenadas reales para los parámetros `--lat` y `--lon`.
- **Formato de Rangos**: `main.py` no acepta notación de rangos como `00-06`. Todos los rangos solicitados por el usuario deben ser expandidos obligatoriamente (ej. `00,01,02,03,04,05,06`).
- **Contexto de Ejecución**: Siempre verifica que te encuentras en el entorno de Python correcto (Conda `goes-toolkit` o Docker) que tenga instaladas las dependencias del proyecto (`goes`, `matplotlib`, `gdal`, `basemap`, etc.) antes de ejecutar los comandos.
- **Ajuste de Satélite en `config.yaml`**: Antes de ejecutar la petición, revisa la fecha solicitada y modifica la propiedad `satellite` de `app/config.yaml`. Si la fecha es **anterior al 7 de abril de 2025**, usa `"G16"`. Si es **posterior**, usa `"G19"`.
