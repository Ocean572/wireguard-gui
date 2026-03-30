# Gemini Development Context - WireGuard Manager

## Project Overview
A PyQt6-based WireGuard GUI for Linux that manages tunnels in `/etc/wireguard`. It prioritizes seamless root elevation and desktop integration.

## Architectural Decisions
- **Root Elevation:** Uses a `run.sh` bash wrapper to handle `pkexec` and environment variable propagation (DISPLAY, WAYLAND_DISPLAY). This ensures the GUI can open as root on modern Wayland-based systems like Fedora.
- **Process Management:** Uses `QThread` and a `CommandRunner` (QObject) to run `wg-quick` commands asynchronously, preventing UI freezes.
- **Status Detection:** Monitors `/sys/class/net/` directly for active interfaces to provide instant, root-less status updates, supplementing them with `wg show` output when privileges are available.
- **Desktop Integration:** Uses `xdg-desktop-menu` and `xdg-desktop-icon` for standard installation. Sets `app.setDesktopFileName("wireguard-gui")` to ensure GNOME matches the window to the launcher icon.

## Current State (v1.0.0)
- Functional core: Connect/Disconnect, Edit/Delete/New config.
- Public IP/Location fetcher integrated.
- System Tray and Menu integration complete.
- Fedora 41 (GNOME/Wayland) compatibility verified.

## Key Files
- `wireguard_gui.py`: Main PyQt6 application.
- `run.sh`: Elevation wrapper.
- `setup.sh`: Installation script.
- `requirements.txt`: Python dependencies.

## Planned/Future Work
- [ ] Speed/Traffic graphs.
- [ ] Support for non-standard config directories.
- [ ] Peer management (QR code generation).
- [ ] Auto-connect on startup options.
