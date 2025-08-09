#!/bin/bash

while true; do
    echo "Choose an action:"
    echo "1 - Start VPN"
    echo "2 - Show sessions"
    echo "3 - Disconnect VPN"
    echo "0 - Exit"
    read -p "Enter choice: " choice

    case $choice in
        1)
            openvpn3 session-start --config msp
            openvpn3 sessions-list
            ;;
        2)
            openvpn3 sessions-list
            ;;
        3)
            openvpn3 session-manage --config msp --disconnect
            ;;
        0)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid input, try again."
            ;;
    esac

    echo ""
done
