#!/bin/bash
# Вызывается Stop хуком — обновляет живой лог текущей сессии

# Читаем session_id из stdin (JSON от Claude Code)
SESSION_ID=$(python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null)

if [ -z "$SESSION_ID" ]; then
    exit 0
fi

JSONL="$HOME/.claude/projects/-home-timur/${SESSION_ID}.jsonl"

if [ ! -f "$JSONL" ]; then
    exit 0
fi

# Обновляем живой лог
python3 ~/bin/extract_conversation.py "$JSONL" "$HOME/claude_logs/live_current.md" 2>/dev/null

# Дописываем новые сообщения в shared_history.json
python3 ~/bin/sync_shared_history.py "$JSONL" 2>/dev/null

exit 0
