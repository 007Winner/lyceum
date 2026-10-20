# Submission audit — The Lyceum

Audited against the semester project specification on 2026-10-19.

| Requirement | Status | Evidence |
|---|---|---|
| Repo contains runnable app | PASS | `backend/`, `frontend/`, `requirements.txt`, `frontend/package.json` |
| README gives fresh-clone setup | PASS | Uvicorn, Vite, environment, corpus, and API instructions |
| Parent-folder `.env` supported | PASS | `backend/agents.py` loads repo `.env`, then parent `.env` |
| `.env.example` has no secrets | PASS | Lists only `PORTKEY_API_KEY` placeholder |
| Course model restriction | PASS | `MODEL_NAME = "gpt-6-luna"`, Portkey base URL |
| Report required sections | PASS | Agents, tools, organization, model, run, tokens, cost, cost controls, safety |
| Slides ≤10 slides | PASS | 10 Reveal.js sections |
| Screenshot embedded in report | PASS | Base64 PNG data URI from `platoscreenshot.png` |
| Screenshot embedded in slides | PASS | Same base64 PNG data URI |
| Safety evidence | PASS | Tests cover injection rejection and fail-closed evaluation |
| Automated tests | PASS | 8 `unittest` tests pass |
| Fresh-clone dry run | PASS | Clean copy used parent `.env`; Uvicorn health returned `{"status":"ok","app":"lyceumv4"}` |
| Exact provider invoice cost | NOT AVAILABLE | Official GPT-6 Luna/course rates are not exposed; report uses a clearly labeled illustrative scenario and formula |
| Tokenomics instrumentation | PASS | `backend/agents.py` logs provider usage around the philosopher and evaluator calls |
| Tokenomics analysis script | PASS | `analysis/analyze_costs.py` writes summary and PNG chart |
| Real bounded usage measurement | PASS | Three live calls: two philosopher calls and one evaluator call; evaluator returned `advanced: false` |
| Tokenomics report | PASS | `analysis/tokenomics_report.html` embeds its chart and states measured limits |
| Generated usage CSV privacy | PASS | `analysis/token_usage.csv` is Git-ignored; it contains session metadata but no prompts or responses |
| Frontend unchanged for tokenomics | PASS | No frontend files changed during instrumentation |
| Online deployment | NOT USED | README documents local run, within the 10-minute setup path |
| Public repository access | PASS | GitHub API confirms `007Winner/lyceum` is public on `main` |
| Author identity | PASS | Report and slides name Win Mordecai |

## Verification performed

- `\.venv\Scripts\python.exe -m unittest discover -s tests -v`: 8 tests passed.
- `frontend`: `npm run build` passed.
- `report.html` and `slides.html` each contain an embedded PNG data URI and no screenshot placeholder.
- `analysis/tokenomics_report.html` embeds its PNG chart and reports the three-call controlled run.
- No backend, prompt, evaluator, API contract, or gameplay files were changed for the deliverables pass.

## Final manual checks before Canvas submission

1. Clone the pushed repository into a clean directory. *(Completed locally in `C:\\Users\\wmord\\AppData\\Local\\Temp\\lyceum-dry-run`.)*
2. Put the course `.env` one level above the clone.
3. Follow README commands from a fresh PowerShell window.
4. Open the frontend, create a session, send one argument, and confirm a real response.
5. Double-click `report.html`; confirm the Plato screenshot appears.
6. Double-click `slides.html`; use arrow keys and `F` to test the deck.
7. Replace planning cost assumptions with measured Portkey invoice rates if the course requires exact dollars.

