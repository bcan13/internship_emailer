# intern_pos_emailer

A bot that **runs every 2 hours on GitHub Actions** and posts to **Discord** with new US
quant internship openings plus software / consulting new-grad openings.
It pulls from community internship aggregators and directly from company career
sites (via their ATS APIs), filters to what you care about, remembers what it has
already shown you, and only alerts on **new** postings.

```
sources (github lists + Greenhouse/Lever/Ashby/Workday)
   → normalize → filter (quant internship OR non-quant new-grad · category · US)
   → dedup vs data/seen_jobs.json
   → Discord webhook digest
   → commit updated state back to the repo
```

> Email (Gmail) and SMS (Twilio) are still supported but **off by default**.

## What it tracks
- **Roles:** quant internships; new-grad/full-time entry roles for everything else.
- **Categories:** software engineering, software development, quant dev, quant
  trading, big tech, unicorns, startups, consulting (tech tracks).
- **Location:** United States (incl. US-remote).

All of this is tunable in `config/` — no code changes needed.

## Layout
```
config/        # all tunables (no code): companies, github lists, filters, settings
src/sources/   # one module per source type (github lists + 4 ATS APIs)
src/filters.py # internship / season / category / US-location rules
src/dedup.py   # seen-jobs state (data/seen_jobs.json)
src/notify/    # discord.py (webhook) + optional email.py/SMS
src/apply/     # FUTURE auto-apply scaffold (not yet implemented)
src/main.py    # orchestrator + CLI
.github/workflows/daily.yml  # the scheduled cron
tests/         # pytest: filters + dedup
```

## Quick start (local)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# See what it would send today — fetches live sources, no email/SMS, no state write:
python -m src.main --dry-run
```

Add credentials to send for real:
```bash
cp .env.example .env      # then fill in DISCORD_WEBHOOK_URL
python -m src.main --test-notify   # sends one sample Discord notification
python -m src.main                 # full run
```

**First-run tip:** with an empty `data/seen_jobs.json`, the first real run will
post the *entire current backlog* (~hundreds of postings) in one digest. If you'd
rather start clean and only get *new* postings from then on, seed the state once:
```bash
python -m src.main --seed   # marks everything currently open as "seen", sends nothing
```

Run the tests:
```bash
pytest
```

## Credentials
Set these as **GitHub repo Secrets** (Settings → Secrets and variables → Actions),
and/or in a local `.env` (see `.env.example`). With none set, the bot still runs in
`--dry-run` and prints results.

| Secret | What it is |
| --- | --- |
| `DISCORD_WEBHOOK_URL` | Discord channel webhook URL |

That's the whole setup. In Discord, go to channel settings, Integrations, Webhooks,
then create/copy the webhook URL.

## Deploy (private repo + every-2-hours cron)
1. Create a **private** GitHub repo and push this project.
2. Add the `DISCORD_WEBHOOK_URL` secret.
3. (Optional) Run `python -m src.main --seed` locally once and commit the updated
   `data/seen_jobs.json`, so your first scheduled Discord post is a small delta rather than
   the whole backlog.
4. The workflow `.github/workflows/daily.yml` runs **every 2 hours** and also
   on-demand from the **Actions tab** (`workflow_dispatch`, with a dry-run toggle).
5. Each run commits the updated `data/seen_jobs.json` back to the repo, so the bot
   remembers what it already sent.

Notes:
- Private-repo Actions get 2,000 free minutes/month on GitHub Free. Running every 2 hours is about 360 runs/month; at ~1-3 minutes each, that is roughly 360-1,080 minutes/month, leaving a conservative buffer for manual runs or slower days.
- GitHub disables scheduled workflows after **60 days of no repo activity** — the recurring
  state commit normally counts, but you can also re-trigger manually to keep it alive.
- Adjust the cadence by editing the `cron:` line (it's in UTC).

## Tuning
- **`config/companies.yaml`** — add companies by ATS + token. Quant firms and
  consulting are seeded here because the community lists skew SWE. Some seed tokens
  are best-effort — run `--dry-run` and disable any that 404 (`enabled: false`).
- **`config/github_lists.yaml`** — the community `listings.json` URLs. These repos
  roll names each cycle (`Summer2026` → `Summer2027`); update the URL when the new
  cycle's repo appears.
- **`config/filters.yaml`** — role targets, keywords, allowed seasons/years, and US location terms.
- **`config/settings.yaml`** — Discord digest format, state pruning, suppression.

## Optional: Email
Email is still available through Gmail SMTP. To enable it:
1. In `config/settings.yaml`, set `email.enabled: true`.
2. Add `GMAIL_USER`, `GMAIL_APP_PASSWORD`, and `EMAIL_TO` as secrets / `.env` values.

## Optional: SMS
An SMS-nudge channel (`src/notify/sms.py`, via
Twilio) ships dormant. To enable it later:
1. In `config/settings.yaml`, set `sms.enabled: true`.
2. Uncomment `twilio>=8` in `requirements.txt` and reinstall.
3. Add `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM`, `SMS_TO` (E.164)
   as secrets / `.env` values, and uncomment them in `.github/workflows/daily.yml`.

It sends a short "N new roles today" text alongside the Discord digest. Twilio
costs a few cents per message.

## Auto-apply (local) — implemented
`src/apply/` is a working local tool that applies to the jobs the bot finds:
opens each Greenhouse / Lever / Ashby application form in a real browser, fills
your details, generates a tailored cover letter via Gemini 2.5 Flash, and
**auto-submits simple forms while pausing for your review on forms with custom
questions**.

```bash
pip install -r requirements.txt -r requirements-apply.txt
python -m playwright install chromium
python -m src.apply --prepare-only      # safe first run: fills but never submits
python -m src.apply                     # real run (visible browser)
```

Runs on your machine (not CI) so you can watch, solve CAPTCHAs, and review before
submit. It needs your resume in `resumes/`, a filled `config/profile.yaml` (copy
`config/profile.example.yaml`), and optionally `GEMINI_API_KEY` for cover letters.
Every attempt is logged to `data/applications.json` so re-runs never double-apply.

**See [APPLYING.md](APPLYING.md) for the full guide, modes, and what to provide.**

## Legal / etiquette
Uses official public JSON APIs (Greenhouse, Lever, Ashby, Workday) and open,
community-maintained data — no scraping of LinkedIn/Indeed or other anti-bot sites.
Requests are rate-limited and retried politely. Respect each site's Terms of Service.
