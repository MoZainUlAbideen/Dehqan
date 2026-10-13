# CLAUDE.md — Dehqan (دہقان)

## What this project is
Dehqan is a voice-first crop doctor and market advisor for Pakistani farmers.
A farmer sends a voice note (Urdu / Pashto / Punjabi) and a photo of a sick leaf.
Dehqan:
1. Diagnoses the disease/pest (and says "I'm not sure" when it isn't).
2. Grades severity from the photo (lesion area %).
3. Gives treatment using ONLY pesticides registered in Pakistan, with dose + safety (PPE) taken from cited official advisories.
4. Checks the farmer's field from satellite (Sentinel-2 NDVI) — whole-field vs patch stress.
5. Finds a safe spray window from the weather forecast (Open-Meteo).
6. Suggests sell vs hold using mandi price history + forecast.
7. Replies as a spoken voice note in the farmer's language.

Goal: a portfolio project that impresses AI-engineering recruiters AND a sellable MVP
(buyers: agri-input companies, agri-lending banks, extension departments).

## About me (the developer)
- I'm Zain, an AI engineer, still new to AI-engineering practices.
- This is the 5th project in my portfolio push (after EdgarIQ, Rehnuma, Parity, Earshot).
  EdgarIQ and Rehnuma are the quality bar: real tests, honest evals, live backend, polished frontend.
- I'm on Windows, using VS Code + PowerShell.
- I use daily free-tier limits, so every session must end with real, tangible progress.

## How you must work with me (very important)
1. **Explain every change in very simple words.** After each change, write a short
   "What I did / Why / How to explain it in an interview" note. I must be able to
   defend every part of this project in interviews.
2. **Go step by step.** One small, testable step at a time. Tell me exactly what to run
   and what output I should expect. Don't dump huge multi-file changes without explaining them.
3. **Use `uv` for everything Python.** Never `python -m venv` or `pip install`.
   - `uv init`, `uv add <pkg>`, `uv add --dev <pkg>`, `uv run pytest`, `uv run <script>`
4. **Real tests, real bugs.** Write pytest tests for real logic. When something breaks,
   diagnose it from the actual error/output — read logs, reproduce, then fix. Never guess-fix.
5. **Honest evals.** Every model/agent gets an eval with real numbers, including bad ones.
   Never inflate metrics, never test on training data, always compare against a simple baseline.
   If something doesn't beat the baseline, we say so in the README and the UI.
6. **Git workflow, step by step.** After each working step, give me the exact commands:
   `git status` → `git add ...` → `git commit -m "..."` → `git push`.
   Use clear conventional commit messages (feat:, fix:, test:, docs:, chore:).
   Never commit `.env`, API keys, model weights, or large datasets.
7. **Progress log.** Every time a task is checked off, show me the updated
   progress checklist (below) as a separate block, and update `PROGRESS.md` in the repo.
8. **Free tier first.** Prefer free APIs/models (Groq, Gemini free tier — `gemini-3.1-flash-lite`
   has been the reliable one for me, HF Hub, Open-Meteo, Copernicus). Cache aggressively,
   rate-limit the public demo to protect my quotas.
9. **Ask before big decisions** (new paid service, big refactor, changing architecture).

## Safety rules for the product (non-negotiable)
- Never recommend a pesticide that is not on the Pakistan registered-pesticide list, or is banned.
- Dose, timing and PPE must come from a retrieved, cited source document — never from LLM memory.
- Low-confidence diagnosis → abstain and suggest contacting the local agriculture extension office.
- The safety red-team eval must pass at 100% in CI before any deploy.

## Tech stack (default — discuss before changing)
- Backend: Python 3.12, FastAPI, uv, pytest, Docker → deployed on Render (free tier)
- Frontend: Next.js + TypeScript + Tailwind → deployed on Vercel
  - Must be MORE attractive than Rehnuma: map of Pakistan hero, NDVI timeline slider,
    diagnosis view with segmentation overlay + severity gauge, voice-note waveform UI,
    "How we measured accuracy" page. Earthy greens + wheat gold, Urdu Nastaliq wordmark.
- Vision: PyTorch / HF transformers (classification, segmentation, zero-shot gate); checkpoints on HF Hub
- Voice: Whisper / MMS for ASR, MMS-TTS for Urdu & Pashto
- RAG: embeddings + vector store (Chroma or similar) over agri advisories & pesticide list
- Agents: supervisor router + specialist agents (intake, diagnosis, agronomy RAG, field/satellite, weather, market)
- LLMOps: Langfuse tracing, CI eval gate (GitHub Actions), drift monitoring, nightly data refresh
- Channels: web app + WhatsApp (Twilio sandbox for demo)

## Repo layout (target)
```
dehqan/
  backend/
    app/            # FastAPI app, agents, routers
    vision/         # training, inference, abstention gate
    voice/          # ASR / TTS
    rag/            # ingestion, retrieval, safety guardrail
    data_sources/   # open-meteo, sentinel, mandi scraper (with caching)
    tests/
  evals/            # eval scripts + results (committed as JSON/markdown)
  data/             # gitignored; download scripts only are committed
  frontend/         # Next.js app
  .github/workflows/
  CLAUDE.md
  PROGRESS.md
  README.md
```

## Milestones & progress checklist
- [ ] **M1 — Scaffold & data:** repo + uv setup, dataset download scripts (PlantVillage, PlantDoc, Pakistan crop sets), my own labelled field photos, baseline classifier, lab-vs-field eval
- [ ] **M2 — Diagnosis v2:** field-tuned model, severity segmentation, zero-shot "not a crop" gate, abstention (coverage vs accuracy eval)
- [ ] **M3 — Agronomy RAG + safety:** ingest advisories + registered-pesticide list, cited answers, guardrail, red-team suite, faithfulness eval
- [ ] **M4 — Voice:** Urdu + Pashto ASR/TTS, WER eval on real farmer-style voice notes
- [ ] **M5 — Field, weather, market agents + supervisor router:** NDVI, spray window, mandi scraper + forecast vs naive baseline
- [ ] **M6 — Live product:** Docker backend on Render, Next.js frontend on Vercel, WhatsApp sandbox, rate limits
- [ ] **M7 — LLMOps:** Langfuse, CI eval gate, drift job, nightly refresh, README with honest metrics

Fallback scope if time is tight: 2 crops (wheat, cotton), 2 languages (Urdu, Pashto), 1 mandi region.

## Start of every session
1. Read this file and `PROGRESS.md`.
2. Tell me where we left off and propose the next small, rewarding step.
3. Wait for my go-ahead, then build it step by step.
