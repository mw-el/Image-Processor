#!/bin/bash
# AA Image Processor Startscript
# Startet die App im aa-image-processor Environment

echo "Starting AA Image Processor..."

# Ins Projektverzeichnis wechseln
cd ~/_AA_Image_Processor

# App mit conda run starten (zuverlässiger als manuelle Aktivierung)
# Unset LD_LIBRARY_PATH to prevent system Qt interference
echo "Launching app in aa-image-processor environment..."
env -u LD_LIBRARY_PATH conda run -n aa-image-processor python -m src.app "$@"

echo "AA Image Processor closed"
