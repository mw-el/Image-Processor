#!/bin/bash
# AA Image Processor Startscript
# Aktiviert das aa-image-processor Environment und startet die App

echo "Starting AA Image Processor..."

# Miniconda aktivieren
source ~/miniconda3/bin/activate

# aa-image-processor Environment aktivieren
conda activate aa-image-processor

# Prüfen ob Environment korrekt aktiviert wurde
if [ "$CONDA_DEFAULT_ENV" != "aa-image-processor" ]; then
    echo "Error: aa-image-processor Environment could not be activated"
    echo "Please run manually: conda activate aa-image-processor"
    exit 1
fi

echo "Environment aa-image-processor activated"

# Ins Projektverzeichnis wechseln
cd ~/_AA_Image_Processor

# App starten
echo "Starting Image Processor App..."
python -m src.app "$@"

echo "AA Image Processor closed"
