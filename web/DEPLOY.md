# Native pages on thetrademarkhelpline.com — deploy & handoff

Goal: the report is a **real page on the domain** (real URL, real SEO, native
look), not an embedded app. We do that by splitting the finished engine from
its front end:

```
  thetrademarkhelpline.com/industry-report   (WordPress page: report.html)
                    │  fetch() JSON
                    ▼
  api.thetrademarkhelpline.com               (Cloud Run: the Python engine)
                    │
                    ▼
  Temmy + Companies House
```

Nothing about the engine changed — `api/main.py` imports the same
`data_access`, `recommend`, `viability`, `resolve`, `brandkit`, `assessment`
the Streamlit app uses. One source of truth; the Streamlit app can stay up as
the internal tool while the public pages run off the API.

---

## What you're deploying

| Piece | What it is | Where it goes |
|---|---|---|
| `api/` | FastAPI app wrapping the engine | Cloud Run → `api.thetrademarkhelpline.com` |
| `web/report.html` | The native page (self-contained, no build step) | WordPress page, Custom HTML block |
| `web/braudit.css` | The stylesheet (already the app's) | served next to the page (or via the API) |
| `web/brand/` | logo + owl characters | served next to the page |

---

## No DNS yet? You are not blocked.

The `api.thetrademarkhelpline.com` subdomain is **cosmetic**. The page calls
the API from the visitor's browser in the background — nobody ever sees the
URL. Every Python host gives you a working HTTPS address the moment you deploy
(`something.onrender.com`, `something.run.app`, …). Point the page at *that*,
ship, and swap in the pretty subdomain later by changing one line — no
re-deploy of the page needed.

What each piece actually needs:

| Piece | Needs | Have it? |
|---|---|---|
| The page (`report.html` + assets) | **WP-Admin only** | ✅ yes |
| The API (Python) | *any* Python host — **DNS not required** | one signup |

So the single outstanding thing is somewhere to run the Python. WP-Admin can't
(WordPress is PHP), but the host's default HTTPS URL is enough.

### Easiest Python hosts (pick one — all give HTTPS, none need DNS)

- **Render** (render.com) — connect the GitHub repo, "New Web Service", root
  `goal3-industry-report`, start command
  `uvicorn api.main:app --host 0.0.0.0 --port $PORT`. Free tier sleeps when
  idle (first hit after a nap is slow); ~£6/mo keeps it warm.
- **Railway** (railway.app) — same idea, deploy from repo, add the env vars.
- **Google Cloud Run** — the command below; scales to zero, effectively free,
  but needs a Google Cloud signup.

Whichever you choose, set the same env vars (keys from
`temmy-access/secrets.env`) plus
`CORS_ORIGINS=https://www.thetrademarkhelpline.com,https://thetrademarkhelpline.com`.
Then confirm `GET <host>/health` returns `{"ok": true, "sector": true}` and
use that host URL as `TMH_API_BASE` in Step 2.

---

## Step 1 (optional, later) — Cloud Run with the pretty subdomain

Only when Cloudflare/DNS access is back. Cloud Run is the cheapest fit
(scales to zero, ~£0 when idle). From the repo root:

```bash
gcloud run deploy tmh-report-api \
  --source . \
  --region europe-west2 \
  --allow-unauthenticated \
  --set-env-vars "TEMMY_API_BASE_URL=…,TEMMY_API_KEY=…,TEMMY_QUERY_RUNS_API_KEY=…,COMPANIES_HOUSE_API_KEY=…,CORS_ORIGINS=https://www.thetrademarkhelpline.com,https://thetrademarkhelpline.com"
```

- The Dockerfile (`api/Dockerfile`) copies the whole app so the engine imports
  resolve; it binds to Cloud Run's `$PORT`.
- **Secrets do not go in this file or in Git.** Set them with
  `--set-env-vars` (or, better, Secret Manager). They're the same keys from
  `temmy-access/secrets.env`.
- Cloud Run gives you a URL like `https://tmh-report-api-xxxx.run.app`.
  Confirm `GET /health` returns `{"ok": true, "sector": true}`.

### Point the subdomain at it (DNS — your part)

In your DNS, map `api.thetrademarkhelpline.com` to the Cloud Run service:

1. Cloud Run → the service → **Manage custom domains** → add
   `api.thetrademarkhelpline.com`. Google gives you a DNS record to add.
2. Add that record (a CNAME to `ghs.googlehosted.com`, or the exact target
   Google shows) in your DNS.
3. Google issues the TLS cert automatically once the record resolves.

---

## Step 2 — Put the page on WordPress

The page is one file and depends only on `braudit.css` + `brand/` + the API.

1. **Host the assets.** Upload `braudit.css` and the `brand/` folder to the
   site (Media library, or `/wp-content/uploads/tmh/`). Note the URLs.
2. **Create the page.** New WordPress page, title *Industry Trademark Report*,
   permalink `/industry-report/`. In Elementor add an **HTML widget** (or a
   Gutenberg **Custom HTML** block) and paste the contents of `report.html`.
3. **Set the three URLs** by adding this *above* the pasted markup. Use your
   host's URL for `TMH_API_BASE` — the `.onrender.com` / `.run.app` address is
   fine; it does not have to be the subdomain:

   ```html
   <script>
     // Whatever your Python host gave you. Swap for the subdomain later.
     window.TMH_API_BASE = "https://tmh-report-api.onrender.com";
     window.TMH_ASSETS   = "https://www.thetrademarkhelpline.com/wp-content/uploads/tmh/brand";
   </script>
   ```

   and change the `<link rel="stylesheet" href="./braudit.css">` line in the
   markup to the uploaded stylesheet's URL.

   **When DNS comes back:** change `TMH_API_BASE` to
   `https://api.thetrademarkhelpline.com` and save the page. Nothing else moves.

That's it — the page renders inside your normal header/footer, because it's a
normal page. The report itself sits in the `.bd` scope so it won't fight
Elementor's styles, and vice-versa.

---

## Why this shape (worth keeping in mind)

- **SEO:** the page is server-delivered HTML on your domain, so Google sees the
  content — unlike an iframed app. The sector data loads client-side (it's
  personalised, not indexable), but the page, its copy and its headings are.
- **Magic links:** `/industry-report/?company=13327422` can pre-load a company
  — same idea as the app's magic link, now a real URL you can email.
- **Partner embeds:** the same `report.html` works on a partner site by
  pointing `TMH_API_BASE` at the API and adding their origin to `CORS_ORIGINS`.
  This is the free-search "one embeddable file" pattern, extended to the report.
- **The engine stays one thing.** A change to banding or viability is one
  deploy of the API; every surface (Streamlit, this page, partner embeds)
  follows.

---

## What's built vs. what's next

**Built and proven against the live engine (this slice):**
- The API: `/find`, `/owner-marks`, `/company/{n}`, `/sector`, `/classes`,
  `/terms`, `/viability`, `/assessment`, `/business-types`, `/health`.
- `report.html`: **Input 1 → Build 1 → Reveal 1** (the free sector one-pager),
  rendering entirely from API data.

**Next slice (the tailored half):**
- Input 2 (classes + the 3 questions), Build 2, Reveal 2 (viability dials,
  risk table, kept classes, assessment result, offer, urgency).
- All the API endpoints those screens need already exist — it's front-end
  wiring, the same pattern as Reveal 1.

Ship the API + this page first; it's the whole free experience and it proves
the domain/DNS/WordPress path before the bigger screen is built on top.
