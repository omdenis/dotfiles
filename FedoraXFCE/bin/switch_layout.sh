#!/bin/bash

# Определяем клавиши Ctrl
LEFT_CTRL=37
RIGHT_CTRL=105

# Получаем нажатие Ctrl
xev | while read line; do
    # Когда нажимается левый Ctrl (37)
    if [[ "$line" == *"keycode $LEFT_CTRL (keysym 0xFFE1, Control_L)"* ]]; then
        # Переключаем на русский
        setxkbmap -layout ru
    fi

    # Когда нажимается правый Ctrl (105)
    if [[ "$line" == *"keycode $RIGHT_CTRL (keysym 0xFFE4, Control_R)"* ]]; then
        # Переключаем на английский
        setxkbmap -layout us
    fi
done
