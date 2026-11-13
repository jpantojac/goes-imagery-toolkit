#!/bin/bash

# Obtener la hora actual en UTC
current_date=$(date -u +"%Y%m%d")
current_hour=$(date -u +"%H")
current_minute=$(date -u +"%M")

# Redondear los minutos hacia abajo a los múltiplos de 10
rounded_minute=$(( (current_minute / 10) * 10 ))

# Si los minutos actuales son menores que el múltiplo de 10, restar una hora y poner los minutos en 50
if [ "$rounded_minute" -eq 0 ] && [ "$current_minute" -lt 10 ]; then
    rounded_minute=50
    current_hour=$(date -u -d "-1 hour" +"%H")
elif [ "$rounded_minute" -eq 0 ]; then
    rounded_minute=50
    current_hour=$((current_hour - 1))
fi

# Ejecutar el script de Python con la hora ajustada
python3 main.py --mode="auto" --source="aws" --date="$current_date" --hours="$current_hour" --minutes="$rounded_minute"
