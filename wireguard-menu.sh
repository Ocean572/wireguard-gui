#!/bin/bash

WG_DIR="/etc/wireguard"

# Use sudo with shell so glob expands as root
mapfile -t tunnels < <(sudo bash -c "ls $WG_DIR/*.conf 2>/dev/null" | xargs -n1 basename | sed 's/.conf//')

if [ ${#tunnels[@]} -eq 0 ]; then
    echo "No WireGuard configs found in $WG_DIR"
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Available WireGuard tunnels:"
for i in "${!tunnels[@]}"; do
    echo "$((i+1))) ${tunnels[$i]}"
done

echo
read -p "Select a tunnel (number): " choice

if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt ${#tunnels[@]} ]; then
    echo "Invalid selection."
    read -p "Press Enter to exit..."
    exit 1
fi

TUNNEL="${tunnels[$((choice-1))]}"

echo
echo "Bringing up tunnel: $TUNNEL"
sudo wg-quick up "$TUNNEL"

if [ $? -ne 0 ]; then
    echo "Failed to start tunnel."
    read -p "Press Enter to exit..."
    exit 1
fi

echo
echo "Tunnel is up. Showing status every 5 seconds."
echo "Press 'q' then Enter to stop..."

while true; do
    clear
    echo "=== wg show ($TUNNEL) ==="
    sudo wg show "$TUNNEL"
    echo
    echo "Type 'exit' and press Enter to disconnect tunnel"
    echo "Press Enter to refresh immediately"

    read -t 5 input

    if [[ "$input" == "exit" ]]; then
        read -p "Are you sure you want to disconnect? (yes/no): " confirm
        if [[ "$confirm" == "yes" ]]; then
            break
        fi
    fi
done

echo
echo "Shutting down tunnel: $TUNNEL"
sudo wg-quick down "$TUNNEL"

echo
read -p "Tunnel closed. Press Enter to exit..."
