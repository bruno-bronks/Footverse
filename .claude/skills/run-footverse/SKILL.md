---
description: Launch and drive the Footverse app (FastAPI backend + Vite/React frontend) for manual testing or smoke verification. Use when asked to run, start, or screenshot Footverse, or to confirm a change works end-to-end (not just unit tests).
---

# Running Footverse

Two processes: FastAPI backend (port 8000) + Vite dev server (port 5173, proxies
API calls to 8000). Both must be running for the frontend to work.

## Setup (once per environment)

```bash
pip install -e ".[api,agents]"
cd frontend && npm install
```

Copy `.env.example` to `.env` in the repo root and fill in `OPENAI_API_KEY` if you
need to exercise the agent layer (Scout/Coach/Finance/ClubManager) for real. Without
it, everything except `/ask/*` and `/admin/clubs/{id}/run-ai` still works.

## Run

**Backend** — ⚠️ the uvicorn target MUST be `footverse.api.app:app`, NOT
`footverse.api:app`. The package `footverse/api/__init__.py` only exports
`create_app` (not `app`), so `footverse.api:app` resolves to the **submodule**
`footverse.api.app` itself (not the FastAPI instance inside it), and uvicorn fails
with `TypeError: 'module' object is not callable`.

```bash
set -a && source .env && set +a   # load env vars (bash)
python -m uvicorn footverse.api.app:app --host 127.0.0.1 --port 8000 &
```

Wait for readiness, then verify:
```bash
curl -sf http://127.0.0.1:8000/ && echo OK
# → {"app":"Footverse","version":"0.1.0","fase":3}
```

**Frontend**:
```bash
cd frontend && npm run dev &
```
Vite binds to `localhost:5173`. Use `http://localhost:5173` (not `127.0.0.1` —
in this environment Vite's IPv6/`::1` binding made `127.0.0.1` unreachable while
`localhost` worked fine).

Check `frontend/vite.config.ts`'s `server.proxy` covers every API prefix the
frontend calls: `/clubs`, `/market`, `/auth`, `/divisions`, `/admin`. If you add a
new top-level route to `footverse/api/app.py`, add its prefix here too — `/auth`
and `/divisions` were missing for a long time after Phase 2/3 added them, causing
silent 404s in dev only (production build doesn't need the proxy since the API
serves the built frontend directly).

**Stop** (Windows):
```powershell
Get-NetTCPConnection -LocalPort 8000,5173 -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
```

## State is in-memory and shared across requests

`World` (in-memory `Store`) lives for the lifetime of the backend process. The
market (50 NPC players) is generated once at startup and **shrinks as it's
bought from** — running the same manual test twice without restarting the
backend means fewer/different players available the second time (e.g., the
guaranteed minimum of 6 GOL players can run out). **Restart the backend between
independent test runs** if you need a fresh market:

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
```
then relaunch uvicorn as above. (Setting `DATABASE_URL` switches to `SqlStore`,
which persists across restarts via SQLite/Postgres — delete the `.db` file
instead if you need a clean slate in that mode.)

## Drive it: Playwright (Python) smoke test

`chromium-cli` is not available in this environment. Use Python's `playwright`
package directly (already installed; verify with
`python -c "from playwright.sync_api import sync_playwright"`).

Golden path that exercises the full loop — auth → club → market → squad →
lineup → round → standings:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    page.goto("http://localhost:5173/")
    page.wait_for_selector("text=Footverse")
    page.click("text=Criar conta e obter chave API")
    page.wait_for_selector("text=Continuar"); page.click("text=Continuar")
    page.fill("input[placeholder='Ex: Atlético Futuro']", "Smoke Test FC")
    page.click("button:has-text('Criar clube')")
    page.wait_for_selector("text=Smoke Test FC")
    page.screenshot(path="dashboard.png")

    print("console errors:", errors or "none")
    browser.close()
```

### Gotchas hit while writing this

- **Buying players by clicking "first match" races the network.** The buy
  button's row doesn't disappear from the DOM until the `POST .../transfers`
  response comes back. Looping "click first row of sector X" without waiting
  for that response can hit the *same* row twice, double-clicking one player
  and silently failing the second click (already owned). Wrap each click in
  `with page.expect_response(lambda r: "/transfers" in r.url): ...` and check
  `resp.status == 201` before counting it as bought.
- **MarketTab sorts each sector by OVR descending** (priciest first), not by
  price. A naive "buy first row" loop buys the *most expensive* players,
  which can exhaust the FV$50M starting budget before reaching later sectors
  (manifests as `402 INSUFFICIENT_FUNDS`, not a bug). Use `rows.nth(count-1)`
  (last row = cheapest in that sector) when budget matters, mirroring
  `tests/_montar_xi` helpers in the pytest suite.
- **`<select>` dropdowns in LineupTab re-render between picks.** Reading
  `option` values for all 11 slots up front and assigning them without
  waiting for each `select_option()` to settle can make the app legitimately
  move a player you already assigned to a different slot (the app removes a
  player from any prior slot when you reassign it — by design). Add a short
  `wait_for_timeout(200-300)` between each slot assignment.
- **`GET /clubs/{id}/lineup` 404s when no lineup is set yet — this is
  intentional** and already handled by the frontend (`.catch(() => null)`).
  Chrome's console still logs the underlying failed network request as an
  "error" even though the app handles it gracefully; don't treat every
  console 404 as a real bug without checking what endpoint it is and whether
  the call site catches it.
- **SSE endpoints (`/clubs/{id}/events`) hang under `TestClient`/sync
  Playwright `page.locator(...).click()` patterns that wait for full
  response.** Don't try to assert on the live stream directly in a quick
  script; either test the publish-side logic directly (call the publish
  function with a fake subscriber queue) or use `page.expect_response` with
  a short timeout and accept partial reads.
