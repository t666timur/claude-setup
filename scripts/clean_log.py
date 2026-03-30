#!/usr/bin/env python3
"""
Конвертирует raw терминальный лог в читаемый текст.
Использует pyte для эмуляции терминала.
"""

import sys
import re
import pyte

def clean_raw_log(raw_path, clean_path, cols=220, rows=50):
    with open(raw_path, 'r', errors='replace') as f:
        content = f.read()

    # Убираем заголовок script
    content = re.sub(r'Script started on.*?\n', '', content)
    content = re.sub(r'Script done on.*?\n', '', content)

    screen = pyte.Screen(cols, rows)
    stream = pyte.ByteStream(screen)

    lines_out = []
    current_chunk = []

    # Разбиваем по строкам входного файла (каждая строка = порция вывода)
    for raw_line in content.split('\n'):
        raw_line += '\n'
        try:
            stream.feed(raw_line.encode('utf-8', errors='replace'))
        except Exception:
            pass

        # Снимаем снимок экрана после каждой строки
        screen_lines = []
        for i in range(rows):
            line = screen.buffer[i]
            text = ''.join(char.data for char in line.values()).rstrip()
            if text:
                screen_lines.append(text)

        if screen_lines:
            current_chunk = screen_lines

    # Финальный снимок — весь текст что остался на экране
    # Но нам нужна история, а не только последний экран
    # Поэтому используем другой подход — посимвольную обработку

    # Второй проход: посимвольная обработка с обработкой \r
    lines_out = []
    current_line = []

    i = 0
    data = content
    while i < len(data):
        ch = data[i]
        if ch == '\r':
            # Carriage return — возврат в начало строки
            if i + 1 < len(data) and data[i+1] == '\n':
                # \r\n — обычный перенос строки
                line_text = ''.join(current_line).rstrip()
                if line_text:
                    lines_out.append(line_text)
                current_line = []
                i += 2
                continue
            else:
                # Просто \r — очищаем текущую строку (TUI перерисовка)
                current_line = []
        elif ch == '\n':
            line_text = ''.join(current_line).rstrip()
            if line_text:
                lines_out.append(line_text)
            current_line = []
        elif ch == '\x08':
            # Backspace
            if current_line:
                current_line.pop()
        elif ch == '\x1b':
            # ANSI escape sequence — пропускаем
            # Читаем до конца последовательности
            j = i + 1
            if j < len(data):
                if data[j] == '[':
                    j += 1
                    while j < len(data) and data[j] not in 'ABCDEFGHJKLMPSTXZabcdefghijklmnoprstuvwxyz@`':
                        j += 1
                    i = j + 1
                    continue
                elif data[j] == ']':
                    # OSC sequence — до BEL или ST
                    j += 1
                    while j < len(data) and data[j] not in '\x07\x9c':
                        j += 1
                    i = j + 1
                    continue
                else:
                    i = j + 1
                    continue
        elif ord(ch) < 32:
            # Другие управляющие символы — пропускаем
            pass
        else:
            current_line.append(ch)
        i += 1

    if current_line:
        line_text = ''.join(current_line).rstrip()
        if line_text:
            lines_out.append(line_text)

    # Убираем дублирующиеся строки подряд (артефакты TUI перерисовки)
    deduped = []
    prev = None
    for line in lines_out:
        if line != prev:
            deduped.append(line)
            prev = line

    # Убираем тройные+ пустые строки
    result = '\n'.join(deduped)
    result = re.sub(r'\n{3,}', '\n\n', result)

    with open(clean_path, 'w') as f:
        f.write(result)

    print(f"Готово: {clean_path}")
    print(f"Строк: {len(deduped)}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f"Использование: {sys.argv[0]} input.raw.log output.log")
        sys.exit(1)
    clean_raw_log(sys.argv[1], sys.argv[2])
