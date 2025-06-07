#!/bin/bash

# Получаем текущий workspace (номер начинается с 0)
current_ws=$(wmctrl -d | awk '/\*/ {print $1}')

# Получаем список окон, которые на этом workspace
# Формат: window_id title
wmctrl -lx | awk -v ws="$current_ws" '$2 == ws {print " " substr($0, index($0,$5))}' | \
rofi -monitor -1 -dmenu -p "Window: " | \
awk '{print $1}' | \
xargs -r wmctrl -ia
