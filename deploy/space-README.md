---
title: Dehqan API
emoji: 🌾
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# Dehqan API

Backend for [Dehqan](https://github.com/MoZainUlAbideen/Dehqan), an honest AI crop doctor for Pakistani farmers.
Research prototype, not agronomic advice. See the GitHub repo for the evaluation results and limits.

Endpoints: `GET /health`, `POST /diagnose`, `POST /spray-window`, `GET /docs`.

Space variables to set: `DEHQAN_MODEL_REPO` (your model repo) and `DEHQAN_CORS_ORIGINS` (your website's URL).
