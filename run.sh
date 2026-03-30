#!/bin/bash
# WireGuard GUI Wrapper - Fedora-optimized
# Logs output to /tmp/wireguard-gui.log for debugging

LOG="/tmp/wireguard-gui.log"
echo "--- Starting WireGuard GUI at $(date) ---" > "$LOG"

# Get the absolute path to the project directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if we are already root
if [ "$(id -u)" -eq 0 ]; then
    echo "Running as root, launching Python GUI..." >> "$LOG"
    # Fedora often needs this to open windows as root on Wayland
    export DISPLAY="${DISPLAY:-:0}"
    export WAYLAND_DISPLAY="${WAYLAND_DISPLAY}"
    export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR}"
    
    "$SCRIPT_DIR/venv/bin/python3" "$SCRIPT_DIR/wireguard_gui.py" >> "$LOG" 2>&1
    exit $?
fi

echo "Not root, requesting privileges using pkexec..." >> "$LOG"

# Using pkexec directly with the run.sh ensures Fedora GNOME handles the prompt
# Passing GUI environment variables is critical for Wayland
pkexec env DISPLAY="$DISPLAY" \
           XAUTHORITY="$XAUTHORITY" \
           WAYLAND_DISPLAY="$WAYLAND_DISPLAY" \
           XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
           "$SCRIPT_DIR/run.sh" "$@"
RET=$?

if [ $RET -ne 0 ]; then
    echo "pkexec failed (code $RET), trying zenity fallback..." >> "$LOG"
    if [ -f "/usr/bin/zenity" ]; then
        PASS=$(zenity --password --title="WireGuard Manager Root Access" 2>/dev/null)
        if [ $? -eq 0 ] && [ ! -z "$PASS" ]; then
            echo "$PASS" | sudo -S env DISPLAY="$DISPLAY" \
                                       WAYLAND_DISPLAY="$WAYLAND_DISPLAY" \
                                       XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
                                       "$SCRIPT_DIR/run.sh" "$@" >> "$LOG" 2>&1
            exit $?
        fi
    fi
fi

exit $RET
