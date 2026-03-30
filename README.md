# WireGuard Manager (GUI)

A modern, easy-to-use WireGuard VPN manager for Linux distributions (Fedora, Ubuntu, Arch, etc.). Built with Python and PyQt6, it provides a clean graphical interface for managing your `/etc/wireguard` configurations with native system integration.

![WireGuard Manager](wireguard.png)

## Features

- **One-Click Connectivity:** Quickly start and stop WireGuard tunnels (`wg-quick up/down`).
- **Root Elevation Integration:** Automatically handles root privileges via `pkexec` or `zenity`, ensuring secure access to system configurations.
- **Real-time Status Monitoring:** View detailed tunnel statistics, including transfer rates and peer information.
- **IP & Location Intelligence:** Automatically fetches and displays your current public IP, city, and ISP, updating instantly when you connect/disconnect.
- **Configuration Management:** Create, edit, and delete WireGuard `.conf` files directly within the app.
- **System Tray Support:** Minimize to the system tray for quick access and background monitoring.
- **Desktop Integration:** Follows XDG standards for application menu and desktop shortcut installation.

## Installation

### Prerequisites
The installation script will automatically attempt to install these for you:
- `wireguard-tools`
- `python3`
- `PyQt6`

### Setup
1. Clone the repository to your preferred location.
2. Run the setup script to install dependencies and create the desktop shortcut:
   ```bash
   sudo ./setup.sh --install-desktop
   ```
3. Search for **WireGuard Manager** in your application menu.

## Usage

- **Connecting:** Select a tunnel from the list and click **Connect**. A password prompt will appear to grant root privileges.
- **Status:** The active tunnel will be highlighted in green. Detailed `wg show` output is displayed in the right panel.
- **Managing Configs:** Use the **+ New**, **Edit**, and **Delete** buttons to manage your files in `/etc/wireguard`.
- **System Tray:** Use the tray icon (right-click) to connect or disconnect tunnels without opening the main window.

## Architecture

- **`wireguard_gui.py`**: The core PyQt6 application.
- **`run.sh`**: A robust wrapper that handles graphical root elevation (Wayland/X11 compatible).
- **`setup.sh`**: Automates environment setup, dependency installation, and XDG desktop registration.

## License
MIT
