#!/bin/bash
# Запускает claude и записывает весь диалог в файл

mkdir -p ~/claude_logs

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RAW_LOG=~/claude_logs/session_${TIMESTAMP}.raw.log
CLEAN_LOG=~/claude_logs/session_${TIMESTAMP}.log

echo "Лог сессии: $CLEAN_LOG"
echo "Начало: $(date)" > "$RAW_LOG"
echo "---" >> "$RAW_LOG"

# Запускаем claude внутри script (записывает весь терминальный вывод)
script -q -a "$RAW_LOG" -c "/home/timur/.local/bin/claude $*"

echo "---" >> "$RAW_LOG"
echo "Конец: $(date)" >> "$RAW_LOG"

# Очищаем от ANSI escape-кодов и управляющих символов
python3 -c "
import re, sys

with open('$RAW_LOG', 'r', errors='replace') as f:
    text = f.read()

# Убираем ANSI escape-коды (цвета, курсор и т.д.)
text = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)
text = re.sub(r'\x1b\][^\x07]*\x07', '', text)
text = re.sub(r'\x1b[()][AB012]', '', text)
text = re.sub(r'[\x00-\x08\x0e-\x1f\x7f]', '', text)

# Убираем дублирующиеся пустые строки
text = re.sub(r'\n{3,}', '\n\n', text)

with open('$CLEAN_LOG', 'w') as f:
    f.write(text)
"

# Удаляем сырой лог
rm "$RAW_LOG"

echo "Сессия сохранена: $CLEAN_LOG"
