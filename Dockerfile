# Usar la imagen base de Debian
FROM debian:bullseye-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    gfortran \
    wget \
    curl \
    libgeos-dev \
    libproj-dev \
    libcurl4-openssl-dev \
    libffi-dev

# Instalar las librerías necesarias
RUN pip3 install --no-cache-dir \
    gdal \
    numpy \
    netCDF4 \
    matplotlib \
    cartopy \
    wrf-python \
    xarray \
    pandas \
    GOES

# Establece el directorio de trabajo
WORKDIR /app
# Copia el código fuente (opcional)
# COPY . /app/

# Define el comando predeterminado
CMD ["tail", "-f", "/dev/null"]

