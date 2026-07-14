# health-literacy-app

A Streamlit web app that uses Claude to simplify medical text (discharge instructions, clinical notes) into plain language across 24 languages, with adjustable reading levels, PHI/prompt-injection safeguards, rate limiting, and a Duolingo-style medical vocabulary game. Built as a health informatics portfolio project.

Nearly 9 out of 10 adults in the United States struggle with health literacy, and limited health literacy can cause worsened health outcomes (Center for Health Care Strategies, 2024). Health literacy is also associated with other determinants of health, such as education, income, access to care, and area-based measures of social disadvantage; these determinants are key to disease prevention and controlling health disparities, making health literacy a health equity issue to be addressed (Coughlin et al., 2020).

## Features

- **Simplifier** — paste text or upload a `.txt`/`.pdf`, choose an output language, tone (warm/clinical/child-friendly), and target grade level (2–8, or bullet-points-only for very low literacy). Powered by Claude (Anthropic API).
- **Terminology highlighting** — flags medical terms found in the original text before showing the simplified version.
- **"Questions to ask your doctor"** — optional auto-generated follow-up questions.
- **Downloads** — export the result as `.txt` (always) or `.pdf` (Latin-script languages).
- **Word Match game** — a Duolingo-style matching game for learning common medical vocabulary, with score, streak, and accuracy tracking.
- **Session history** — a running log of what you've simplified this session (cleared on tab close, never persisted).
- **About tab** — what the app is, plus the security/privacy summary and HIPAA disclaimer.

## Security & privacy

This is a public demo, not a clinical tool. Guardrails in place:

- **No PHI storage** — text is sent to the Anthropic API for processing and discarded; nothing is written to a database.
- **PHI pattern screening** — heuristic scan blocks submission if it looks like it contains an SSN, phone number, email, medical record number, or date-of-birth pattern.
- **Prompt-injection screening** — checks pasted text for common phrases used to hijack AI instructions (like "ignore previous instructions") and blocks it before submission. As a backup, the AI itself is instructed to always treat the pasted text as content to simplify, never as commands to follow.
- **Input sanitization** — control characters and HTML/script tags stripped before processing; all rendered output is HTML-escaped.
- **File upload validation** — instead of trusting the file type your browser reports (which is easy to fake), the app checks the file's actual content to confirm it's really a PDF or text file. Uploads are also capped at 2MB.
- **Rate limiting** — a 30-second per-session cooldown plus an app-wide daily request cap (`usage_guard.py`) to keep API costs bounded regardless of traffic.
- **No raw errors exposed** — exceptions are logged server-side; users see a generic message.
- **Session-only history** — nothing persists across sessions or between users.

**Not HIPAA-certified.** Real clinical deployment would require HIPAA-eligible infrastructure and BAAs with all third-party services (including Anthropic). Do not enter real patient PHI.

## Tech stack

Python · Streamlit · Anthropic Claude API · textstat · fpdf2 · pypdf

## Setup

```bash
git clone https://github.com/<your-username>/health-literacy-app.git
cd health-literacy-app
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file (see `.env.example`) with your Anthropic API key:

```
ANTHROPIC_API_KEY=your_key_here
```

Run it:

```bash
streamlit run app.py
```

## Project structure

```
app.py            # Main Streamlit app — UI, security helpers, simplifier, game, history, about
usage_guard.py     # Daily request cap + per-session cooldown tracker
.streamlit/        # Streamlit config
.env.example        # Template for required environment variables
DEVLOG.md           # Architecture walkthrough
```

## How this was built

This app was built iteratively, not generated once and left alone. I directed development by prompting for features and fixes, testing the results, and making direct edits to the code myself throughout rather than being written once and handed off untouched.

What that process produced, layer by layer:

- **Core simplifier** — the base loop of taking medical text and rewriting it in plain language at a chosen reading level, tone, and language via the Anthropic API.
- **Security hardening** — added on top of the base app: input sanitization, PHI pattern screening, prompt-injection screening, file-upload magic-byte validation, layered rate limiting (`usage_guard.py`), and a fix that closed a self-XSS path in the jargon-highlighter (evidenced by an inline comment in `app.py` documenting the before/after).
- **Word Match game** — a second, separate feature (vocabulary-matching game) added afterward, sharing the app's design system.

## Disclaimer

For demonstration and educational purposes only. Not validated for clinical use, not a substitute for professional medical advice.

## References

Center for Health Care Strategies. (2024, March). *Health Literacy Fact Sheets* [Review of *Health Literacy Fact Sheets*]. Center for Health Care Strategies. https://www.chcs.org/resource/health-literacy-fact-sheets/

Coughlin, S. S., Vernon, M., Hatzigeorgiou, C., & George, V. (2020). Health literacy, Social Determinants of health, and Disease Prevention and Control. *Journal of Environment and Health Sciences*, *6*(1). https://pmc.ncbi.nlm.nih.gov/articles/PMC7889072/
