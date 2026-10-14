# Deploying Dehqan (free tiers)

Backend on **Render** (free web service), website on **Vercel**, model files on the **Hugging Face Hub**.

> **Status: prepared, not deployed.** The Dockerfile has never been built (the Docker engine was not running on
> the dev PC) and Render has never run this repo. Expect to read the first build log and fix small things.

## Why the backend runs on ONNX, not PyTorch

Render's free tier has **512 MB of RAM**. Measured on the dev PC:

| Backend | RAM with all 3 models loaded and running |
|---|---|
| PyTorch + transformers (development) | ~909 MB: too big |
| **ONNX Runtime** (what the server uses) | **~220 MB** |

The three models were exported with `vision/export_onnx.py`. CLIP's text half is computed once instead of on
every request, and its image half is int8-quantised (351 MB to 88 MB). `vision/check_onnx_parity.py` measures how
closely the ONNX models match the PyTorch ones (results in the README and `evals/onnx_parity.json`).

## Expectations on Render's free plan

- **Slow:** the free plan gives a small slice of one CPU. A diagnosis takes 0.2 s on the dev PC's full CPU, so
  expect several seconds on Render. This has not been measured there.
- **Sleeps after ~15 minutes without traffic.** The first request after a nap takes roughly a minute while the
  service wakes. The model files are baked into the image, so there is no download on wake-up.
- The in-memory rate limit (10 per minute per IP) is per instance and resets on restart.
- Photos are processed in memory and not stored.

## 0. Licenses: read before publishing

The weights inherit their data's licenses:

| Weights | Trained on | Consequence |
|---|---|---|
| severity model | PDSNet, **CC-BY-NC-4.0** | non-commercial only |
| classifier model | PlantVillage + PlantDoc | check both licenses before commercial use |

Fine for a portfolio demo. **Selling the product would need models retrained on data you may use commercially.**

## 1. Put the ONNX files on the Hugging Face Hub (your model repo `MoZainUlAbideen/Dehqan`)

The Docker build downloads these files from the repo, so it must be **public** (it is).

1. Open `https://huggingface.co/MoZainUlAbideen/Dehqan`, then **Files and versions → Add file → Upload files**.
2. Drag the **folder** `D:\VS-Code-Projects\Dehqan\data\hf_upload\onnx` into the upload box (103 MB; it was
   prepared for you and holds only the files the server needs). It must end up as an `onnx/` folder inside the
   repo holding exactly these 5 files:
   `classifier.onnx`, `severity.onnx`, `clip_vision_int8.onnx`, `clip_text.npy`, `meta.json`.
   (If you ever re-export, the full output is in `data\models\onnx`; never upload `clip_vision.onnx`, 351 MB, unused.)
3. Commit. Check the repo page shows the `onnx/` folder with those files.
4. Add a model card (the repo's README.md): the weights are for **non-commercial research use** and this is a
   research prototype. The old `.pt` files can stay or be deleted; the server no longer uses them.

## 2. Deploy the backend on Render

You know Render, so the dashboard route is quickest:

1. Render dashboard → **New → Web Service** → connect the GitHub repo `MoZainUlAbideen/Dehqan`.
2. Settings: **Language: Docker**. **Root Directory: `backend`**. Dockerfile path `./Dockerfile` (the default).
   **Instance type: Free**. Branch `main`.
3. Environment: nothing required (the Dockerfile sets `DEHQAN_MODEL_REPO` and `DEHQAN_CORS_ORIGINS=*`). Later,
   to restrict browser access to your website, set `DEHQAN_CORS_ORIGINS` to your Vercel URL.
4. **Health check path:** `/health`.
5. Create the service and watch the build log. The build installs the runtime dependencies and downloads the
   model files from the Hub. When it is live, open `https://<your-service>.onrender.com/health`. You want
   `"models_loaded": true`. Then try `/docs`.

(A `render.yaml` Blueprint at the repo root describes the same service. It is untested; the dashboard route
above is the safer choice.)

## 3. Deploy the website on Vercel

1. vercel.com → **Add New → Project** → import the GitHub repo.
2. **Root Directory: `frontend`**. Framework: Next.js (auto-detected).
3. Environment variable: `NEXT_PUBLIC_API_URL` = `https://<your-service>.onrender.com`
4. Deploy. Optionally restrict CORS afterwards (step 2.3).

The accuracy page uses the committed copies in `frontend/data/evals/` (a deploy rooted at `frontend/` cannot see
`../evals`). After re-running an evaluation, run `npm run sync-evals` in `frontend/` and commit the result.
