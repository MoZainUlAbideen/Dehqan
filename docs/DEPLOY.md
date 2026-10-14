# Deploying Dehqan (free tiers)

Backend on a **Hugging Face Space** (Docker, free CPU with 16 GB RAM), website on **Vercel**. Render's free tier
(512 MB) is too small: the CLIP file alone is 605 MB.

> **Status:** the pieces below are prepared and the packaged backend folder was started and called locally.
> The Docker image itself has **not** been built, and the Space has never run, so expect to read the first build
> log and fix small things. Nothing here has been deployed yet.

## 0. Before you publish anything: licenses

The trained weights inherit their data's licenses:

| Weights | Trained on | Consequence |
|---|---|---|
| `severity.pt` | PDSNet, **CC-BY-NC-4.0** | non-commercial only |
| `field_tuned.pt` | PlantVillage + PlantDoc | check both dataset licenses before commercial use |

Publishing them for a portfolio demo is fine. **Selling the product would need retrained models on data you may
use commercially.** Say so in the model repo's description.

## 1. Put the weights on the Hugging Face Hub (DONE: `MoZainUlAbideen/Dehqan`)

Already done: the model repo `MoZainUlAbideen/Dehqan` holds both files, and the startup download was tested against it
(both files fetched anonymously in about 12 s and are byte-identical to `data/models/`). For a new repo: **New → Model**, public.
Still to do: add a model card (the repo's README.md) saying the weights are **non-commercial** (see section 0) and that this is a research prototype. The repo currently has no license note.

## 2. Create and push the Space

```powershell
# from the repo root: build the folder to push
powershell -File deploy/make_space.ps1          # creates build/space/
```

1. huggingface.co → **New → Space**. Name `dehqan-api`, **SDK: Docker**, blank template, free CPU.
2. Clone it and copy the built folder in (the push will ask for your username and a Hugging Face *access token*
   as the password; create one under Settings → Access Tokens with write permission):
   ```powershell
   git clone https://huggingface.co/spaces/<your-username>/dehqan-api
   Copy-Item -Recurse -Force build\space\* dehqan-api\
   cd dehqan-api
   git add .
   git commit -m "Deploy Dehqan API"
   git push
   ```
3. In the Space → **Settings → Variables and secrets**, add:
   - `DEHQAN_MODEL_REPO` = `MoZainUlAbideen/Dehqan`
   - `DEHQAN_CORS_ORIGINS` = your Vercel URL (add it after step 3; until then `http://localhost:3000`)
4. Watch the build log. The first start also downloads CLIP (~600 MB) and the two weight files, so give it a few
   minutes. Then open `https://<your-username>-dehqan-api.hf.space/health`. You want `"models_loaded": true`.
5. Try it: `https://<your-username>-dehqan-api.hf.space/docs`.

## 3. Deploy the website on Vercel

1. vercel.com → **Add New → Project** → import the GitHub repo.
2. **Root Directory: `frontend`**. Framework: Next.js (auto-detected).
3. Environment variable: `NEXT_PUBLIC_API_URL` = `https://<your-username>-dehqan-api.hf.space`
4. Deploy. Then go back to the Space and set `DEHQAN_CORS_ORIGINS` to the Vercel URL, so the browser may call it.

The accuracy page uses the committed copies in `frontend/data/evals/` (a deploy rooted at `frontend/` cannot see
`../evals`). After re-running an evaluation, run `npm run sync-evals` in `frontend/` and commit the result.

## Things to expect on the free tiers

- The Space **sleeps after inactivity**; the first request after a nap takes a minute while models reload.
- Each diagnosis takes a few seconds on 2 CPUs. The in-memory rate limit (10 per minute per IP) is per instance.
- Photos are processed in memory and not stored.
