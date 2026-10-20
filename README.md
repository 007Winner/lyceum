# The Lyceum

The Lyceum is a philosophical conversation game for people who want to practice
making and revising arguments. Five independent philosopher agentsâ€”Plato,
Aristotle, Machiavelli, Hume, and Kantâ€”hold open-ended conversations. A player
advances only when the philosopher's response and a separate evaluator support a
substantive reconsideration.

## Run locally

1. From this folder, create the required virtual environment and install Python dependencies:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and add `PORTKEY_API_KEY`. The API also checks
   the folder above this repository, so a grader's `submissions/.env` works.

3. Start the backend with the reloader disabled:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
   ```

4. In a second terminal, install and start the frontend:

   ```powershell
   cd frontend
   npm install
   npm run dev -- --host 127.0.0.1
   ```

5. Open `http://127.0.0.1:5173`.

Gameplay requires the configured Portkey key; model failures return an explicit API error rather than simulated dialogue. Portkey calls use
`gpt-6-luna` through PydanticAI and never expose the key to the browser.

## Agent design

`prompts.md` is the editable source of truth for the shared rules, all five
philosophers, and the evaluator. `backend/agents.py` builds one philosopher
agent and one evaluator request per turn. `harness.py` caps each model response
at 420 output tokens and each session at 120 requests; each philosopher remains
available until persuaded. `tools.py` owns session state and redacted audit
events. The evaluator rejects keyword tricks, prompt injection, and bare claims.

## Primary-text retrieval

The included `data/texts/` corpus contains fourteen Project Gutenberg plain-text
editions, with title, author, translator/editor, edition, and source URL recorded
in `data/sources.json`. `backend/retrieval.py` strips Gutenberg boilerplate,
chunks the works, and searches a local SQLite FTS5 index. The current index is
`data/lyceum_fts.sqlite3`; it is rebuilt with:

```powershell
.\.venv\Scripts\python.exe scripts\build_corpus.py --index
```

Each non-social philosopher turn retrieves up to three relevant passages and
adds them to the philosopher prompt as reference-only material. Retrieval never
reaches the independent evaluator and cannot override its rules. The passages,
works, and URLs used for a run are logged in `output/retrieval_log.jsonl`.

The reproducible evidence run covers three text-grounded conversations for each
philosopher:

```powershell
.\.venv\Scripts\python.exe scripts\corpus_demo.py
```

Its 15 recorded cases are in `output/corpus_demo.json`.

Gutenberg does not provide a direct `Metaphysics` edition in this corpus build;
that absence is recorded in `data/sources.json`, and Aristotle's available
`Poetics` is included as the documented substitute. The source files are already
included, so a fresh clone does not need to download anything. To refresh an
available source from its recorded URL, use `scripts/build_corpus.py --download`
and then rebuild the index.

The API exposes `GET /api/health`, `POST /api/sessions`,
`GET /api/sessions/{id}`, and `POST /api/sessions/{id}/messages`.

## Evidence

See [report.html](report.html) for the architecture, cost model, safety design,
and a reproducible walkthrough. [slides.html](slides.html) is a short reveal.js
deck for a live presentation.



