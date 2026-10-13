# Dehqan (دہقان)

**A voice-first crop doctor and market advisor for Pakistani farmers.**

A farmer sends a voice note (Urdu / Pashto / Punjabi) and a photo of a sick leaf. Dehqan diagnoses the problem, grades how severe it is, recommends **only pesticides registered in Pakistan** with dose and safety gear taken from cited official advisories, checks the field from satellite, finds a safe spray window from the weather forecast, suggests whether to sell or hold at the mandi, and answers as a **spoken voice note** in the farmer's language.

> **Status: work in progress (Milestone 1 of 7).** This README separates what is **built and measured** from what is **planned**. Nothing in the "Built" section is aspirational.

---

## Why this exists

Most Pakistani farmers get spray advice from the pesticide dealer, who is also the person selling the product. Dehqan is meant to be a neutral second opinion that is honest about what it does not know:

- When the diagnosis is uncertain, it **abstains** and points the farmer to the local agriculture extension office instead of guessing.
- Dose, timing and protective gear **never come from an LLM's memory**. They come from a retrieved, cited document.
- It never recommends a pesticide that is unregistered or banned in Pakistan.

---

## Architecture

### Target system (what we are building toward)

```mermaid
flowchart TD
    F[Farmer: WhatsApp / web<br/>voice note + leaf photo + field pin] --> I

    subgraph Supervisor["Supervisor router"]
        I[Intake agent<br/>ASR, language detect, intent]
        I --> D[Diagnosis agent]
        I --> R[Agronomy RAG agent]
        I --> FA[Field agent]
        I --> W[Weather agent]
        I --> M[Market agent]
    end

    D -->|"classifier → severity segmentation → abstention gate"| R
    R -->|"cited dose + PPE"| G{{Safety guardrail<br/>registered & not banned?}}
    FA -->|"Sentinel-2 NDVI: whole field or one patch?"| ANS
    W -->|"Open-Meteo: rain-free, low-wind spray window"| ANS
    M -->|"mandi prices + forecast vs naive baseline"| ANS
    G --> ANS[Answer composer]
    ANS --> T[TTS: Urdu / Pashto voice note]
    T --> F
```

| Component | Job | Tech |
|---|---|---|
| Intake agent | Speech-to-text, language detection, route the request | Whisper / MMS |
| Diagnosis agent | Disease classifier, lesion-area severity, "not a crop / not sure" gate | PyTorch, HF Transformers |
| Agronomy RAG agent | Cited treatment from advisories + registered-pesticide list | Embeddings + Chroma |
| Safety guardrail | Blocks unregistered/banned chemicals; dose and PPE only from sources | Rules + red-team eval |
| Field agent | Sentinel-2 NDVI history for the farmer's plot | Copernicus |
| Weather agent | Spray window from forecast | Open-Meteo |
| Market agent | Mandi price history, forecast, sell/hold with confidence band | Time-series model |
| Voice reply | Spoken answer in the farmer's language | MMS-TTS |

**Planned stack:** Python 3.12 · FastAPI · `uv` · pytest · Docker → Render · Next.js + TypeScript + Tailwind → Vercel · Langfuse tracing · GitHub Actions eval gate.

### Repo layout

```
backend/
  app/            FastAPI app, agents, routers          (planned)
  vision/         data download, training, eval          (built: M1)
  voice/          ASR / TTS                              (planned)
  rag/            ingestion, retrieval, safety guardrail (planned)
  data_sources/   Open-Meteo, Sentinel, mandi scraper    (planned)
  tests/          pytest
evals/            committed eval results (JSON)
data/             gitignored; download scripts only are committed
frontend/         Next.js app                            (planned)
```

---

## Built so far (Milestone 1)

### Pipeline: how we got to the first real number

```mermaid
flowchart LR
    A[Pick datasets<br/>lab + field] --> B[Download as class folders<br/>vision/download_data.py]
    B --> C[Map class names so both<br/>datasets share one label set<br/>vision/classes.py]
    C --> D[Train baseline on LAB images<br/>MobileNetV3-Small, CPU]
    D --> E[Test on held-out LAB images]
    D --> F[Test on real FIELD images]
    E --> G[Compare to majority-class baseline<br/>evals/baseline_lab_vs_field.json]
    F --> G
```

