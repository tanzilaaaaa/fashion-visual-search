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
| **Latency** | `backend/scripts/benchmark.py`: mean/p50/p95 for text and image search through the API | PRD budget: 2 s text, 4 s image |
| **Footprint** | Bytes of `index.faiss`, `metadata.json`, `images/` | Must fit the hosting tier |

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
