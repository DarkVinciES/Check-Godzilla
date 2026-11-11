#!/usr/bin/env python3
"""
Watches Scope Cinemas (Sri Lanka) for a Godzilla Minus Zero listing and sends
a phone alert when it appears on the Coming Soon or Now Showing page.

Alerts go to:
  - ntfy (free phone push app)  -> set env NTFY_TOPIC
  - Telegram (optional)         -> set env TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID

Usage:
  python check_godzilla.py            # check once (used by GitHub Actions)
  python check_godzilla.py --test     # send a test alert to check your phone setup
  python check_godzilla.py --loop 10  # PC mode: check every 10 minutes forever
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

PAGES = {
    "Coming Soon": "https://www.scopecinemas.com/movies/coming-soon",
    "Now Showing": "https://www.scopecinemas.com/movies/now-showing",
}

# Any "Godzilla" mention triggers, so a listing titled "GODZILLA -0.0" or
# "GODZILLA MINUS ZERO (IMAX)" is still caught.
KEYWORD = re.compile(r"godzilla", re.IGNORECASE)

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "found.txt")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def page_text(raw_html: str) -> str:
    """Drop scripts/styles and tags, keep visible text plus alt/title attributes."""
    raw_html = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", raw_html)
    attrs = " ".join(re.findall(r'(?i)(?:alt|title)\s*=\s*"([^"]*)"', raw_html))
    text = re.sub(r"(?s)<[^>]+>", " ", raw_html)
    return html.unescape(re.sub(r"\s+", " ", text + " " + attrs))


def find_matches(text: str) -> list[str]:
    """Return short snippets around each Godzilla mention."""
    snippets = []
    for m in KEYWORD.finditer(text):
        s = text[max(0, m.start() - 40): m.end() + 60].strip()
        if s not in snippets:
            snippets.append(s)
    return snippets[:3]


def notify(title: str, message: str, click_url: str) -> None:
    sent = False
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if topic:
        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers={
                "Title": title.encode("ascii", "ignore").decode(),
                "Priority": "urgent",
                "Tags": "rotating_light,movie_camera",
                "Click": click_url,
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=30).read()
        print("ntfy alert sent")
        sent = True

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if token and chat_id:
        body = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": f"{title}\n\n{message}\n\n{click_url}",
        }).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage", data=body, timeout=30
        ).read()
        print("Telegram alert sent")
        sent = True

    if not sent:
        print("WARNING: no alert channel set (NTFY_TOPIC or TELEGRAM_*). Printing only.")
        print(title, message, click_url, sep="\n")


def check_once() -> bool:
    """Returns True if Godzilla was found (and alerted) this run."""
    if os.path.exists(STATE_FILE):
        print("Already alerted earlier (found.txt exists). Delete it to re-arm.")
        return True

    hits = {}
    errors = []
    for name, url in PAGES.items():
        try:
            matches = find_matches(page_text(fetch(url)))
            print(f"{name}: {'FOUND' if matches else 'not listed yet'}")
            if matches:
                hits[name] = (url, matches)
        except Exception as e:  # keep checking the other page
            errors.append(f"{name}: {e}")
            print(f"{name}: ERROR {e}")

    if hits:
        where = " and ".join(hits)
        first_url = next(iter(hits.values()))[0]
        detail = "\n".join(f"[{n}] {s}" for n, (_, ms) in hits.items() for s in ms)
        notify(
            "GODZILLA is on Scope Cinemas!",
            f"Listed on: {where}\n\n{detail}\n\nGo book tickets!",
            first_url,
        )
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} UTC\n{json.dumps({k: v[1] for k, v in hits.items()}, ensure_ascii=False)}\n")
        return True

    if len(errors) == len(PAGES):
        # Both pages failed: fail loudly so GitHub emails you about the broken run.
        sys.exit("Could not load either page:\n" + "\n".join(errors))
    return False


def main() -> None:
    args = sys.argv[1:]
    if "--test" in args:
        notify("Godzilla watcher: test alert",
               "If you can see this, alerts are working.",
               PAGES["Coming Soon"])
        return
    if "--loop" in args:
        i = args.index("--loop")
        minutes = int(args[i + 1]) if len(args) > i + 1 else 10
        while True:
            print(time.strftime("%Y-%m-%d %H:%M:%S"), "checking...")
            try:
                if check_once():
                    print("Found it. Stopping the loop.")
                    return
            except SystemExit as e:
                print(e)  # keep looping on network errors in PC mode
            time.sleep(minutes * 60)
    check_once()


if __name__ == "__main__":
    main()