1. **Chose two kinds of data on purpose.** [PlantVillage](https://huggingface.co/datasets/BrandonFors/Plant-Diseases-PlantVillage-Dataset) is the standard benchmark but its photos are single leaves on plain backgrounds (lab). [PlantDoc](https://huggingface.co/datasets/Project-AgML/plant_doc_classification) is scraped from the web and looks like real fields: clutter, shadows, odd angles.
2. **Hit and fixed a download problem.** The first PlantVillage copy was ~54,000 tiny files and the Hugging Face Hub rate-limited it (HTTP 429). Switching to a parquet copy (3 large files) fixed it.
3. **Made the datasets comparable.** The two use different class names. We mapped 27 shared classes (`vision/classes.py`, unit-tested). One PlantDoc class (two-spotted spider mites) has only 2 images and is excluded.
4. **Trained a deliberately simple baseline.** ImageNet-pretrained MobileNetV3-Small, fully fine-tuned on 4,050 PlantVillage images (150 per class), 3 epochs, on a laptop CPU (~15 minutes).
5. **Evaluated honestly.** Same model, two test sets, plus a "always guess the most common class" baseline for scale.

### Result: the lab-to-field gap

| Test set | Images | Accuracy | Macro-F1 | Always-guess-majority |
|---|---|---|---|---|
| PlantVillage held-out (lab) | 1,615 | **95.5%** | 0.956 | 3.7% |
| PlantDoc (field) | 2,567 | **11.8%** | 0.089 | 3.6% |

The same model loses ~84 accuracy points when it leaves the lab. It is still about 3x better than guessing on field photos, but it is not usable. Most crop-disease demos report only the first row. **Closing this gap is the point of Milestone 2.**

**Caveats we know about**
- PlantVillage contains several photos of the same leaf, so its test split likely shares leaves with training. The 95.5% is probably optimistic.
- One run, one seed, small training subset. These are baseline numbers, not tuned ones.
- PlantDoc has no wheat or cotton. The comparison uses shared classes (tomato, potato, corn, apple, grape and others).

### Field data for Pakistan's main crops

No public dataset covers Pakistani fields, so we assembled the closest real field photos available (`vision/download_field_crops.py`):

| Crop | Source | What it is | License |
|---|---|---|---|
| Cotton | [Bangladesh cotton leaf set](https://huggingface.co/datasets/Project-AgML/cotton_leaf_disease_classification_bangladesh_2) | 2,137 photos, 7 classes incl. Curl Virus (CLCuV, a major Pakistan cotton disease) | CC-BY-4.0 |
| Cotton | [Second cotton set](https://huggingface.co/datasets/Project-AgML/cotton_leaf_disease_classification) | Different source and camera setup, used as a cross-source test set | CC-BY-NC-4.0 |
| Corn | [Anhui corn leaf set](https://huggingface.co/datasets/Project-AgML/corn_leaf_disease_classification) | 600 field photos, 6 classes | CC-BY-4.0 |

**Known gaps (not hidden):**
- **None of this is from Pakistan.** Bangladesh and China are the nearest public sources. Our own labelled Pakistani photos remain a goal.
- **No wheat.** The only public wheat-disease set we found on the Hub ([wheat_disease_detection](https://huggingface.co/datasets/Project-AgML/wheat_disease_detection)) labels its 7 classes only as `0`-`6`, and we could not verify the names from the card, Zenodo record or paper. We will not guess disease names for a product that gives spray advice.

### Cotton classifier (first Milestone 2 result)

`vision/train_cotton.py` fine-tunes the same MobileNetV3-Small on the Bangladesh cotton set (1,710 train images, 7 classes, 4 epochs, CPU, ~10 minutes). It is tested two ways: a held-out split of the same source, and the second cotton set, which came from a different group and camera setup. Results are in `evals/cotton_cross_source.json`.

**Same-source test (427 images)**

| | Accuracy | Macro-F1 | Always-guess-majority |
|---|---|---|---|
| 7-class | **82.0%** | 0.778 | 27.2% |

Per-class recall: Leaf Redding 98%, Curl Virus 98%, Leaf Variegation 96%, Healthy 88%, Bacterial Blight 78%, Herbicide Damage 73%, **Leaf Hopper Jassids 11%** (the model mostly misses this class).

**Cross-source test (551 images, only the 2 classes the sets share)**

| Scoring | Accuracy | Reference |
|---|---|---|
| Strict (pick 1 of 7 classes) | **0.5%** | |
| Shared-only (choose between the 2 shared classes) | **70.0%** | chance 50%, always-guess-majority **60.4%** |

**What this means, honestly**
- **Cross-source accuracy barely beats the dumb baseline** (70.0% vs 60.4%). The model calls almost everything "Bacterial Blight" (99% recall) and recognises only 51% of healthy leaves. It learned this one source's look, not cotton disease in general.
- **Strict accuracy is near zero:** on photos from another source the model rarely picks the right class out of all 7.
- **The 82% same-source number is probably optimistic.** Photos from the same plants and sessions likely land on both sides of the split. Treat it as an upper bound.
- This is the same lab-to-field pattern as the baseline above, now on cotton: a model that scores well on its own data does not carry over to new cameras and fields. Fixing it (stronger augmentation, training on mixed sources, confidence-based abstention) is the rest of Milestone 2.

### Abstention: saying "I'm not sure"

`vision/abstention.py` answers only when the model's top softmax probability is above a threshold, otherwise Dehqan defers to the extension office. `vision/eval_abstention.py` measures the trade-off on the cotton model (`evals/abstention_cotton.json`). *Coverage* is the share of photos answered, and *selective accuracy* is accuracy on only those.

| Test set | Answer everything | Best coverage at ≥90% accuracy | Best coverage at ≥95% accuracy |
|---|---|---|---|
| Same source (427 images) | 82.0% | **85%** of photos | **67%** of photos |
| Different source (551 images, 2 classes) | 70.0% | **27%** of photos | **25%** of photos |

- **On familiar photos abstention works well:** answering 85% of photos at 90% accuracy beats answering everything at 82%.
- **On photos from a new source it helps much less.** To reach 90% accuracy the model must defer on ~73% of photos, because it is often confidently wrong on unfamiliar cameras. Confidence is a weak safety net under distribution shift.
- **These thresholds were picked on the test data itself,** so the numbers are optimistic. A production threshold would be chosen on a separate validation split.

### Field-tuned model: how much does a little field data help?

`vision/train_field_tuned.py` retrains on PlantVillage (lab) **plus 70% of PlantDoc (field)** and tests on the held-out 30% of PlantDoc (768 images). The old lab-only baseline is scored on the *same* 768 images. Results are in `evals/field_tuned.json`.

| Model | Field accuracy | Macro-F1 | Lab accuracy | Always-guess-majority (field) |
|---|---|---|---|---|
| Lab-only baseline | **11.5%** | 0.088 | 95.5% | 3.7% |
| Lab + 1,799 field photos | **47.4%** | 0.433 | 93.3% | 7.4% |

- **Field accuracy rises about 4x (11.5% to 47.4%)** after adding 1,799 field photos, at a cost of about 2 points of lab accuracy.
- **47% is still not usable for spray advice.** More than half of field photos get the wrong label.
- **Abstention does not rescue it.** The model is overconfident: reaching 90% accuracy means answering only **9%** of photos (95% accuracy: 6%), so at this stage it would defer almost every time.
- **Caveats:** PlantDoc is scraped from the web and may contain near-duplicate photos on both sides of the split, so 47.4% may be optimistic. One run, one seed, 3 epochs on CPU with a small model; there is room to improve, and we have not yet tried a larger backbone or stronger augmentation.

---

## Honest-evaluation principles

These apply to every model in this repo:

1. Every model gets an eval with real numbers, including bad ones.
2. Never test on training data; always compare against a simple baseline.
3. If something does not beat the baseline, the README and the UI say so.
4. The safety red-team suite must pass 100% in CI before any deploy.

## Roadmap

- [x] **M1 Scaffold & data:** repo, dataset scripts, baseline, lab-vs-field eval, field crop sets
- [ ] **M2 Diagnosis v2:** field-tuned model, severity segmentation, "not a crop" gate, abstention (coverage vs accuracy). *In progress: cotton classifier, abstention gate and field-tuned model done (field accuracy 11.5% to 47.4%, still not usable); segmentation and "not a crop" gate not started.*
- [ ] **M3 Agronomy RAG + safety:** cited answers, registered-pesticide guardrail, red-team suite
- [ ] **M4 Voice:** Urdu + Pashto ASR/TTS, WER eval
- [ ] **M5 Field / weather / market agents + supervisor router**
- [ ] **M6 Live product:** Render backend, Vercel frontend, WhatsApp sandbox, rate limits
- [ ] **M7 LLMOps:** Langfuse, CI eval gate, drift monitoring, nightly refresh

Fallback scope if time is tight: 2 crops (wheat, cotton), 2 languages (Urdu, Pashto), 1 mandi region.

## Run it

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12. Everything runs on CPU.

```powershell
cd backend
uv sync
uv run pytest                                   # unit tests
uv run python -m vision.download_data           # PlantVillage + PlantDoc into ../data
uv run python -m vision.download_field_crops    # cotton + corn field sets
uv run python -m vision.train_baseline          # ~15 min on CPU; writes ../evals/baseline_lab_vs_field.json
uv run python -m vision.train_cotton            # ~10 min on CPU; writes ../evals/cotton_cross_source.json
uv run python -m vision.eval_abstention         # seconds; writes ../evals/abstention_cotton.json
uv run python -m vision.train_field_tuned       # ~27 min on CPU; writes ../evals/field_tuned.json
```

Datasets and model weights are gitignored. Only the download scripts and eval results are committed.

## Data licenses and credits

PlantVillage and PlantDoc are public research datasets; the field crop sets are redistributed by the [AgML project](https://project-agml.github.io/) on the Hugging Face Hub under the licenses listed above. Check each dataset card before commercial use: one cotton set is CC-BY-NC.
