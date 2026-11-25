"""Precompute the zero-shot label prototypes into ``artifacts/prototypes.npz``.

Photo searches guess an upload's category and colour by comparing it with text
"prototypes" ("a photo of a skirt.", "a red garment." …). Computing them takes ~80
text encodings. Doing it once here means a cold-started server never pays for it.

    python scripts/precompute_prototypes.py --artifacts artifacts
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402

from app.container import build_container  # noqa: E402
from app.core.config import Settings  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--artifacts", type=Path, required=True)
    a = ap.parse_args()
    c = build_container(Settings(_env_file=None, artifacts_dir=a.artifacts, users_db_path=a.artifacts / "_tmp.db"))
    if not c.ready:
        raise SystemExit(f"backend not ready: {c.startup_error}")
    c.search.infer_attributes(c.embedding.encode_image(Image.new("RGB", (224, 224), (128, 128, 128))))
    c.embedding.save_prototypes(a.artifacts / "prototypes.npz")
    (a.artifacts / "_tmp.db").unlink(missing_ok=True)
    print("saved", a.artifacts / "prototypes.npz", "for", sorted(c.embedding._prototypes))


if __name__ == "__main__":
    main()
