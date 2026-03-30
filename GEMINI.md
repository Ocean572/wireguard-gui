# Gemini Development Context - WireGuard Manager

## Project Overview
A PyQt6-based WireGuard GUI for Linux that manages tunnels in `/etc/wireguard`. It prioritizes seamless root elevation and desktop integration.

## Architectural Decisions
- **Root Elevation:** Uses a `run.sh` bash wrapper to handle `pkexec` and environment variable propagation (DISPLAY, WAYLAND_DISPLAY, DBUS_SESSION_BUS_ADDRESS). This ensures the GUI and system services (like DNS) work as root on modern Wayland systems.
- **Thread Management:** Uses a strict "Worker-Thread" pattern with explicit cleanup. Workers are moved to `QThread` objects, and connections to `finished` signals ensure threads are quit and deleted correctly, preventing "object deleted while running" crashes.
- **Status Detection:** Monitors `/sys/class/net/` directly for active interfaces to provide instant, root-less status updates.
- **Resilient IP Fetching:** Implements a multi-service failover (ip-api.com -> ipify.org) with retries to handle network transitions during VPN state changes.
- **Distribution:** Supports both `.deb` (Debian/Ubuntu) and `.rpm` (Fedora/RHEL) package generation with automatic virtual environment setup in post-install scripts.

## Current State (v1.0.0-2 Stable)
- Stable Core: High-reliability Connect/Disconnect logic.
- Robust Threading: All background tasks (IP, Monitor, Commands) are safely isolated.
- Fedora 41 Verified: Full compatibility with Wayland and GNOME desktop standards.
- Logging: Integrated logging to `/tmp/wireguard-gui.log`.

## Key Files
- `wireguard_gui.py`: Main PyQt6 application.
- `run.sh`: Elevation and environment wrapper.
- `setup.sh`: Legacy installation script.
- `wireguard-manager.spec.tmp`: Template for RPM builds.

## Planned/Future Work
- [ ] Speed/Traffic real-time graphs.
- [ ] QR Code generation for peers.
- [ ] Auto-connect on system boot.
