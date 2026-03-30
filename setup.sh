#!/bin/bash
set -e

echo "WireGuard GUI Setup"
echo "=================="
echo

# Detect package manager and OS
if command -v apt-get &> /dev/null; then
    PACKAGE_MANAGER="apt"
    OS="debian-based"
elif command -v dnf &> /dev/null; then
    PACKAGE_MANAGER="dnf"
    OS="fedora-based"
elif command -v pacman &> /dev/null; then
    PACKAGE_MANAGER="pacman"
    OS="arch-based"
elif command -v zypper &> /dev/null; then
    PACKAGE_MANAGER="zypper"
    OS="suse-based"
else
    echo "Error: Unsupported package manager"
    echo "Supported: apt (Debian/Ubuntu), dnf (Fedora), pacman (Arch), zypper (openSUSE)"
    exit 1
fi

echo "Detected OS: $OS (using $PACKAGE_MANAGER)"
echo

# Install system dependencies
echo "Installing system dependencies..."

case $PACKAGE_MANAGER in
    apt)
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip python3-venv python3-dev build-essential wireguard wireguard-tools
        ;;
    dnf)
        sudo dnf install -y python3 python3-pip python3-devel gcc make wireguard-tools
        ;;
    pacman)
        sudo pacman -Sy --noconfirm python python-pip base-devel wireguard-tools
        ;;
    zypper)
        sudo zypper install -y python3 python3-pip python3-devel gcc make wireguard-tools
        ;;
esac

echo "System dependencies installed"
echo

# Create virtual environment
echo "Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip setuptools
pip install -r requirements.txt

echo
echo "✓ Setup complete!"
echo
echo "To run the application:"
echo "  source venv/bin/activate"
echo "  python3 wireguard_gui.py"
echo

# Implementation of --install-desktop
if [[ "$1" == "--install-desktop" ]]; then
    echo "Installing desktop shortcut..."
    USER_HOME=$(eval echo "~$SUDO_USER")
    if [ -z "$SUDO_USER" ]; then
        USER_HOME=$HOME
    fi
    
    # Get absolute path of current directory
    CURRENT_DIR=$(pwd)
    TEMP_DESKTOP="/tmp/wireguard-gui.desktop"
    
    # Create a temporary desktop file for installation
    cat > "$TEMP_DESKTOP" << EOF
[Desktop Entry]
Type=Application
Name=WireGuard Manager
Comment=Manage WireGuard VPN connections
Exec=$CURRENT_DIR/run.sh
Icon=$CURRENT_DIR/wireguard.png
Categories=Network;Utility;
Terminal=false
StartupNotify=true
EOF
    
    # Use standard XDG tools to install
    sudo -u $SUDO_USER xdg-desktop-menu install --mode user "$TEMP_DESKTOP"
    sudo -u $SUDO_USER xdg-desktop-icon install "$TEMP_DESKTOP"
    
    # Make sure it's executable for GNOME "Trust"
    DESKTOP_FILE="$USER_HOME/.local/share/applications/wireguard-gui.desktop"
    ACTUAL_DESKTOP="$USER_HOME/Desktop/wireguard-gui.desktop"
    
    chmod +x "$DESKTOP_FILE"
    [ -f "$ACTUAL_DESKTOP" ] && chmod +x "$ACTUAL_DESKTOP"
    
    # Update the database
    sudo -u $SUDO_USER update-desktop-database "$USER_HOME/.local/share/applications"
    
    rm "$TEMP_DESKTOP"
    echo "✓ Desktop shortcut installed to Application Menu and Desktop"
else
    echo "Or create a desktop shortcut by running:"
    echo "  sudo $0 --install-desktop"
fi
