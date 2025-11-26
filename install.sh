#!/bin/bash
# AA Image Processor Installation Script
# Installs all dependencies and sets up desktop integration

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="AA Image Processor"
ENV_NAME="aa-image-processor"
PYTHON_VERSION="3.11"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"

# Helper functions
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."

    # Check if conda is available
    if ! command -v conda &> /dev/null; then
        print_error "Conda is not installed or not in PATH"
        echo "Please install Miniconda or Anaconda from https://docs.conda.io/en/latest/miniconda.html"
        exit 1
    fi

    # Check if python is available
    if ! command -v python &> /dev/null; then
        print_error "Python is not installed or not in PATH"
        exit 1
    fi

    print_info "Prerequisites check passed"
}

# Create conda environment
create_environment() {
    print_info "Creating conda environment: $ENV_NAME with Python $PYTHON_VERSION..."

    # Check if environment already exists
    if conda env list | grep -q "^$ENV_NAME "; then
        print_warn "Environment '$ENV_NAME' already exists. Skipping creation..."
        return 0
    fi

    conda create -n "$ENV_NAME" python="$PYTHON_VERSION" -y
    print_info "Conda environment created successfully"
}

# Install dependencies
install_dependencies() {
    print_info "Installing dependencies..."

    # Activate the environment
    source ~/miniconda3/bin/activate "$ENV_NAME" 2>/dev/null || \
        source ~/anaconda3/bin/activate "$ENV_NAME" 2>/dev/null || \
        (print_error "Failed to activate conda environment"; exit 1)

    # Install from requirements.txt
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        pip install -r "$SCRIPT_DIR/requirements.txt"
        print_info "Dependencies installed successfully"
    else
        print_error "requirements.txt not found in $SCRIPT_DIR"
        exit 1
    fi
}

# Setup desktop integration
setup_desktop_integration() {
    print_info "Setting up desktop integration..."

    mkdir -p "$DESKTOP_DIR" "$ICON_DIR"

    # Copy icon
    if [ -f "$SCRIPT_DIR/image_processor.png" ]; then
        cp "$SCRIPT_DIR/image_processor.png" "$ICON_DIR/aa-image-processor.png"
        print_info "Icon installed"
    else
        print_warn "Icon file not found at $SCRIPT_DIR/image_processor.png"
    fi

    # Create desktop entry
    DESKTOP_FILE="$DESKTOP_DIR/image_processor.desktop"

    cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=$PROJECT_NAME
Comment=Image cropping and WebP export with adjustments
Exec=$SCRIPT_DIR/start_image_processor.sh %u
Icon=$ICON_DIR/aa-image-processor.png
Terminal=false
Type=Application
Categories=Graphics;Photography;
StartupNotify=true
MimeType=image/jpeg;image/png;image/webp;image/bmp;image/tiff;
StartupWMClass=AA Image Processor
EOF

    print_info "Desktop entry created at $DESKTOP_FILE"

    # Update desktop database if available
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
        print_info "Desktop database updated"
    fi

    # Register MIME types
    if command -v xdg-mime &> /dev/null; then
        xdg-mime default image_processor.desktop image/jpeg image/png image/webp image/bmp image/tiff
        print_info "MIME types registered"
    else
        print_warn "xdg-mime not found - MIME type registration skipped"
    fi
}

# Make startup script executable
make_executable() {
    print_info "Making startup scripts executable..."

    if [ -f "$SCRIPT_DIR/start_image_processor.sh" ]; then
        chmod +x "$SCRIPT_DIR/start_image_processor.sh"
        print_info "start_image_processor.sh is now executable"
    fi

    chmod +x "$SCRIPT_DIR/install.sh"
}

# Verify installation
verify_installation() {
    print_info "Verifying installation..."

    source ~/miniconda3/bin/activate "$ENV_NAME" 2>/dev/null || \
        source ~/anaconda3/bin/activate "$ENV_NAME" 2>/dev/null || true

    # Check if required packages are installed
    local required_packages=("PySide6" "Pillow" "opencv" "numpy" "scipy")
    local failed=0

    for package in "${required_packages[@]}"; do
        if python -c "import $(echo $package | tr '[:upper:]' '[:lower:]')" 2>/dev/null; then
            print_info "✓ $package installed"
        else
            print_warn "✗ $package not found"
            ((failed++))
        fi
    done

    if [ $failed -eq 0 ]; then
        print_info "All required packages are installed"
        return 0
    else
        print_error "$failed package(s) missing"
        return 1
    fi
}

# Main installation flow
main() {
    echo "=========================================="
    echo "  $PROJECT_NAME Installation"
    echo "=========================================="
    echo ""

    check_prerequisites
    echo ""

    create_environment
    echo ""

    install_dependencies
    echo ""

    make_executable
    echo ""

    setup_desktop_integration
    echo ""

    if verify_installation; then
        echo ""
        echo "=========================================="
        echo -e "${GREEN}Installation completed successfully!${NC}"
        echo "=========================================="
        echo ""
        echo "You can now start the application by:"
        echo "  1. Running the startup script:"
        echo "     $SCRIPT_DIR/start_image_processor.sh"
        echo ""
        echo "  2. Or directly with:"
        echo "     python -m src.app [image_file]"
        echo ""
        echo "  3. Using the desktop application menu"
        echo ""
        echo "Make sure to activate the environment first:"
        echo "  conda activate $ENV_NAME"
        echo ""
    else
        echo ""
        echo "=========================================="
        echo -e "${RED}Installation completed with warnings${NC}"
        echo "=========================================="
        echo "Some packages may be missing. Please check the output above."
        echo ""
        exit 1
    fi
}

# Run main function
main "$@"
