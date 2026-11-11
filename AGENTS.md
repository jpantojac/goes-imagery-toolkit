# 🤖 Instrucciones para Agentes de IA (AGENTS.md)

Este archivo proporciona contexto y directrices para los asistentes o agentes de Inteligencia Artificial que operen sobre el proyecto **SatelliteProducts**. Su propósito es definir cómo el Agente debe interpretar las instrucciones en lenguaje natural y traducirlas a ejecuciones de código o scripts de forma autónoma y correcta.

## 1. Contexto y Sentido del Proyecto

**SatelliteProducts** es una herramienta desarrollada para procesar, generar y visualizar imágenes satelitales provenientes de los satélites **GOES-16 y GOES-19**. Las imágenes se descargan desde fuentes como AWS Open Data o el repositorio regional del IDEAM y se procesan para producir:

- Imágenes PNG con diferentes paletas personalizadas (escala de grises, térmico, vapor de agua, etc.).
- Archivos georreferenciados como PGW o imágenes TIFF (si se requieren para GIS).
- Mapas que pueden contener marcadores geográficos (basados en coordenadas lat/lon) y etiquetas institucionales o anillos concéntricos.

El núcleo ejecutable de este proyecto recae en el script `app/main.py`.

## 2. Traducción de Lenguaje Natural a CLI (Funcionalidades)

Cuando recibas una petición en lenguaje natural, debes estructurar los parámetros solicitados y ejecutar `main.py` desde la raíz del proyecto.

### 💡 Ejemplo de Instrucción de Usuario:
> *"Genera las imágenes satelitales día 26/05/2026 desde las 0000Z hasta las 0600Z cada 30 minutos para centro en SKCG activa la opcion de label y coordenadas con centro en SKCG"*

### 🧠 Razonamiento Esperado del Agente:
1. **Fecha (`--fecha`)**: El usuario indicó `26/05/2026`. Debe formatearse a formato `YYYYMMDD` -> `--fecha=20260526`
2. **Horas (`--horas`)**: "desde las 0000Z hasta las 0600Z". Debes expandir este rango a horas individuales separadas por coma -> `--horas=00,01,02,03,04,05,06`
3. **Minutos (`--minutos`)**: "cada 30 minutos". Implica los minutos 00 y 30 -> `--minutos=00,30`
4. **Coordenadas de Centro (`--lat`, `--lon`)**: El usuario indica el código ICAO **SKCG** (Aeropuerto Las Brujas, Corozal, Colombia). El Agente debe deducir o buscar las coordenadas (Latitud: `9.333`, Longitud: `-75.283`) y pasarlas como parámetros -> `--lat=9.333 --lon=-75.283`
5. **Opciones Adicionales (`--label`)**: "activa la opción de label" -> `--label=true`
6. **Modo (`--tipo`)**: Al ser un procesamiento para una fecha/hora específicas, corresponde al modo manual -> `--tipo="manual"`

### 💻 Comando Resultante que el Agente debe ejecutar:
```bash
python app/main.py \
  --fuente="aws" \
  --tipo="manual" \
  --fecha=20260526 \
  --horas=00,01,02,03,04,05,06 \
  --minutos=00,30 \
  --lat=9.333 \
  --lon=-75.283 \
  --label=true
```

## 3. Resumen de Parámetros de `main.py`

| Parámetro | Descripción | Ejemplo |
|-----------|-------------|---------|
| `--tipo` | "manual" (para fechas específicas) o "auto" (para la imagen más reciente) | `--tipo="manual"` |
| `--fecha` | Fecha(s) en formato `YYYYMMDD` | `--fecha=20250523` |
| `--horas` | Hora(s) en formato `HH` (separadas por coma) | `--horas=13,14,15` |
| `--minutos` | Minuto(s) en formato `MM` (separados por coma) | `--minutos=00,30` |
| `--fuente` | "aws" (defecto) o "ideam" | `--fuente="aws"` |
| `--lat` | Latitudes para marcadores (soporta varias separadas por coma) | `--lat=4.711,9.333` |
| `--lon` | Longitudes para marcadores (soporta varias separadas por coma) | `--lon=-74.072,-75.283` |
| `--label` | Define si se muestran etiquetas y barra de color (`true`/`false`) | `--label=true` |

## 4. Directrices Finales para el Agente
- **Códigos ICAO / Topónimos**: Siempre que el usuario provea una ciudad, departamento o código ICAO (ej. SKCG, SKBO, etc.), es tu responsabilidad como Agente traducir ese identificador a sus coordenadas reales para los parámetros `--lat` y `--lon`.
- **Formato de Rangos**: `main.py` no acepta notación de rangos como `00-06`. Todos los rangos solicitados por el usuario deben ser expandidos obligatoriamente (ej. `00,01,02,03,04,05,06`).
- **Contexto de Ejecución**: Siempre verifica que te encuentras en el entorno de Python correcto (virtual environment si aplica) que tenga instaladas las dependencias del proyecto (como `goes`, `matplotlib`, `basemap`, etc.) antes de ejecutar los comandos.
- **Ajuste de Satélite en `config.yaml`**: Antes de ejecutar la petición, revisa la fecha solicitada y modifica la línea 18 (`satellite`) del archivo `app/config.yaml`. Si la fecha es **anterior al 7 de abril de 2025**, usa `"G16"`. Si es **posterior**, usa `"G19"`.
