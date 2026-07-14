# Dev Log — How This App Was Built

A note on this document: there's no git history or session transcript to pull a literal commit-by-commit timeline from — this repo is being initialized for the first time, from code that already existed on disk. What follows is a walkthrough of what's actually in `app.py` and `usage_guard.py`, organized in the logical build order the code itself implies (core feature first, hardening and polish layered on after — visible from in-code comments like the one on the XSS fix below). Treat it as an architecture explanation rather than a literal diff-by-diff history.

## 1. Core concept

The base idea: patients get discharge instructions and clinical notes full of jargon they can't parse. The app's job is narrow — take medical text in, hand back the same information in plain language, at a chosen reading level, in a chosen language.

This lives in the **Simplifier** tab (`tab1`). It calls the Anthropic API (`client.messages.create`, Claude Sonnet) with a system prompt that scopes the model to one job — simplify medical text — and a user prompt built from four knobs:

- **Output language** — 24 options (`LANGUAGES` dict), from English through Urdu, Dari, Japanese, and later Bengali, Telugu, Tamil, and Malayalam, followed by Russian, Haitian Creole, Gujarati, and Nepali. (Fixed during repo setup: the hero banner used to hardcode "13 Languages," out of sync with the actual list. It now reads `len(LANGUAGES)` dynamically, so it can't drift again — adding these languages required no other code change.)
- **Tone** — warm & reassuring / clinical & clear / child-friendly.
- **Reading level** — a grade 2–8 slider, or a "bullet points only" mode for very low literacy that caps bullets at 8 words.
- **Follow-up questions** — an optional "Questions to Ask Your Doctor" section appended by the model and then split back out in code so it renders in its own card.

## 2. Input handling

Two input paths: paste text, or upload a `.txt`/`.pdf`. Both converge on the same `input_text` variable before hitting the API, which is where the security layer (next section) hooks in. PDF text extraction uses `pypdf`.

## 3. Security hardening

This is the layer that turns a toy demo into something safe to put in front of the public internet with a real API key behind it. Several distinct concerns, each handled separately:

**Input sanitization** (`sanitize_input`) — strips control characters and HTML/script tags from anything before it reaches the model or the page.

**Prompt-injection screening** (`check_prompt_injection`, `INJECTION_PATTERNS`) — a heuristic regex screen for the obvious jailbreak phrasing ("ignore previous instructions," "you are now," "DAN," "pretend you," etc.). This is explicitly a heuristic, not a guarantee — it's backed up by a system prompt that tells the model to treat the entire medical-text field as data, never as instructions, and to refuse and bounce back a fixed message if the input looks like it's trying to direct the model rather than describe a patient's care.

**PHI pattern screening** (`check_for_phi_warning`) — regex checks for SSN-shaped numbers, 10-digit strings that look like MRNs, email addresses, phone numbers, and DOB-shaped dates. If any hit, submission is blocked with a specific message naming what was detected, before anything is sent to the API.

**File upload validation** (`validate_file_magic`) — browser-reported MIME type is trivially spoofable, so uploads are checked by magic bytes instead (`%PDF` header for PDFs, UTF-8 decodability for text), on top of a 2MB size cap.

**Rate limiting, two layers** (`usage_guard.py`) — a per-session 30-second cooldown (`CooldownTracker`) stops rapid-fire resubmission from one user, and an app-wide daily request counter (`DAILY_REQUEST_LIMIT = 100`, backed by a JSON file) caps total API spend across every visitor regardless of session. The module's own docstring is explicit that this is a *soft* backstop — the real one is the spend limit set directly in the Anthropic Console, since a filesystem counter resets if the host redeploys.

**Output escaping / a specific XSS fix** — every value interpolated into rendered HTML (`html.escape(...)`) is escaped before display. The jargon-highlighting code path has an explicit inline comment marking a fix: *"HTML-escape FIRST, then apply markdown highlight syntax on top. This closes the self-XSS path in the jargon branch where the non-escaped path previously bypassed html.escape()."* In other words, an earlier version of the highlighter ran the bolding/highlight replacement on raw text before escaping it, which meant unescaped user input could reach the page. The fix reorders it: escape first, then layer the `**:orange[term]**` markdown syntax on top of the already-safe string.

**No raw errors surfaced** — API/PDF failures are caught, logged to server-side console (`print(f"[ERROR] ...")`), and the user only ever sees a generic "something went wrong" message — no stack traces or internal details leak into the UI.

**A consent gate** — before any tab is reachable, a disclaimer screen requires an explicit click-through acknowledging the app isn't HIPAA-certified, PHI shouldn't be entered, and text isn't stored. This isn't decorative — `st.stop()` halts rendering of everything else until `disclaimer_accepted` is set.

## 4. Word Match game

A second tab, unrelated to the simplifier's core loop but sharing its design system: a Duolingo-style matching game (`ALL_TERM_PAIRS`, `new_game_round`, `check_match`) where the player taps a medical term, then taps its plain-English definition. Score, streak, and best-streak are tracked in session state; five pairs per round are drawn from a pool of ~30, with a wraparound so it doesn't run out. Correct matches award points and build a streak counter that changes color/emoji past 3 in a row; incorrect matches reset the streak and reveal the right answer inline. This reinforces the same vocabulary the simplifier is built around, framed as practice rather than lookup.

**A latent bug, fixed during repo setup:** `ALL_TERM_PAIRS` contained "Benign" twice, with two different definitions ("Not cancerous / not harmful" and "Not cancerous"). If `random.sample` happened to draw both entries into the same round, `game_left_order` would end up with "Benign" twice, and the two term-card buttons would both be keyed `left_Benign` — Streamlit requires unique widget keys per render, so this would have crashed the game with a duplicate-element-ID error. It was intermittent (only triggered if both "Benign" tuples got drawn together in the same round), which is probably why it hadn't surfaced yet. The duplicate entry has been removed.

## 5. History and About tabs

**History** (`tab3`) — a session-scoped log of past simplifications (timestamp, language, tone, grade, truncated original/result). Explicitly not persisted — cleared when the browser tab closes, which is called out both in the UI copy and the disclaimer.

**About** (`tab4`) — originally held both the health-equity case for the project (literacy statistics, disparities by race/income/language/geography, sourced citations) *and* a plain-language security/privacy summary. The external research and citations were removed from the tab; The tab itself covers what the app is and the security model above.

## 6. Output and export

Results render in three cards — original (with jargon terms highlighted inline), simplified, and questions-to-ask — followed by download options: a `.txt` export always, and a `.pdf` export (via `fpdf2`) for Latin-script languages only, since the default font can't render non-Latin scripts. PDF generation writes to a temp file and explicitly cleans it up in a `finally` block regardless of success.

## 7. Visual design system

A single `<style>` block defines CSS custom properties for light and dark mode (`:root` vs `[data-theme="dark"]`), so every component — cards, buttons, tabs, the game's term cards — pulls color from tokens rather than hardcoded values. Two typefaces (Playfair Display for headings, DM Sans for body/UI), a teal-to-coral gradient used consistently across the hero banner and the game header, and a mobile breakpoint at 640px.

## Summary of the security posture

| Concern | Mitigation |
|---|---|
| Prompt injection | Regex heuristic screen + system prompt instructing the model to treat input as data only |
| PHI exposure | Regex screen blocks submission on SSN/MRN/email/phone/DOB patterns |
| XSS | All interpolated output HTML-escaped; highlighter fixed to escape before styling |
| Malicious file upload | Magic-byte validation instead of trusting MIME type; 2MB cap |
| API cost abuse | Per-session cooldown + app-wide daily cap (soft) + Anthropic Console spend limit (hard) |
| Information leakage via errors | Errors logged server-side only; generic message shown to users |
| Data persistence | No database; history is session-only; explicit no-PHI disclaimer gate |

Not covered, and worth knowing if this ever moves past demo status: no authentication, no HIPAA-eligible infrastructure/BAAs, and the daily usage counter is a local JSON file that won't survive a multi-instance deployment or a redeploy — both acceptable trade-offs for a single-instance portfolio demo, not for production clinical use.

## Repo setup changes (this session, actually tracked)

Unlike the rest of this doc, these are real changes made while preparing the repo — not reconstruction:

- Fixed the hardcoded "13 Languages" hero text to read `len(LANGUAGES)` dynamically (was out of sync with the actual 16-entry list).
- Removed the duplicate "Benign" entry from `ALL_TERM_PAIRS` (latent crash risk in the Word Match game, described above).
- Removed the About tab's external research/citations from `app.py`; the tab now only covers what the app is and its security/privacy model.
- Added `requirements.txt`, `README.md`, `LICENSE` (MIT), and this file.
