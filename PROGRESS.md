# PROGRESS.md — Dehqan

_Last updated: 2026-10-13_

## Milestones
- [ ] **M1 — Scaffold & data:** repo + uv setup, dataset download scripts, own field photos, baseline classifier, lab-vs-field eval
  - [x] Repo scaffold: git init, uv backend project, .gitignore, folder layout, PROGRESS.md
  - [x] Backend smoke test (pytest runs green)
  - [x] Dataset download scripts (PlantVillage 54,305 imgs/38 classes; PlantDoc 2,569 imgs/28 classes)
  - [x] Baseline classifier trained on PlantVillage (MobileNetV3-Small, 4,050 imgs, 3 epochs, CPU)
  - [x] Lab-vs-field eval: lab 95.5% -> field 11.8% accuracy (chance 3.7%), see evals/baseline_lab_vs_field.json
  - [ ] Own labelled field photos (held-out "real Pakistan" test set)
- [ ] **M2 — Diagnosis v2**
- [ ] **M3 — Agronomy RAG + safety**
- [ ] **M4 — Voice**
- [ ] **M5 — Field, weather, market agents + supervisor router**
- [ ] **M6 — Live product**
- [ ] **M7 — LLMOps**

## Session log
- 2026-10-13: Scaffolded repo.
