"""
usage_guard.py
Lightweight, dependency-free usage controls for a free-tier Streamlit deployment.

This is intentionally simple: a JSON file on local disk tracks how many
Anthropic API calls have been made "today" across ALL users of this app.
Once the daily ceiling is hit, every user sees a friendly limit message
instead of triggering another paid API call.

This is a SOFT, app-level backstop. The HARD backstop is the spend limit
you set directly in the Anthropic Console — that one can't be bypassed by
restarting the app, clearing cookies, or anything else. Always keep both.

Notes on the Streamlit Community Cloud environment:
- The filesystem is ephemeral and resets when the app restarts or redeploys.
  Worst case, the counter resets early and you get a slightly more generous
  day than intended — never less safe, just occasionally less precise.
- This approach does NOT require any new account, database, or paid service.
"""

import json
import os
import time
import datetime

USAGE_FILE = os.path.join(os.path.dirname(__file__), ".usage_counter.json")

# Tune this to whatever daily budget feels comfortable for a portfolio demo.
# At ~1500 max_tokens/request, 100 requests/day keeps cost predictable
# while still letting plenty of real visitors try the demo.
DAILY_REQUEST_LIMIT = 100


def _today_str():
    return datetime.date.today().isoformat()


def _read_counter():
    if not os.path.exists(USAGE_FILE):
        return {"date": _today_str(), "count": 0}
    try:
        with open(USAGE_FILE, "r") as f:
            data = json.load(f)
        if data.get("date") != _today_str():
            # New day — reset
            return {"date": _today_str(), "count": 0}
        return data
    except (json.JSONDecodeError, OSError):
        # If the file is corrupted or unreadable, fail safe by resetting
        # rather than crashing the app.
        return {"date": _today_str(), "count": 0}


def _write_counter(data):
    try:
        with open(USAGE_FILE, "w") as f:
            json.dump(data, f)
    except OSError:
        # If we can't write, we silently continue — the Console spend cap
        # is still the real backstop, so this never blocks the app entirely.
        pass


def check_daily_limit():
    """Returns (allowed: bool, remaining: int, limit: int)."""
    data = _read_counter()
    remaining = DAILY_REQUEST_LIMIT - data["count"]
    return remaining > 0, max(remaining, 0), DAILY_REQUEST_LIMIT


def record_request():
    """Call this immediately after a successful (or attempted) API call."""
    data = _read_counter()
    data["count"] += 1
    _write_counter(data)


class CooldownTracker:
    """
    Per-session cooldown, kept as a second, independent layer.
    This does not replace the daily cap — it just slows down rapid-fire
    submissions from a single active session as an additional layer.
    """

    def __init__(self, session_state, seconds=30):
        self.session_state = session_state
        self.seconds = seconds

    def check(self):
        now = time.time()
        last = self.session_state.get("last_submission_time", 0)
        if now - last < self.seconds:
            remaining = int(self.seconds - (now - last))
            return False, remaining
        return True, 0

    def record(self):
        self.session_state["last_submission_time"] = time.time()