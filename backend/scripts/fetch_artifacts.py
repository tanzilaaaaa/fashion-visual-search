"""Download index artifacts from a private Hugging Face dataset repo at Docker build time.

DeepFashion2's terms forbid redistribution, so the artifacts live in a *private*
repo and are pulled with a token supplied as a build secret. If artifacts are
already present (copied into the build context), this is a no-op.

    HF_TOKEN=... python scripts/fetch_artifacts.py --repo <user>/fvs-artifacts --dest artifacts
"""

from __future__ import annotations

import argparse
import os
import sys
import tarfile
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("ARTIFACTS_REPO", ""))
    ap.add_argument("--dest", type=Path, default=Path("artifacts"))
    a = ap.parse_args()

    if (a.dest / "index.faiss").exists() and (a.dest / "metadata.json").exists():
        print(f"artifacts already present in {a.dest} — skipping download")
        return 0
    if not a.repo:
        print("No ARTIFACTS_REPO set and no local artifacts; the API will start in degraded mode.")
        return 0

    from huggingface_hub import snapshot_download

    token = os.environ.get("HF_TOKEN")
    if not token and Path("/run/secrets/HF_TOKEN").exists():
        token = Path("/run/secrets/HF_TOKEN").read_text().strip()
    a.dest.mkdir(parents=True, exist_ok=True)
    local = Path(snapshot_download(repo_id=a.repo, repo_type="dataset", token=token, local_dir=a.dest))
    # The Kaggle notebook ships images as one tarball (50k small files upload badly).
    tarball = local / "images.tar"
    if tarball.exists():
        with tarfile.open(tarball) as tf:
            tf.extractall(a.dest, filter="data")
        tarball.unlink()
    missing = [f for f in ("index.faiss", "metadata.json") if not (a.dest / f).exists()]
    if missing:
        print(f"Downloaded repo is missing {missing}", file=sys.stderr)
        return 1
    print(f"artifacts ready in {a.dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
