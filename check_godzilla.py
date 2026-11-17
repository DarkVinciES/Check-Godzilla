#!/usr/bin/env python3
"""
Watches Scope Cinemas (Sri Lanka) for a Godzilla Minus Zero listing and sends
one phone alert per page: when it first appears on Coming Soon, and again when
it appears on Now Showing (tickets out). found.txt records which pages alerted.

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
    attrs = " ".join(v for _, v in re.findall(
        r"""(?i)(?:alt|title)\s*=\s*(["'])(.*?)\1""", raw_html))
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


# One alert per page. Now Showing is the "tickets are out" alert.
ALERTS = {
    "Coming Soon": ("GODZILLA is listed as Coming Soon on Scope!",
                    "Tickets may not be on sale yet. You'll get another alert "
                    "when it moves to Now Showing."),
    "Now Showing": ("GODZILLA tickets are out on Scope Cinemas!",
                    "It's on Now Showing. Go book tickets!"),
}


def load_state() -> dict:
    """Pages already alerted, as {page: {"at": ..., "snippets": [...]}}."""
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, encoding="utf-8") as f:
        raw = f.read()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except ValueError:
        pass
    # Old format (one alert for any page): "<time> UTC" line + {page: snippets} line.
    lines = raw.splitlines()
    for line in lines:
        try:
            old = json.loads(line)
        except ValueError:
            continue
        if isinstance(old, dict) and old:
            at = lines[0] if lines else ""
            return {page: {"at": at, "snippets": s} for page, s in old.items()}
    return {"Coming Soon": {"at": raw.strip(), "snippets": []}}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def check_once() -> bool:
    """Returns True when every page has been alerted (nothing left to watch)."""
    state = load_state()
    pending = {n: u for n, u in PAGES.items() if n not in state}
    if not pending:
        print("Already alerted for every page (see found.txt). Delete it to re-arm.")
        return True
    for name in PAGES:
        if name in state:
            print(f"{name}: already alerted at {state[name].get('at', '?')}")

    hits = {}
    errors = []
    for name, url in pending.items():
        try:
            matches = find_matches(page_text(fetch(url)))
            print(f"{name}: {'FOUND' if matches else 'not listed yet'}")
            if matches:
                hits[name] = (url, matches)
        except Exception as e:  # keep checking the other page
            errors.append(f"{name}: {e}")
            print(f"{name}: ERROR {e}")

    if hits:
        # If both turn up in the same run, send one alert using the tickets wording.
        main_page = "Now Showing" if "Now Showing" in hits else next(iter(hits))
        title, note = ALERTS[main_page]
        detail = "\n".join(f"[{n}] {s}" for n, (_, ms) in hits.items() for s in ms)
        notify(title, f"Listed on: {' and '.join(hits)}\n\n{detail}\n\n{note}",
               hits[main_page][0])
        now = time.strftime("%Y-%m-%d %H:%M:%S") + " UTC"
        for name, (_, ms) in hits.items():
            state[name] = {"at": now, "snippets": ms}
        save_state(state)
        return all(n in state for n in PAGES)

    if len(errors) == len(pending):
        # Every page still being watched failed: fail loudly so GitHub emails you.
        sys.exit("Could not load the page(s):\n" + "\n".join(errors))
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
                    print("Alerted for every page. Stopping the loop.")
                    return
            except SystemExit as e:
                print(e)  # keep looping on network errors in PC mode
            time.sleep(minutes * 60)
    check_once()


if __name__ == "__main__":
    main()
