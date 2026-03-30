#!/usr/bin/env python3
"""
Синхронизирует сообщения из JSONL сессии Claude Code в shared_history.json.
Добавляет только новые пары (user+assistant) которых ещё нет в истории.
"""

import json
import sys
import os
from datetime import datetime

SHARED_HISTORY = '/home/timur/claude_logs/shared_history.json'

def load_shared():
    if os.path.exists(SHARED_HISTORY):
        with open(SHARED_HISTORY) as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def save_shared(history):
    os.makedirs(os.path.dirname(SHARED_HISTORY), exist_ok=True)
    with open(SHARED_HISTORY, 'w') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def extract_pairs(jsonl_path):
    """Извлекает пары (user, assistant) из JSONL файла."""
    messages = []
    with open(jsonl_path, errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except:
                continue
            if d.get('isSidechain'):
                continue
            msg = d.get('message', {})
            role = msg.get('role', '')
            if role not in ('user', 'assistant'):
                continue
            timestamp = d.get('timestamp', '')
            content = msg.get('content', '')
            text_parts = []
            if isinstance(content, str):
                text_parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get('type') == 'text':
                        t = block.get('text', '').strip()
                        if t:
                            text_parts.append(t)
            text = '\n'.join(text_parts).strip()
            if text:
                messages.append({'role': role, 'text': text, 'time': timestamp})

    # Собираем пары user+assistant
    pairs = []
    i = 0
    while i < len(messages):
        if messages[i]['role'] == 'user':
            user_msg = messages[i]
            # Ищем следующий ответ assistant
            if i + 1 < len(messages) and messages[i + 1]['role'] == 'assistant':
                pairs.append({
                    'source': 'console',
                    'time': user_msg['time'],
                    'user': user_msg['text'],
                    'assistant': messages[i + 1]['text']
                })
                i += 2
            else:
                i += 1
        else:
            i += 1
    return pairs

def main():
    if len(sys.argv) < 2:
        print("Использование: sync_shared_history.py <file.jsonl>")
        sys.exit(1)

    jsonl_path = sys.argv[1]
    if not os.path.exists(jsonl_path):
        sys.exit(0)

    pairs = extract_pairs(jsonl_path)
    if not pairs:
        sys.exit(0)

    history = load_shared()

    # Находим уже существующие записи из этой сессии (по source+time)
    existing_times = {(e.get('source'), e.get('time')) for e in history}

    added = 0
    for pair in pairs:
        key = (pair.get('source'), pair.get('time'))
        if key not in existing_times:
            history.append(pair)
            existing_times.add(key)
            added += 1

    if added > 0:
        save_shared(history)
        print(f"Добавлено {added} новых сообщений в shared_history.json", file=sys.stderr)

if __name__ == '__main__':
    main()
