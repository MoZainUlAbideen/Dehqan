# PROGRESS.md — Dehqan

_Last updated: 2026-10-13_

## Milestones
- [x] **M1 — Scaffold & data:** repo + uv setup, dataset download scripts, own field photos, baseline classifier, lab-vs-field eval
  - [x] Repo scaffold: git init, uv backend project, .gitignore, folder layout, PROGRESS.md
  - [x] Backend smoke test (pytest runs green)
  - [x] Dataset download scripts (PlantVillage 54,305 imgs/38 classes; PlantDoc 2,569 imgs/28 classes)
  - [x] Baseline classifier trained on PlantVillage (MobileNetV3-Small, 4,050 imgs, 3 epochs, CPU)
  - [x] Lab-vs-field eval: lab 95.5% -> field 11.8% accuracy (chance 3.7%), see evals/baseline_lab_vs_field.json
  - [x] Online field-photo sets instead of own photos: cotton_bd 2,137 + cotton_alt 1,373 + corn_anhui 600 (no wheat: unnamed classes). Own Pakistani photos still a future goal.
- [ ] **M2 — Diagnosis v2**
  - [x] Cotton classifier + cross-source eval: same-source 82.0%, cross-source 70.0% vs 60.4% majority baseline (does not generalise yet), Leaf Hopper Jassids recall 11%
  - [ ] Corn field test with baseline
  - [ ] Field-tuned model (train on mixed sources), measure gap closed
  - [ ] Abstention gate (coverage vs accuracy)
  - [ ] Severity segmentation + "not a crop" gate
- [ ] **M3 — Agronomy RAG + safety**
- [ ] **M4 — Voice**
- [ ] **M5 — Field, weather, market agents + supervisor router**
- [ ] **M6 — Live product**
- [ ] **M7 — LLMOps**

## Session log
- 2026-10-13: Scaffolded repo.
