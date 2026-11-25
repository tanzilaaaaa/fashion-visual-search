"""Shrink the runtime artifacts so the API fits in 512 MB (Render free / Starter).

Run at Docker build time, after the artifacts are fetched:

* ``index.faiss`` / ``text_index.faiss``: exact float32 flat indexes are rewritten
  as 8-bit scalar-quantised indexes (``IndexScalarQuantizer``, QT_8bit, inner
  product): ~4× smaller, cosine error ~1e-3, still exhaustive and filterable with
  ID selectors. The originals are replaced in place.
* ``metadata.json``: written as ``metadata.npz`` (columnar numpy arrays). Parsing
  the 15 MB JSON creates 50k Python dicts (~250 MB at peak); the npz loads in a
  few MB and ``MetadataService`` builds item dicts on demand.

    python scripts/compact_artifacts.py --artifacts artifacts [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.compact_metadata import save_compact  # noqa: E402  (app/__init__ loads the macOS shim)


def quantise_index(path: Path, check: bool) -> dict:
    import faiss  # after `app` (torch-before-faiss on macOS)

    flat = faiss.read_index(str(path))
    if not isinstance(flat, faiss.IndexFlat):
        return {"file": path.name, "skipped": f"already {type(flat).__name__}"}
    vecs = flat.reconstruct_n(0, flat.ntotal)
    sq = faiss.IndexScalarQuantizer(flat.d, faiss.ScalarQuantizer.QT_8bit, faiss.METRIC_INNER_PRODUCT)
    sq.train(vecs)
    sq.add(vecs)
    report = {"file": path.name, "items": int(sq.ntotal), "flat_mb": round(path.stat().st_size / 1e6, 1)}
    if check:
        rng = np.random.default_rng(0)
        q = vecs[rng.choice(len(vecs), size=min(200, len(vecs)), replace=False)]
        _, a = flat.search(q, 10)
        _, b = sq.search(q, 10)
        report["top10_overlap"] = round(float(np.mean([len(set(x) & set(y)) / 10 for x, y in zip(a, b)])), 4)
        report["top1_same"] = round(float(np.mean(a[:, 0] == b[:, 0])), 4)
    tmp = path.with_suffix(".sq8.tmp")
    faiss.write_index(sq, str(tmp))
    tmp.replace(path)
    report["sq8_mb"] = round(path.stat().st_size / 1e6, 1)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--artifacts", type=Path, required=True)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--keep-json", action="store_true", help="keep metadata.json next to metadata.npz")
    a = ap.parse_args()

    out = {}
    for name in ("index.faiss", "text_index.faiss"):
        p = a.artifacts / name
        if p.exists():
            out[name] = quantise_index(p, a.check)
    meta_json = a.artifacts / "metadata.json"
    if meta_json.exists():
        data = json.loads(meta_json.read_text())
        items = data["items"] if isinstance(data, dict) else data
        save_compact(items, a.artifacts / "metadata.npz")
        out["metadata"] = {"items": len(items), "json_mb": round(meta_json.stat().st_size / 1e6, 1),
                           "npz_mb": round((a.artifacts / "metadata.npz").stat().st_size / 1e6, 1)}
        if not a.keep_json:
            meta_json.unlink()
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
