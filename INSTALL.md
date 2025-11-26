# Installation Guide: AA Image Processor

## Quick Start

### Prerequisites
- **Python 3.11+**
- **Conda** (Miniconda or Anaconda) - [Install here](https://docs.conda.io/en/latest/miniconda.html)
- **Linux** (X11 or Wayland)
- **Git** (optional, for cloning)

### Automatic Installation (Recommended)

```bash
# Clone or download the repository
cd ~/path/to/_AA_Image_Processor

# Run the installation script
bash install.sh
```

This script will:
1. ✓ Check for required dependencies (Conda, Python)
2. ✓ Create a dedicated Conda environment (`aa-image-processor`)
3. ✓ Install all Python dependencies from `requirements.txt`
4. ✓ Set up desktop integration (menu entry, MIME types, icon)
5. ✓ Make startup scripts executable
6. ✓ Verify all packages are installed

### Manual Installation

If you prefer to install manually:

```bash
# 1. Create conda environment
conda create -n aa-image-processor python=3.11
conda activate aa-image-processor

# 2. Install dependencies
pip install -r requirements.txt

# 3. Make startup script executable
chmod +x start_image_processor.sh install.sh

# 4. Setup desktop integration (optional)
mkdir -p ~/.local/share/applications
mkdir -p ~/.local/share/icons/hicolor/512x512/apps

cp image_processor.png ~/.local/share/icons/hicolor/512x512/apps/aa-image-processor.png

cat > ~/.local/share/applications/image_processor.desktop << 'EOF'
[Desktop Entry]
Name=AA Image Processor
Comment=Image cropping and WebP export with adjustments
Exec=/full/path/to/_AA_Image_Processor/start_image_processor.sh %u
Icon=/home/YOUR_USERNAME/.local/share/icons/hicolor/512x512/apps/aa-image-processor.png
Terminal=false
Type=Application
Categories=Graphics;Photography;
StartupNotify=true
MimeType=image/jpeg;image/png;image/webp;image/bmp;image/tiff;
StartupWMClass=AA Image Processor
EOF

update-desktop-database ~/.local/share/applications
xdg-mime default image_processor.desktop image/jpeg image/png image/webp image/bmp image/tiff
```

## Starting the Application

### Via Startup Script (Recommended)
The startup script automatically activates the Conda environment:

```bash
# Navigate to the project directory
cd ~/path/to/_AA_Image_Processor

# Run the startup script
./start_image_processor.sh

# Or with a specific image file
./start_image_processor.sh /path/to/image.jpg
```

### Via Python Module
```bash
# First activate the environment
conda activate aa-image-processor

# Then run the application
python -m src.app [optional_image_file]
```

### Via Application Menu
If desktop integration was set up, you can launch the application from your desktop environment's application menu.

### Via File Manager
Right-click on an image file → Open With → AA Image Processor

## Verifying Installation

After installation, verify everything is working:

```bash
# Activate the environment
conda activate aa-image-processor

# Test the import
python -c "from src.app import *; print('Installation successful!')"

# Run the test suite
python -m unittest discover -s tests
```

## Dependencies

The application requires the following Python packages (automatically installed via `requirements.txt`):

| Package | Version | Purpose |
|---------|---------|---------|
| PySide6 | 6.6.0+ | Qt GUI framework |
| Pillow | 10.2.0+ | Image processing |
| OpenCV | 4.9.0+ | Computer vision operations |
| NumPy | 1.26.0+ | Numerical computing |
| SciPy | 1.11.0+ | Scientific computing |

## Troubleshooting

### "Conda command not found"
- Ensure Conda is installed: https://docs.conda.io/en/latest/miniconda.html
- Reload your shell: `source ~/.bashrc` or restart your terminal

### "aa-image-processor environment not found"
- The environment may have been created under a different name
- Check available environments: `conda env list`
- Manually activate the correct environment: `conda activate [env_name]`

### "PySide6 import error"
- Make sure you're using the correct Conda environment:
  ```bash
  conda activate aa-image-processor
  python -c "import PySide6"
  ```
- If it still fails, reinstall the environment:
  ```bash
  conda env remove -n aa-image-processor
  bash install.sh
  ```

### "Desktop entry not showing"
- Verify the desktop file was created:
  ```bash
  cat ~/.local/share/applications/image_processor.desktop
  ```
- Update the desktop database:
  ```bash
  update-desktop-database ~/.local/share/applications
  ```
- Clear the application menu cache:
  ```bash
  rm -rf ~/.cache/application-*.xbel
  ```

### "Application won't start"
- Check environment activation:
  ```bash
  conda activate aa-image-processor
  python -m src.app
  ```
- Check for error messages in the console
- Verify all dependencies are installed:
  ```bash
  pip list | grep -E "PySide|Pillow|opencv|numpy|scipy"
  ```

## System Requirements

### Minimum
- 4 GB RAM
- 500 MB disk space (without models)
- X11 or Wayland display server

### Recommended
- 8 GB RAM
- 2 GB disk space
- Modern Linux distribution (Ubuntu 22.04+, Fedora 36+, Debian 12+)

## Updating

To update the application to the latest version:

```bash
cd ~/path/to/_AA_Image_Processor
git pull origin main  # If using git
bash install.sh      # Re-run installation to update dependencies
```

## Additional Documentation

- **README.md** - Full feature overview and usage guide
- **docs/development_plan.md** - Development roadmap
- **docs/manual_test_plan.md** - Testing procedures
- **docs/user_guide.md** - Detailed user documentation (if available)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the README.md and documentation
3. Check the console output for error messages
4. Create an issue on the repository

## License

See the project repository for license information.
