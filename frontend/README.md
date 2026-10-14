# Dehqan frontend

Next.js (App Router) + TypeScript + Tailwind. Pages: home, `/diagnose`, `/spray`, `/accuracy`.

```powershell
cd frontend
npm install
npm run dev          # http://localhost:3000
```

The site talks to the FastAPI backend at `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`). Start the
backend first (`cd backend; uv run uvicorn app.main:app`).

The `/accuracy` page reads the project's eval results from `data/evals/`. `npm run dev` and `npm run build`
first copy `../evals/*.json` there (`scripts/sync-evals.mjs`), so the page cannot drift from the repo's real
numbers. If `../evals` is missing (a deploy rooted at `frontend/`), the committed copies are used.

`data/pakistan.geo.json` is a coarse outline used for the illustrative map only.
