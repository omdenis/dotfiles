#!/bin/bash

SOURCE="$HOME"
DEST="$HOME/projects/dotfiles/FedoraXFCE/home/denis"

INCLUDES=(
  ".bashrc"
  ".config/autostart"
  ".config/obsidian"
  ".config/xfce4/xfconf/xfce-perchannel-xml/xfce4-keyboard-shortcuts.xml"
)

echo "📦 Начинаем резервное копирование..."

for item in "${INCLUDES[@]}"; do
  src_path="$SOURCE/$item"
  dest_path="$DEST/$item"

  echo "🛠️ Копируем: $src_path → $dest_path"

  # Создаём папку, если надо
  mkdir -p "$(dirname "$dest_path")"

  # Копируем файл или папку
  if [ -f "$src_path" ]; then
    cp "$src_path" "$dest_path"
  elif [ -d "$src_path" ]; then
    cp -r "$src_path" "$dest_path"
  else
    echo "⚠️ Пропущено (не найдено): $src_path"
  fi
done

echo "✅ Готово! Бэкап сохранён в $DEST"
