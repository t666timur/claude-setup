#!/usr/bin/env python3
"""
Car Database Agent — webdatabays.com
Задаёт уточняющие вопросы, находит автомобиль, возвращает данные + скриншоты.

Запуск:
  python3 car_agent.py                    # интерактивный режим
  python3 car_agent.py --relogin          # сначала получить новые куки
  python3 car_agent.py --query "..."      # одиночный запрос

Зависимости:
  pip install requests beautifulsoup4 playwright --break-system-packages
  playwright install chromium
  FlareSolverr запущен на localhost:8191 (см. webdatabays_login.py)
"""

import sys, os, re, json, time, argparse
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ── конфиг ──────────────────────────────────────────────────────────────────
BASE          = "https://webdatabays.com"
FSOLVER       = "http://localhost:8191/v1"
COOKIES_FILE  = "/tmp/workshop_cookies.json"
LOGIN_SCRIPT  = os.path.join(os.path.dirname(__file__), "webdatabays_login.py")
SCREENSHOT_DIR = "/tmp/car_screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


# ── FlareSolverr навигация ───────────────────────────────────────────────────
class Navigator:
    def __init__(self, cookies_file=COOKIES_FILE):
        self.cookies = self._load_cookies(cookies_file)
        self.fs_cookies = [
            {"name": k, "value": v, "domain": "webdatabays.com", "path": "/"}
            for k, v in self.cookies.items()
        ]
        self._pw = None
        self._browser = None
        self._page = None

    def _load_cookies(self, path):
        with open(path) as f:
            return json.load(f)

    def _fs_get(self, url):
        """GET через FlareSolverr (обходит Cloudflare)."""
        r = requests.post(FSOLVER, json={
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 45000,
            "cookies": self.fs_cookies
        }, timeout=55)
        d = r.json()
        if d.get("status") == "ok":
            return d["solution"]["response"]
        print(f"[!] FlareSolverr error: {d.get('message')}")
        return None

    def _soup(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup(['script', 'style', 'noscript']): tag.decompose()
        return soup

    def _clean(self, el):
        return ' '.join(el.get_text().split())

    # ── 1. Поиск марки ───────────────────────────────────────────────────────
    def get_makes(self, trucks=False):
        """Возвращает dict {name: makeId}"""
        path = "makesOverviewTrucks" if trucks else "makesOverview"
        html = self._fs_get(f"{BASE}/workshop/touch/site/layout/{path}")
        if not html: return {}
        soup = self._soup(html)
        makes = {}
        for a in soup.find_all('a', href=True):
            m = re.search(r'makeId=([\w]+)', a['href'])
            if m:
                name = self._clean(a)
                if name:
                    makes[name.upper()] = m.group(1)
        return makes

    def find_make(self, query):
        """Найти makeId по части названия (нечёткий поиск)."""
        makes = self.get_makes()
        q = query.upper().strip()
        # Точное совпадение
        if q in makes: return q, makes[q]
        # Частичное
        for name, mid in makes.items():
            if q in name or name in q:
                return name, mid
        return None, None

    # ── 2. Модели марки ─────────────────────────────────────────────────────
    def get_model_groups(self, make_id):
        """Возвращает list of {name, groupId, years}"""
        html = self._fs_get(f"{BASE}/workshop/touch/site/layout/modelOverview?makeId={make_id}")
        if not html: return []
        soup = self._soup(html)
        groups = []
        for a in soup.find_all('a', href=True):
            m = re.search(r'modelGroupId=([\w]+)', a['href'])
            if m:
                lines = [l.strip() for l in a.get_text().split('\n') if l.strip()]
                name = lines[0] if lines else ''
                years = ' '.join(lines[1:3])
                if name:
                    groups.append({"name": name, "groupId": m.group(1), "years": years})
        return groups

    # ── 3. Кузова/серии (E46, E36 и т.д.) ──────────────────────────────────
    def get_model_variants(self, group_id, make_id):
        """Возвращает list of {name, modelId, years}"""
        html = self._fs_get(
            f"{BASE}/workshop/touch/site/layout/modelTypes?modelGroupId={group_id}&makeId={make_id}"
        )
        if not html: return []
        soup = self._soup(html)
        variants = []
        # data-url="/touch/site/layout/modelTypesList?modelId=d_770"
        for a in soup.find_all(attrs={'data-url': True}):
            durl = a['data-url']
            m = re.search(r'modelId=([\w]+)', durl)
            if m:
                lines = [l.strip() for l in a.get_text().split('\n') if l.strip()]
                name = lines[0] if lines else ''
                years = ' '.join(l for l in lines[1:] if re.search(r'\d{4}', l))
                if name:
                    variants.append({"name": name, "modelId": m.group(1), "years": years})
        return variants

    # ── 4. Двигатели варианта ───────────────────────────────────────────────
    def get_engines(self, model_id):
        """Возвращает list of {name, typeId, engine, cc, kw, years}"""
        html = self._fs_get(
            f"{BASE}/workshop/touch/site/layout/modelTypesList?modelId={model_id}"
        )
        if not html: return []
        soup = self._soup(html)
        engines = []
        for a in soup.find_all(attrs={'data-url': True}):
            durl = a['data-url']
            m = re.search(r'typeId=([\w]+)', durl)
            if m:
                parts = [l.strip() for l in a.get_text().split('|')]
                parts = [p.strip() for p in parts if p.strip()]
                engines.append({
                    "name": parts[0] if len(parts) > 0 else '',
                    "engine": parts[1] if len(parts) > 1 else '',
                    "cc": parts[2] if len(parts) > 2 else '',
                    "kw": parts[3] if len(parts) > 3 else '',
                    "years": ' '.join(parts[4:]) if len(parts) > 4 else '',
                    "typeId": m.group(1),
                })
        return engines

    # ── 5. Данные автомобиля ────────────────────────────────────────────────
    def get_vehicle_data(self, type_id):
        """Возвращает dict с основными данными и доступными секциями."""
        html = self._fs_get(
            f"{BASE}/workshop/touch/site/layout/modelDetail?typeId={type_id}"
        )
        if not html: return {}

        soup = self._soup(html)
        text_lines = [l.strip() for l in soup.get_text('\n').split('\n') if l.strip()]

        # Найти доступные секции (ссылки)
        sections = {}
        for a in soup.find_all('a', href=True):
            h = a['href']
            t = self._clean(a)
            if any(x in h for x in ['repairTimes', 'repairManuals', 'adjustmentData',
                                      'faultCodes', 'maintenance', 'costEstimate',
                                      'jackingPoints', 'eobdConnector']):
                sections[t] = BASE + h if h.startswith('/') else h

        return {
            "type_id": type_id,
            "summary": text_lines[:30],
            "sections": sections,
            "raw_html": html
        }

    def get_section_data(self, url):
        """Получить данные конкретной секции."""
        html = self._fs_get(url)
        if not html: return None
        soup = self._soup(html)
        return {
            "text": [l.strip() for l in soup.get_text('\n').split('\n') if l.strip()],
            "html": html
        }

    # ── 6. Скриншот через Playwright ────────────────────────────────────────
    def screenshot(self, url, filename=None):
        """Сделать скриншот страницы, вернуть путь к файлу."""
        if not filename:
            ts = int(time.time())
            filename = f"{SCREENSHOT_DIR}/screenshot_{ts}.png"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1280, "height": 900}
            )
            # Set cookies
            ctx.add_cookies([
                {"name": k, "value": v, "domain": "webdatabays.com", "path": "/",
                 "secure": True}
                for k, v in self.cookies.items()
            ])
            page = ctx.new_page()
            page.goto(url, timeout=20000)
            time.sleep(3)
            page.screenshot(path=filename, full_page=True)
            browser.close()

        print(f"[+] Screenshot saved: {filename}")
        return filename


