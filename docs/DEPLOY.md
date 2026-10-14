# Deploying Dehqan (free tiers)

Backend on **Render** (free web service), website on **Vercel**, model files on the **Hugging Face Hub**.

> **Status: backend deployed and verified at https://dehqan.onrender.com; website not yet on Vercel.** The Docker
> image builds on Render. Measured there: about 2 s per diagnosis, warm.

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

- **Slower than a laptop:** a diagnosis takes 0.2 s on the dev PC's full CPU and about 2 s end to end on Render
  (measured over 5 requests from Pakistan, network included).
- **Sleeps after ~15 minutes without traffic.** The first request after a nap takes roughly a minute while the
  service wakes. The model files are baked into the image, so there is no download on wake-up.
- The in-memory rate limit (10 per minute per IP) is per instance and resets on restart.
- **The satellite field check is the heaviest request.** It took 39 s on the dev PC for a first check of a place; the free plan is slower, so the endpoint stops after 45 s and returns the dates it managed to read (and says how many are missing). Results are cached for 6 hours per place. It is limited to 4 requests per minute per IP. Not yet measured on Render.
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
3. No environment variable needed: production builds default to `https://dehqan.onrender.com`. (To use a different
   backend, set `NEXT_PUBLIC_API_URL`.)
4. Deploy. Optionally restrict CORS afterwards (step 2.3).

The accuracy page uses the committed copies in `frontend/data/evals/` (a deploy rooted at `frontend/` cannot see
`../evals`). After re-running an evaluation, run `npm run sync-evals` in `frontend/` and commit the result.

## Troubleshooting a live deploy

**The website shows "This feature is not available on the server yet".** The website (Vercel) is newer than the API (Render).
Check `https://<your-service>.onrender.com/openapi.json`: it must list `/ask`, `/market`, `/field-ndvi`. If it does not,
Render has not deployed the latest commit. In the Render dashboard open the service, then **Events**: see whether the latest
deploy failed (open its log), or was never triggered (**Manual Deploy → Deploy latest commit**; also check
Settings → Build & Deploy → Auto-Deploy is "On Commit"). A failed deploy leaves the previous version running.

**An answer says "weather service unavailable".** Open `https://<your-service>.onrender.com/status`. It names the failing service
with its HTTP status or error (for example a 429 rate limit from the weather service, which can happen when many apps share
a host's IP address). The service log also records each failed attempt with its reason, and weather calls retry twice first.

**Quick health checklist:** `/health` (models loaded?), `/status` (outside services reachable?), `/openapi.json` (which routes exist).

**The deploy log ends with `ImportError: ... cannot open shared object file`.** A Python package needs a system library that the
slim Docker image does not have (this happened with `libexpat.so.1`, needed by rasterio). Add it to the `apt-get install` line at the
top of `backend/Dockerfile`. To find every library a package needs, list the dynamic-library requirements of its Linux wheel.

**Do not build the Docker image on a small PC.** Docker Desktop's VM takes about half of an 8 GB machine's RAM, and Windows then swaps
heavily. The `docker` job in `.github/workflows/ci.yml` builds the same image on every push and starts the server in it, which is the
check that would have caught the `libexpat` crash before Render did.
