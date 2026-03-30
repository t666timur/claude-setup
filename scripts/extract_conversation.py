#!/usr/bin/env python3
"""
Извлекает читаемый диалог из JSONL файла сессии Claude Code.
Использование: python3 extract_conversation.py <file.jsonl> [output.md]
"""

import json
import sys
from datetime import datetime

def extract(jsonl_path, output_path=None):
    messages = []

    with open(jsonl_path, errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg = d.get('message', {})
            role = msg.get('role', '')
            if role not in ('user', 'assistant'):
                continue

            # Пропускаем sidechain (внутренние вызовы инструментов)
            if d.get('isSidechain'):
                continue

            timestamp = d.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    time_str = dt.strftime('%H:%M:%S')
                except:
                    time_str = ''
            else:
                time_str = ''

            content = msg.get('content', '')
            text_parts = []

            if isinstance(content, str):
                text_parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get('type', '')
                    if btype == 'text':
                        t = block.get('text', '').strip()
                        if t:
                            text_parts.append(t)
                    elif btype == 'tool_use':
                        name = block.get('name', '')
                        inp = block.get('input', {})
                        # Показываем только самое важное
                        if name == 'Bash':
                            cmd = inp.get('command', '')[:120]
                            text_parts.append(f'[Bash: {cmd}]')
                        elif name in ('Read', 'Write', 'Edit'):
                            path = inp.get('file_path', '')
                            text_parts.append(f'[{name}: {path}]')
                        elif name:
                            text_parts.append(f'[Tool: {name}]')
                    elif btype == 'tool_result':
                        # Пропускаем результаты инструментов — они загромождают лог
                        pass

            text = '\n'.join(text_parts).strip()
            if not text:
                continue

            messages.append((role, time_str, text))

    if not messages:
        print("Сообщений не найдено.", file=sys.stderr)
        return

    lines = []
    lines.append(f"# Сессия Claude Code")
    lines.append(f"Файл: {jsonl_path}")
    lines.append(f"Сообщений: {len(messages)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for role, time_str, text in messages:
        if role == 'user':
            prefix = f"## Timur [{time_str}]" if time_str else "## Timur"
        else:
            prefix = f"### Claude [{time_str}]" if time_str else "### Claude"
        lines.append(prefix)
        lines.append(text)
        lines.append("")

    result = '\n'.join(lines)

    if output_path:
        with open(output_path, 'w') as f:
            f.write(result)
        print(f"Сохранено: {output_path}", file=sys.stderr)
    else:
        print(result)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Использование: {sys.argv[0]} <file.jsonl> [output.md]")
        sys.exit(1)
    extract(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
