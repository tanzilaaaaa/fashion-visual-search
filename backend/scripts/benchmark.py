"""Measure end-to-end API latency (PRD §3.5 / §12.3) against a running backend.

    python scripts/benchmark.py --base-url http://localhost:8000 --image some.jpg
"""

from __future__ import annotations

import argparse
import json
import statistics
import time

import httpx

QUERIES = [
    "black oversized hoodie", "white summer dress", "red casual summer dress", "blue denim jacket",
    "pleated mini skirt", "grey sweatpants", "striped t-shirt", "long winter coat", "denim shorts", "silk slip dress",
]


def stats(samples: list[float]) -> dict:
    s = sorted(samples)
    return {
        "n": len(s),
        "mean_ms": round(statistics.mean(s), 1),
        "p50_ms": round(s[len(s) // 2], 1),
        "p95_ms": round(s[min(len(s) - 1, int(len(s) * 0.95))], 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--image", help="optional image for image-search latency")
    ap.add_argument("--rounds", type=int, default=3)
    a = ap.parse_args()

    with httpx.Client(base_url=a.base_url, timeout=60) as c:
        c.get("/health").raise_for_status()
        text = []
        for _ in range(a.rounds):
            for q in QUERIES:
                t = time.perf_counter()
                c.post("/search/text", json={"query": q}).raise_for_status()
                text.append((time.perf_counter() - t) * 1000)
        report = {"text_search": stats(text)}
        if a.image:
            img = []
            data = open(a.image, "rb").read()
            for _ in range(a.rounds * 3):
                t = time.perf_counter()
                c.post("/search/image", files={"file": ("q.jpg", data, "image/jpeg")}).raise_for_status()
                img.append((time.perf_counter() - t) * 1000)
            report["image_search"] = stats(img)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
