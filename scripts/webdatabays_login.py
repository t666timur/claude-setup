#!/usr/bin/env python3
"""
Hybrid login: Playwright for auth cookies, FlareSolverr for Turnstile bypass.
Retries up to 3 times on failure.
"""
import time, requests, sys
from playwright.sync_api import sync_playwright

LOGIN_URL  = "https://webdatabays.com/Auth/Login"
TARGET_URL = "https://webdatabays.com/workshop/touch"
FSOLVER    = "http://localhost:8191/v1"
USERNAME   = "narwhal967"
PASSWORD   = "whal967"
MAX_RETRIES = 3


def get_login_cookies():
    """Use Playwright to login and return webdatabays cookies."""
    print("[*] Logging in via Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage',
                  '--disable-blink-features=AutomationControlled']
        )
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = ctx.new_page()

        # Visit login page
        page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # Fill form
        page.locator('input[name=Login]').fill(USERNAME)
        page.locator('input[name=Password]').fill(PASSWORD)

        # Submit and wait — don't use networkidle (CF keeps XHR going)
        page.locator('button[type=submit]').click()
        time.sleep(8)  # wait for redirect + Cloudflare
        current_url = page.url
        print(f"[*] After login, URL: {current_url}")

        cookies = ctx.cookies()
        browser.close()

    site_cookies = [
        {"name": c['name'], "value": c['value'],
         "domain": c['domain'].lstrip('.'), "path": c.get('path', '/')}
        for c in cookies
        if 'webdatabays.com' in c.get('domain', '')
    ]
    cookie_names = [c['name'] for c in site_cookies]
    print(f"[*] Got cookies: {cookie_names}")
    return site_cookies


def solve_with_flaresolverr(cookies, attempt=1):
    """Send cookies to FlareSolverr to solve Turnstile and access workshop."""
    print(f"[*] FlareSolverr attempt {attempt}/{MAX_RETRIES} → {TARGET_URL}")
    payload = {
        "cmd": "request.get",
        "url": TARGET_URL,
        "maxTimeout": 90000,
        "cookies": cookies
    }
    r = requests.post(FSOLVER, json=payload, timeout=100)
    data = r.json()
    status = data.get("status", "unknown")
    solution = data.get("solution", {})
    final_url = solution.get("url", "")
    print(f"[*] FlareSolverr status: {status}, final URL: {final_url}")

    if status == "ok":
        resp_cookies = {c['name']: c['value'] for c in solution.get("cookies", [])}
        html = solution.get("response", "")
        print(f"[+] SUCCESS! Cookie keys: {list(resp_cookies.keys())}")
        print(f"[+] HTML length: {len(html)} chars")
        # Show first meaningful content
        if html:
            # Find title or h1
            import re
            title = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)
            h1 = re.search(r'<h[12][^>]*>(.*?)</h[12]>', html, re.I | re.S)
            if title:
                print(f"[+] Page title: {title.group(1).strip()[:100]}")
            if h1:
                print(f"[+] H1: {h1.group(1).strip()[:100]}")
            # Save full HTML for inspection
            with open('/tmp/workshop_page.html', 'w') as f:
                f.write(html)
            print(f"[+] Full HTML saved to /tmp/workshop_page.html")
        return resp_cookies, html
    else:
        msg = data.get("message", "unknown error")
        print(f"[-] FAILED: {msg}")
        return None, None


def main():
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Step 1: get login cookies
            cookies = get_login_cookies()

            if not any(c['name'] == 'sesid' for c in cookies):
                print(f"[-] No sesid cookie — login may have failed. Retrying ({attempt}/{MAX_RETRIES})...")
                time.sleep(5)
                continue

            # Step 2: FlareSolverr solves Turnstile
            result_cookies, html = solve_with_flaresolverr(cookies, attempt)

            if result_cookies is not None:
                print("\n[+] ACCESS GRANTED to workshop!")
                print(f"[+] Workshop URL: https://webdatabays.com/workshop/touch/site/layout/makesOverview")

                # Save cookies for further use
                import json
                with open('/tmp/workshop_cookies.json', 'w') as f:
                    json.dump(result_cookies, f, indent=2)
                print("[+] Cookies saved to /tmp/workshop_cookies.json")
                sys.exit(0)
            else:
                print(f"[-] FlareSolverr failed on attempt {attempt}. Waiting 10s...")
                time.sleep(10)

        except Exception as e:
            print(f"[-] Exception on attempt {attempt}: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(10)

    print("[-] All attempts failed. Check FlareSolverr logs: /tmp/flaresolverr.log")
    sys.exit(1)


if __name__ == "__main__":
    main()
