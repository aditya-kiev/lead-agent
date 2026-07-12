# Demo Quick Start

## Which file to open

| Client type | File | VERTICAL |
|---|---|---|
| Real estate brokerage | `demo-realestate-pro.html` | `real_estate` |
| Insurance agency | `demo-insurance-pro.html` | `insurance` |

## Before you start

Set these in `.env` (copy from `.env.example`):

```
VERTICAL=real_estate       # or insurance
BUSINESS_NAME=Your Brokerage or Agency Name
ALLOWED_ORIGINS=["*"]      # required so the HTML can reach the API
GEMINI_API_KEY=your-key
```

## Run

```bash
uvicorn app.main:app --reload
```

Then open `demo-realestate-pro.html` or `demo-insurance-pro.html` directly
in a browser (double-click the file — no web server needed; CORS is
configured to allow `file://` origins).

## What to expect

1. The page auto-sends an opening message to start the conversation.
2. The bot replies and begins collecting lead info.
3. **The right panel fills in automatically** — name, budget, timeline, and
   status all appear as the lead talks. This is the "wow" moment: no forms,
   no manual entry.
4. Once enough info is collected, the bot scores the lead (hot/warm/cold)
   and offers to book a meeting.
5. The "✓ Meeting confirmed" badge only appears **after** the bot proposes
   specific times and the lead confirms — UI-side sanity check as a second
   line of defense.

## Verifying before a client call (5-minute checklist)

1. `pytest -v` — all tests green, especially the 4 CORS tests.
2. Open the correct `-pro` file and confirm:
   - Chat loads, auto-sends first message.
   - Bot never asks "what company do you work for" (individual-consumer
     default for real_estate/insurance verticals).
   - Budget captures correctly: type "$650,000" or "$150/month" and watch
     the record panel update.
   - Meeting "confirmed" badge only appears after a time-exchange in the
     chat (bot proposes slots, user says "that works").
   - Mobile layout: resize to ~400px wide — panels stack, everything still
     readable.
3. `access-control-allow-origin: *` is returned (test: open DevTools →
   Network tab, check response headers on the `/webhook/message` call).
