"""Download the search artifacts from the private Hugging Face dataset at build time.

DeepFashion2's terms forbid redistribution, so the artifacts live in a *private*
dataset repo and are pulled with ``HF_TOKEN`` (an environment variable on Render).

Two layouts live in the dataset:

* ``--subset full`` (local development with PyTorch): float32 indexes,
  ``metadata.json`` and ``adapter.npz`` at the repo root.
* ``--subset small`` (Render's 512 MB free plan): the ready-made files under
  ``small/`` (int8-weight ONNX CLIP, 8-bit FAISS indexes, columnar
  ``metadata.npz``) produced by ``export_onnx.py`` + ``compact_artifacts.py``.

Both also unpack ``images.tar`` (the 50k thumbnails, shipped as one file because
50k small files upload and download slowly). If the artifacts are already present,
this is a no-op.

    HF_TOKEN=... python scripts/fetch_artifacts.py --repo <user>/fvs-artifacts --dest artifacts --subset small
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tarfile
from pathlib import Path

REQUIRED = {"full": ("index.faiss", "metadata.json"), "small": ("index.faiss", "metadata.npz", "onnx/config.json")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("ARTIFACTS_REPO", ""))
    ap.add_argument("--dest", type=Path, default=Path("artifacts"))
    ap.add_argument("--subset", choices=("full", "small"), default=os.environ.get("ARTIFACTS_SUBSET", "full"))
    a = ap.parse_args()
    need = REQUIRED[a.subset]

    if all((a.dest / f).exists() for f in need) and (a.dest / "images").is_dir():
        print(f"artifacts already present in {a.dest}; skipping download")
        return 0
    if not a.repo:
        print("No ARTIFACTS_REPO set and no local artifacts; the API will start in degraded mode.")
        return 0

    from huggingface_hub import snapshot_download

    token = os.environ.get("HF_TOKEN")
    if not token and Path("/run/secrets/HF_TOKEN").exists():
        token = Path("/run/secrets/HF_TOKEN").read_text().strip()
    a.dest.mkdir(parents=True, exist_ok=True)
    patterns = ["images.tar"] + (["small/*", "small/onnx/*"] if a.subset == "small" else
                                 ["*.faiss", "*.json", "*.npz"])
    local = Path(snapshot_download(repo_id=a.repo, repo_type="dataset", token=token, local_dir=a.dest,
                                   allow_patterns=patterns))
    if a.subset == "small":  # move small/* up to the artifact root
        for item in (local / "small").iterdir():
            target = a.dest / item.name
            if target.exists():
                shutil.rmtree(target) if target.is_dir() else target.unlink()
            shutil.move(str(item), str(target))
        shutil.rmtree(local / "small", ignore_errors=True)
    tarball = a.dest / "images.tar"
    if tarball.exists():
        with tarfile.open(tarball) as tf:
            tf.extractall(a.dest, filter="data")
        tarball.unlink()
    shutil.rmtree(a.dest / ".cache", ignore_errors=True)
    missing = [f for f in need if not (a.dest / f).exists()]
    if missing:
        print(f"Downloaded repo is missing {missing}", file=sys.stderr)
        return 1
    print(f"artifacts ({a.subset}) ready in {a.dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
