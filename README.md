# Godzilla Minus Zero ticket watcher (Scope Cinemas)

Checks these two pages every 10 minutes and pushes an alert to your phone when "Godzilla" shows up on either:

- https://www.scopecinemas.com/movies/coming-soon
- https://www.scopecinemas.com/movies/now-showing

It alerts **once**, then saves `found.txt` so you aren't spammed. Delete `found.txt` to re-arm it.

## Setup (GitHub, about 5 minutes, free, runs with your PC off)

1. **Phone app:** Install **ntfy** (Android Play Store / iOS App Store). Tap **+** and subscribe to a topic name that's hard to guess, e.g. `godzilla-lk-7f3k92`. Anyone who knows the name can read it, so don't use something simple.
2. **Repo:** On GitHub, create a new repository (make it **Public**: scheduled runs are unlimited and free on public repos). Upload `check_godzilla.py`, `README.md` and the `.github/workflows/godzilla-watch.yml` file, keeping that folder path exactly.
   - Easiest way: unzip the zip, then on the repo page click **Add file → Upload files** and drag the whole unzipped folder contents in.
3. **Secret:** Repo → **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `NTFY_TOPIC`  Value: your topic name (e.g. `godzilla-lk-7f3k92`)
4. **Test:** Repo → **Actions** tab → enable workflows if asked → **Godzilla ticket watcher → Run workflow** → tick **Send a test alert** → Run. Your phone should buzz within a minute.
5. Done. It now runs every 10 minutes by itself. You can watch runs in the Actions tab.

### Optional: Telegram as well
Create a bot with @BotFather (gives a token), message your bot once, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your chat id. Add secrets `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

## Good to know
- GitHub's timer isn't exact: runs can be a few minutes late at busy times.
- GitHub pauses scheduled workflows in repos with **no activity for 60 days** and emails you first. If that happens, click "Enable workflow" in the Actions tab.
- If both pages fail to load, the run fails and GitHub emails you, so you'll know if the site blocks it or changes.
- It triggers on any "Godzilla" mention, so a listing like "GODZILLA -0.0 (IMAX)" is still caught.

## PC fallback
Needs Python 3.9+. No extra packages.

```
set NTFY_TOPIC=godzilla-lk-7f3k92        (Windows)   |   export NTFY_TOPIC=...   (Mac/Linux)
python check_godzilla.py --test           send a test alert
python check_godzilla.py --loop 10        check every 10 minutes until found
```
Keep the window open and the PC awake.
