# PROGRESS.md — Dehqan

_Last updated: 2026-10-14_

## Milestones
- [x] **M1 — Scaffold & data:** repo + uv setup, dataset download scripts, own field photos, baseline classifier, lab-vs-field eval
  - [x] Repo scaffold: git init, uv backend project, .gitignore, folder layout, PROGRESS.md
  - [x] Backend smoke test (pytest runs green)
  - [x] Dataset download scripts (PlantVillage 54,305 imgs/38 classes; PlantDoc 2,569 imgs/28 classes)
  - [x] Baseline classifier trained on PlantVillage (MobileNetV3-Small, 4,050 imgs, 3 epochs, CPU)
  - [x] Lab-vs-field eval: lab 95.5% -> field 11.8% accuracy (chance 3.7%), see evals/baseline_lab_vs_field.json
  - [x] Online field-photo sets instead of own photos: cotton_bd 2,137 + cotton_alt 1,373 + corn_anhui 600 (no wheat: unnamed classes). Own Pakistani photos still a future goal.
- [x] **M2 — Diagnosis v2**
  - [x] Cotton classifier + cross-source eval: same-source 82.0%, cross-source 70.0% vs 60.4% majority baseline (does not generalise yet), Leaf Hopper Jassids recall 11%
  - [x] Corn field test (Anhui): lab-only 4.5% vs field-tuned 72.0% on 2 known diseases (50% guess); 20% of unseen-disease photos still >90% confident
  - [x] Field-tuned model (lab + 70% PlantDoc): held-out field accuracy 11.5% -> 47.4% (majority 7.4%), lab 93.3%; still not usable
  - [x] Abstention gate: cotton same-source 85% coverage @90% acc; cross-source 27%; field-tuned model only 9% coverage @90% (overconfident)
  - [x] Severity segmentation (PDSNet, 81 test photos): MAE 8.0 pts vs 13.1 naive, grade acc 81.5% vs 42.0%; wheat weakest (MAE 15.4)
  - [x] Zero-shot "not a crop" gate (CLIP): accepts 99.6% of leaf photos, 1.0% false accepts, AUROC 0.9997 vs 0.675 for classifier-confidence shortcut; hard negatives (soil/weeds/fruit) untested
- [ ] **M3 — Agronomy RAG + safety**
  - [x] Guardrail logic (rag/guardrail.py): banned/registered check + verbatim-citation check for dose and PPE, 14 tests; fixed number-boundary bug (20 ml vs 120 ml)
  - [ ] BLOCKED (needs user): get official registered + banned pesticide lists and advisory PDFs into data/advisories/ (gov sites unreachable from this machine)
  - [ ] Ingest advisories, retrieval, cited answers
  - [ ] Faithfulness eval + red-team suite (100% pass in CI)
- [ ] **M4 — Voice**
- [ ] **M5 — Field, weather, market agents + supervisor router**
  - [x] Weather agent: Open-Meteo client (cached, tested vs real saved response) + spray-window logic (rules-of-thumb thresholds, flagged as not official), 11 tests
  - [x] Field agent: real Sentinel-2 NDVI from the open AWS archive (no account), small-window COG reads, cloud masking, 12-month timeline, even/patchy/bare reading, vs last year. Found and fixed two real bugs (catalogue offset does not match the data; cloud mask read from the wrong window) with regression tests that fail on the old code. POST /field-ndvi, /field page with date slider and play. 39 s cold / 267 MB RAM on dev PC; 6 h cache. No accuracy number (thresholds not validated against ground truth)
  - [x] Market agent: WFP retail prices (5 cities, 8 staples), 5 forecasting methods, honest model choice (must beat naive by 5%), empirical 10-90% range, sell/hold only if whole range clears +/-3%. Walk-forward eval: agent 4.54% vs naive 4.50% mean error, never beat naive (0 better / 4 worse / 32 tied of 36); range coverage 84% overall vs 80% target, wheat only 67%. /market endpoints, /market page, accuracy page section. Retail not mandi prices; data as of 2026-08
  - [x] Supervisor router: POST /ask + /ask page. Keyword lexicon (EN / Roman Urdu / Urdu), city + crop extraction, multi-intent, bilingual answers, asks for missing info. Pesticide/dose questions always refused with no data call. Eval: dev 41 q (tuned), frozen test 40 q: 90% fully right vs 18% / 15% baselines; pesticide questions refused 7/7. Misses: symptom-only descriptions, negated "spray". Lexicon + Urdu text need native review
- [ ] **M6 — Live product**
  - [x] FastAPI backend: /diagnose (gate -> classifier -> abstention -> severity), /spray-window, /health, /about; upload validation, downscaling, per-IP rate limit, CORS; 72 tests; run live with real models
  - [x] Next.js website: home, diagnose, spray window (map + hour grid), accuracy page from real eval JSON; lint + typecheck + build clean; checked in headless Edge (dark mode only)
  - [x] Deploy target chosen: Hugging Face Spaces (Docker) + Vercel. Render free (512 MB) cannot hold torch + CLIP (CLIP file alone is 605 MB)
  - [x] Prepared: GitHub Actions CI (runtime-only install, no PyTorch), backend/Dockerfile (bakes model files in; untested build), render.yaml (untested), model fetch from HF Hub (4 tests), docs/DEPLOY.md for Render + Vercel
  - [x] USER: weights uploaded to HF Hub (MoZainUlAbideen/Dehqan); startup download verified against it (identical files)
  - [x] USER: ONNX files uploaded to the HF model repo; Render service created (free, Docker, root dir backend). First build failed with a 404 because the files were not uploaded yet; after uploading, it succeeded
  - [x] Live API verified: https://dehqan.onrender.com : /health models_loaded true; diagnose ~1.8-2.7 s warm (from Pakistan); identical gate score to local; rejects non-crop and bad uploads; CORS * ; website built against it and checked
  - [x] Frontend: production build defaults to the Render URL (no Vercel env var needed); 'server is waking up' hint after 6 s for the sleeping free tier
  - [x] Frontend redesign: more vivid emerald/gold theme, animated Pakistan map (pulsing city rings, scan sweep, flowing border, glow + hover cards with REAL live weather from Open-Meteo, live timestamp), English + Urdu explanation on the first screen, bilingual how-it-works, Urdu footer disclaimer. Checked in headless Edge at desktop and true 375 px width; hover and light mode not visually verified. Urdu text needs a native-speaker review
  - [ ] USER: deploy frontend on Vercel (Root Directory frontend)
  - [ ] Verify the first real Space build and fix what breaks
  - [ ] WhatsApp sandbox
- [ ] **M7 — LLMOps**
  - [x] CI workflow + eval gate over committed results (tests/test_eval_gate.py); proven to fail when a number regresses
  - [x] Operational visibility: GET /status (live dependency check with reasons), log lines that say why an outside call failed, weather retries on 429/5xx, friendly 'not available on the server yet' message in the site
  - [ ] Langfuse tracing (needs account keys), drift monitoring, nightly data refresh

## Session log
- 2026-10-13: Scaffolded repo.
- 2026-10-14: Weather agent, FastAPI backend, Next.js website; M3 still blocked on official pesticide data.
- 2026-10-14: Live on Render + ONNX backend; vivid theme, live animated map, Urdu explanation; market agent (honest: no method beats naive); satellite NDVI field agent (2 real bugs found and fixed); CI eval gate. 138 tests.
- 2026-10-14 (later): supervisor router (/ask) with bilingual answers and a frozen-test-set evaluation; eval gate extended to the router; 192 backend tests.