# ── Агент ────────────────────────────────────────────────────────────────────
class CarAgent:
    def __init__(self):
        self.nav = None
        self.context = {}  # текущий контекст (марка, модель, двигатель)
        self._ensure_cookies()

    def _ensure_cookies(self):
        """Проверить куки, при необходимости войти заново."""
        if not os.path.exists(COOKIES_FILE):
            print("[*] Куки не найдены. Запускаю логин...")
            self._relogin()
            return

        # Проверить свежесть кук (попробовать один запрос)
        try:
            cookies = json.load(open(COOKIES_FILE))
            fs_c = [{"name": k, "value": v, "domain": "webdatabays.com", "path": "/"}
                    for k, v in cookies.items()]
            r = requests.post(FSOLVER, json={
                "cmd": "request.get",
                "url": f"{BASE}/workshop/touch/site/layout/makesOverview",
                "maxTimeout": 30000,
                "cookies": fs_c
            }, timeout=40)
            d = r.json()
            if d.get("status") == "ok" and 'All makes' in d["solution"].get("response", ""):
                print("[*] Куки действительны.")
                self.nav = Navigator()
                return
        except Exception as e:
            print(f"[!] Проверка кук не удалась: {e}")

        print("[*] Куки устарели. Повторный логин...")
        self._relogin()

    def _relogin(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, LOGIN_SCRIPT],
            capture_output=True, text=True, timeout=300
        )
        print(result.stdout[-500:] if result.stdout else "")
        if result.returncode == 0:
            self.nav = Navigator()
            print("[+] Логин успешен.")
        else:
            print(result.stderr[-300:] if result.stderr else "")
            raise RuntimeError("Логин не удался. Проверьте FlareSolverr.")

    def _ask(self, prompt, options=None):
        """Задать вопрос пользователю."""
        if options:
            for i, opt in enumerate(options, 1):
                print(f"  {i}. {opt}")
            while True:
                ans = input(f"{prompt} (1-{len(options)} или текст): ").strip()
                if ans.isdigit() and 1 <= int(ans) <= len(options):
                    return options[int(ans) - 1]
                # Попробовать найти по тексту
                for opt in options:
                    if ans.lower() in opt.lower():
                        return opt
                print(f"  Введи номер 1-{len(options)} или часть названия.")
        else:
            return input(f"{prompt}: ").strip()

    def find_vehicle(self, query=None):
        """
        Интерактивный поиск автомобиля.
        Возвращает typeId или None.
        """
        print("\n" + "─"*50)
        print("🔍 Поиск автомобиля в базе webdatabays.com")
        print("─"*50)

        # 1. Марка
        if query:
            # Попробовать извлечь марку из запроса
            makes_cache = self.nav.get_makes()
            make_name = None
            for m in makes_cache:
                if m.lower() in query.lower():
                    make_name = m
                    break

        if not make_name if 'make_name' in dir() else True:
            make_input = self._ask("\nМарка автомобиля (напр. BMW, Toyota, Volkswagen)")
            make_name, make_id = self.nav.find_make(make_input)
            if not make_name:
                print(f"[!] Марка '{make_input}' не найдена.")
                return None
        else:
            _, make_id = self.nav.find_make(make_name)

        print(f"  ✓ Марка: {make_name} (ID: {make_id})")
        self.context['make'] = make_name
        self.context['make_id'] = make_id

        # 2. Модель
        print(f"\nЗагружаю модели {make_name}...")
        groups = self.nav.get_model_groups(make_id)
        if not groups:
            print("[!] Модели не найдены.")
            return None

        group_names = [f"{g['name']} ({g['years']})" for g in groups]
        selected_group_str = self._ask(f"\nВыбери модель {make_name}", group_names)
        selected_group = groups[group_names.index(selected_group_str)]
        print(f"  ✓ Модель: {selected_group['name']}")
        self.context['model'] = selected_group['name']

        # 3. Кузов/серия
        print(f"\nЗагружаю варианты кузова...")
        variants = self.nav.get_model_variants(selected_group['groupId'], make_id)
        if not variants:
            print("[!] Варианты не найдены.")
            return None

        variant_names = [f"{v['name']} ({v['years']})" for v in variants]
        selected_var_str = self._ask(f"\nВыбери кузов/серию", variant_names)
        selected_var = variants[variant_names.index(selected_var_str)]
        print(f"  ✓ Кузов: {selected_var['name']}")
        self.context['body'] = selected_var['name']

        # 4. Двигатель
        print(f"\nЗагружаю варианты двигателей...")
        engines = self.nav.get_engines(selected_var['modelId'])
        if not engines:
            print("[!] Двигатели не найдены.")
            return None

        engine_names = [
            f"{e['name']} | {e['engine']} | {e['cc']}cc | {e['kw']} | {e['years']}"
            for e in engines
        ]
        selected_eng_str = self._ask(f"\nВыбери двигатель", engine_names)
        selected_eng = engines[engine_names.index(selected_eng_str)]
        print(f"  ✓ Двигатель: {selected_eng['name']} {selected_eng['engine']}")
        self.context['engine'] = selected_eng
        self.context['type_id'] = selected_eng['typeId']

        return selected_eng['typeId']

    def answer_question(self, type_id, question):
        """
        Ответить на вопрос о найденном автомобиле.
        Выбирает нужную секцию и возвращает данные.
        """
        print(f"\n📊 Получаю данные для typeId={type_id}...")
        data = self.nav.get_vehicle_data(type_id)
        if not data:
            print("[!] Не удалось получить данные.")
            return

        car_name = f"{self.context.get('make','')} {self.context.get('model','')} {self.context.get('body','')} {self.context.get('engine',{}).get('name','')}"
        print(f"\n🚗 Автомобиль: {car_name.strip()}")

        sections = data.get("sections", {})
        q_lower = question.lower()

        # Определить нужную секцию по ключевым словам
        if any(w in q_lower for w in ['предохранит', 'fuse', 'электр', 'electric', 'eobd', 'диагнос']):
            section_key = next((k for k in sections if any(w in k.lower() for w in ['id location', 'eobd', 'connector'])), None)
            section_type = 'electronics'
        elif any(w in q_lower for w in ['техобслуж', 'maintenance', 'масло', 'oil', 'замен', 'интервал']):
            section_key = next((k for k in sections if 'maintenance' in k.lower()), None)
            section_type = 'maintenance'
        elif any(w in q_lower for w in ['repair time', 'трудозатрат', 'нормо-час']):
            section_key = next((k for k in sections if 'repair time' in k.lower()), None)
            section_type = 'repair_times'
        elif any(w in q_lower for w in ['timing', 'цепь', 'ремень', 'грм']):
            section_key = next((k for k in sections if 'timing' in k.lower()), None)
            section_type = 'timing'
        elif any(w in q_lower for w in ['регулировк', 'adjustment', 'момент', 'torque', 'зазор']):
            section_key = next((k for k in sections if 'adjustment' in k.lower()), None)
            section_type = 'adjustment'
        elif any(w in q_lower for w in ['jacking', 'подъём', 'домкрат']):
            section_key = next((k for k in sections if 'jacking' in k.lower()), None)
            section_type = 'jacking'
        else:
            section_key = None
            section_type = 'overview'

        # Показать доступные секции
        print("\n📋 Доступные секции для этого автомобиля:")
        for i, (name, url) in enumerate(sections.items(), 1):
            print(f"  {i}. {name}")

        if section_key and section_key in sections:
            print(f"\n✅ Нашёл подходящую секцию: {section_key}")
            section_url = sections[section_key]
            self._show_section(section_key, section_url, take_screenshot=True)
        else:
            # Предложить выбор
            if sections:
                section_names = list(sections.keys())
                chosen = self._ask("\nВыбери секцию для просмотра", section_names + ["Показать общую сводку"])
                if chosen == "Показать общую сводку":
                    self._show_summary(data)
                else:
                    self._show_section(chosen, sections[chosen], take_screenshot=True)
            else:
                self._show_summary(data)

    def _show_section(self, name, url, take_screenshot=False):
        """Показать данные секции + опционально скриншот."""
        print(f"\n📄 Загружаю: {name}")
        section = self.nav.get_section_data(url)
        if not section:
            print("[!] Не удалось загрузить секцию.")
            return

        print("\n" + "─"*50)
        # Показать текст (убрать навигацию/повторы)
        nav_words = {'Cars', 'Trucks', 'Cost Estimates', 'Settings', 'Logout', 'Database', 'Search'}
        text_lines = [l for l in section['text'] if l not in nav_words and len(l) > 2]
        for line in text_lines[:60]:
            print(f"  {line}")
        if len(text_lines) > 60:
            print(f"  ... (ещё {len(text_lines)-60} строк)")
        print("─"*50)

        if take_screenshot:
            ans = input("\nСделать скриншот этой страницы? (y/n): ").strip().lower()
            if ans == 'y':
                path = self.nav.screenshot(url)
                print(f"\n📸 Скриншот: {path}")
                print("   Открой файл или скопируй путь для просмотра.")

    def _show_summary(self, data):
        """Показать общую сводку."""
        print("\n📄 Сводка:")
        nav_words = {'Cars', 'Trucks', 'Cost Estimates', 'Settings', 'Logout', 'Database', 'Search'}
        for line in data['summary']:
            if line not in nav_words:
                print(f"  {line}")

    def run(self, query=None):
        """Главный цикл агента."""
        print("\n" + "="*60)
        print("  🚗 CAR DATABASE AGENT — webdatabays.com")
        print("="*60)
        print("Этот агент находит техническую информацию об автомобилях.")
        print("Введи 'quit' для выхода.\n")

        # Сначала найти автомобиль
        type_id = self.find_vehicle(query)
        if not type_id:
            print("[!] Автомобиль не найден.")
            return

        # Цикл вопросов
        while True:
            print(f"\n💬 Задай вопрос об этом автомобиле")
            print("  Примеры: 'где предохранители', 'интервал замены масла',")
            print("           'момент затяжки', 'ремень ГРМ', 'скриншот схемы'")
            question = input("\nВопрос (или 'новый авто' / 'quit'): ").strip()

            if question.lower() in ('quit', 'exit', 'q'):
                print("До свидания!")
                break
            elif question.lower() in ('новый авто', 'new', 'reset'):
                type_id = self.find_vehicle()
                if not type_id:
                    print("[!] Автомобиль не найден.")
                    break
            elif question:
                self.answer_question(type_id, question)


# ── Запуск ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Car Database Agent")
    parser.add_argument('--relogin', action='store_true', help='Принудительный повторный логин')
    parser.add_argument('--query', type=str, help='Начальный запрос (марка/модель)')
    args = parser.parse_args()

    if args.relogin and os.path.exists(COOKIES_FILE):
        os.remove(COOKIES_FILE)

    agent = CarAgent()
    agent.run(query=args.query)
