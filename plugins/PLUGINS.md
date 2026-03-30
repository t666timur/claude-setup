# Claude Code — Установленные плагины и скилы

## Slash-команды (wshobson/commands)

**Источник:** https://github.com/wshobson/commands
**Установка:** `git clone https://github.com/wshobson/commands ~/.claude/commands`
**Путь:** `~/.claude/commands/`

### Workflows (многошаговые процессы)

| Команда | Описание |
|---|---|
| `/feature-development` | Полный цикл разработки новой фичи |
| `/tdd-cycle` | Test-Driven Development — тесты сначала |
| `/full-stack-feature` | Full-stack реализация фичи |
| `/security-hardening` | Hardening кода и инфраструктуры |
| `/git-workflow` | Автоматизация git операций |
| `/deploy-checklist` | Чеклист перед деплоем |
| `/smart-fix` | Умный дебаг и исправление багов |
| `/performance-optimization` | Оптимизация производительности |
| `/incident-response` | Реакция на инциденты |
| `/legacy-modernize` | Модернизация legacy кода |
| `/ml-pipeline` | ML pipeline workflow |
| `/multi-platform` | Multi-platform разработка |
| `/data-driven-feature` | Разработка data-driven фич |
| `/full-review` | Полный review кода |
| `/workflow-automate` | Автоматизация workflows |

### Tools (утилиты)

| Команда | Описание |
|---|---|
| `/code-explain` | Объяснение кода |
| `/security-scan` | Сканирование безопасности |
| `/docker-optimize` | Оптимизация Docker |
| `/db-migrate` | Миграции БД |
| `/debug-trace` | Трассировка ошибок |
| `/api-scaffold` | Scaffolding API |
| `/test-harness` | Генерация тестов |
| `/refactor-clean` | Рефакторинг кода |
| `/tech-debt` | Анализ технического долга |
| `/monitor-setup` | Настройка мониторинга |
| `/deploy-checklist` | Чеклист деплоя |
| `/k8s-manifest` | Kubernetes манифесты |
| `/data-pipeline` | Data pipeline |
| `/compliance-check` | Проверка compliance |
| `/deps-audit` | Аудит зависимостей |
| `/deps-upgrade` | Обновление зависимостей |

---

## Официальные плагины Anthropic (marketplace)

**Маркетплейс:** `claude-plugins-official`
**Установка:** `/plugin install <name>@claude-plugins-official`

### Установить (команды запускать внутри `claude` сессии)

```
/plugin install telegram@claude-plugins-official
/plugin install feature-dev@claude-plugins-official
/plugin install commit-commands@claude-plugins-official
/plugin install learning-output-style@claude-plugins-official
/plugin install code-review@claude-plugins-official
```

### Описание плагинов

| Плагин | Описание |
|---|---|
| `telegram` | Telegram-бот подключённый к Claude Code через MCP сервер |
| `feature-dev` | 7-фазный workflow разработки фич с агентами |
| `commit-commands` | `/commit`, `/commit-push-pr`, `/clean_gone` команды |
| `learning-output-style` | Режим обучения — Claude учит тебя писать код |
| `code-review` | Автоматический code review |
| `security-guidance` | Хук безопасности — предупреждает о рисках |

---

## Telegram плагин — Настройка

**Требования:** Bun — `curl -fsSL https://bun.sh/install | bash`

**Шаги:**
1. Создать бота через [@BotFather](https://t.me/BotFather) → `/newbot`
2. Установить плагин: `/plugin install telegram@claude-plugins-official`
3. Сохранить токен: `/telegram:configure 123456789:TOKEN`
4. Запустить: `claude --channels plugin:telegram@claude-plugins-official`
5. Написать боту в Telegram → получить код → `/telegram:access pair <код>`
6. Заблокировать: `/telegram:access policy allowlist`

---

## Внешние репозитории со скилами

| Репозиторий | Описание |
|---|---|
| [anthropics/skills](https://github.com/anthropics/skills) | Официальные скилы Anthropic |
| [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | Каталог всех скилов и инструментов |
| [wshobson/commands](https://github.com/wshobson/commands) | 57 production slash-команд |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | 192+ скила для всех инструментов |
| [travisvn/awesome-claude-skills](https://github.com/travisvn/awesome-claude-skills) | Кураторский список скилов |
| [qdhenry/Claude-Command-Suite](https://github.com/qdhenry/Claude-Command-Suite) | 216+ команд, 12 скилов, 54 агента |
