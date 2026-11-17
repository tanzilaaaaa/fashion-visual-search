# Evaluation

All numbers come from `ml/fvs_ml/evaluate.py`, run by the pipeline. They are written to
`artifacts/evaluation.json`, served at `GET /evaluation` and rendered on the About page.

## Data split

* **Catalogue (indexed):** a category-balanced 50k subset of train + the rest of validation.
* **Evaluation slice:** 25 % of validation `pair_id`s (≤ 4,000 images), chosen with a fixed seed.
  It is disjoint from the catalogue and never used to tune preprocessing, α/β or prompts.
  Splitting by pair keeps each consumer photo with its shop photos.

## Metrics

| Metric | Definition | Baseline |
|---|---|---|
| **Consumer→shop Recall@1/5/10** | Query = consumer ("user") item with `style > 0`; gallery = shop items in the slice; a hit = a gallery item with the same `pair_id` **and** `style` in the top K (the DeepFashion2 retrieval protocol). | Same-category items in random order (what a tag-only catalogue can do) |
| **Text→category Precision@1/5/10** | 16 natural phrasings, several using synonyms ("blue jeans", "tank top", "denim jacket"); a result is relevant if its category is in the probe's relevant set. | Keyword match of query words against category names |
| **Complete the Look Hit@10** | For a garment with a compatible partner in the same photo, is the partner in the top 10 suggestions drawn from all slice items of the target categories? | Random pick from the same categories |
| **Fine-tuning ablation** | The same Recall@K and Precision@K, computed twice on the same slice and index settings: frozen CLIP vectors vs. vectors passed through the fine-tuned adapter (`variants` in `evaluation.json`) | Pretrained CLIP |
| **Latency** | `backend/scripts/benchmark.py`: mean/p50/p95 for text and image search through the API | PRD budget: 2 s text, 4 s image |
| **Footprint** | Bytes of `index.faiss`, `metadata.json`, `images/` | Must fit the hosting tier |

## Results: real build (Kaggle T4, 17 Nov 2026)

* **Catalogue:** 50,000 category-balanced DeepFashion2 garments. Sling (2,232) and short-sleeve
  outwear (657) are short because the dataset has few of them.
* **Evaluation slice:** 6,688 held-out validation items, giving 1,508 street-photo queries
  against a gallery of 4,782 shop items.
* **Fine-tuning data:** 60,008 pair items (5,700 training groups), 40 epochs, 26 s on the GPU.
  The best epoch was 33, and `r = 0.6` was chosen.

| Street photo → shop item | Recall@1 | Recall@5 | Recall@10 |
|---|---|---|---|
| Same-category baseline | 1.6 % | 8.4 % | 14.8 % |
| Pretrained CLIP ViT-B/32 | 11.6 % | 20.7 % | 25.0 % |
| **CLIP + fine-tuned adapter** | **45.0 %** | **64.3 %** | **73.1 %** |

| Text query → right category (16 probes) | P@1 | P@5 | P@10 |
|---|---|---|---|
| Keyword baseline | 37.5 % | 37.5 % | 37.5 % |
| Pretrained CLIP | 87.5 % | 85.0 % | 80.6 % |
| Fine-tuned adapter space | 75.0 % | 70.0 % | 65.0 % |

* **Complete the Look Hit@10:** 24.8 % vs. 0.3 % for random picks from the same categories.
* **Footprint:** index 102 MB, metadata 16 MB, thumbnails 370 MB.
* **Build time:** 113 minutes. About 70 of those went on reading ~224k annotation files from
  Kaggle's network-mounted input.

**Reading the results.** Fine-tuning roughly triples exact-garment retrieval from street photos.
That is the task CLIP was never trained for, and the one the adapter targets. The cost is text
alignment: text precision drops 15 points in the adapted space. It is still far above the keyword
baseline, but the tuning-split guard didn't catch the drop. The guard uses category prompts over
the tuning pairs, which weren't representative of the 16 natural-language probes. The fix is a
**dual index**: photos search the adapted space and text searches the pretrained space. That
keeps both 73 % street→shop Recall@10 and ~81 % text P@10. The pipeline now writes
`text_index.faiss` for every fine-tuned build, and the backend routes text queries to it when it
is present.

## Fine-tuning protocol

* Training pairs come only from the DeepFashion2 **train** split. The evaluation slice is drawn
  from **validation**, so the two never overlap.
* 10 % of training pair ids form a **tuning split**. It picks the best epoch (Recall@10) and the
  residual ratio `r` ∈ {0, 0.2, 0.4, 0.6, 0.8}. The chosen `r` maximises tuning Recall@10, while
  text-category precision may drop by at most 2 points. Ties go to the better Recall@1, then to
  the smaller `r`.
* `evaluation.json → finetune` records the config, pair counts, per-epoch loss and tuning recall,
  the `r` search and the training time. The Insights page plots them.

## Caveats

* Complete-the-Look partners share a photo, so lighting and background make them look similar.
  Treat Hit@10 as a sanity check and pair it with a manual review of ~50 suggestions
  (PRD §12.1, "manually reviewed compatibility set").
* Text precision is measured against **category** labels only, since DeepFashion2 has no colour or style labels.
* Smoke-test numbers from `make dev-index` on synthetic data are meaningless. Report only the Kaggle run.

## Local smoke-test reference (synthetic data — plumbing only)

Measured on an Apple-silicon laptop, CPU, 700-item synthetic index:

| | mean | p50 | p95 |
|---|---|---|---|
| Text search (API round-trip) | 12.5 ms | 2.6 ms (cached) | 29 ms |
| Image search (API round-trip) | 54.5 ms | 42.6 ms | 153 ms |

On Hugging Face's shared CPUs, expect higher numbers. Re-run `make bench` against the deployed URL
(`python backend/scripts/benchmark.py --base-url https://…hf.space --image q.jpg`) for the report.
