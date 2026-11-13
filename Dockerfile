# Use official Ubuntu 22.04 LTS - ultra-fast, stable and proven for geospatial stacks
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

# 1. Install Python, GDAL, NetCDF4, and core scientific libraries from Ubuntu repositories (~30 seconds)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python-is-python3 \
    python3-gdal \
    python3-netcdf4 \
    python3-numpy \
    python3-matplotlib \
    python3-pil \
    python3-yaml \
    python3-requests \
    python3-bs4 \
    gdal-bin \
    libgeos-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Basemap, MetPy and GOES from pre-compiled binary wheels (~15 seconds)
RUN pip3 install --no-cache-dir \
    basemap==1.4.1 \
    basemap-data==1.3.2 \
    metpy \
    GOES

# Set working directory inside the container
WORKDIR /app

# Keep container running for CLI executions
CMD ["tail", "-f", "/dev/null"]
