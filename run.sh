#!/bin/bash
# WireGuard GUI Wrapper - Production Version
# Handles symlinks, path resolution, and Wayland environment propagation

LOG="/tmp/wireguard-gui.log"
# Ensure we can always write to the log by clearing it if it exists
[ -f "$LOG" ] && rm -f "$LOG"
echo "--- Starting WireGuard Manager at $(date) ---" > "$LOG"
chmod 666 "$LOG" 2>/dev/null

# 1. Resolve absolute path
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
REAL_PATH="$SCRIPT_DIR/$(basename "$SOURCE")"

# 2. Check for root
if [ "$(id -u)" -eq 0 ]; then
    export DISPLAY="${DISPLAY:-:0}"
    export WAYLAND_DISPLAY="${WAYLAND_DISPLAY}"
    export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR}"
    export XAUTHORITY="${XAUTHORITY}"
    export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS}"
    
    cd "$SCRIPT_DIR"
    if [ -f "./venv/bin/python3" ]; then
        exec "./venv/bin/python3" "wireguard_gui.py" >> "$LOG" 2>&1
    else
        exec python3 "wireguard_gui.py" >> "$LOG" 2>&1
    fi
fi

# 3. Request elevation
if [ -t 0 ]; then
    exec sudo "$REAL_PATH" "$@"
else
    exec pkexec env DISPLAY="$DISPLAY" \
                   XAUTHORITY="$XAUTHORITY" \
                   WAYLAND_DISPLAY="$WAYLAND_DISPLAY" \
                   XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
                   DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" \
                   "$REAL_PATH" "$@"
fi
