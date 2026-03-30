#!/bin/bash
# Фильтрует логи диалогов — оставляет только значимые части
# Запускать раз в месяц

LOGS_DIR=~/claude_logs
ARCHIVE_DIR=~/claude_logs/archive
SUMMARY_FILE=~/claude_logs/summary_$(date +%Y_%m).md

mkdir -p "$ARCHIVE_DIR"

echo "# Важные моменты за $(date +%B\ %Y)" > "$SUMMARY_FILE"
echo "" >> "$SUMMARY_FILE"

# Ищем строки с ключевыми словами в логах за прошлый месяц
for log in "$LOGS_DIR"/session_*.log; do
    [ -f "$log" ] || continue

    # Извлекаем значимые фрагменты
    MATCHES=$(grep -i -A 3 \
        -e "установил\|настроил\|создал\|добавил\|исправил\|решил\|готово\|сделано\|ошибка\|проблема" \
        "$log" 2>/dev/null | head -50)

    if [ -n "$MATCHES" ]; then
        echo "## $(basename $log)" >> "$SUMMARY_FILE"
        echo '```' >> "$SUMMARY_FILE"
        echo "$MATCHES" >> "$SUMMARY_FILE"
        echo '```' >> "$SUMMARY_FILE"
        echo "" >> "$SUMMARY_FILE"
    fi

    # Архивируем старые логи (старше 35 дней)
    if [ $(find "$log" -mtime +35 2>/dev/null | wc -l) -gt 0 ]; then
        mv "$log" "$ARCHIVE_DIR/"
        echo "Архивирован: $(basename $log)"
    fi
done

echo "Готово! Резюме сохранено: $SUMMARY_FILE"
