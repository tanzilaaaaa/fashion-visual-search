"""Build the real index on a Kaggle GPU through the Kaggle API.

    python ml/kaggle/run_kaggle.py push        # bundle fvs_ml into a kernel and run it
    python ml/kaggle/run_kaggle.py status      # queued / running / complete / error
    python ml/kaggle/run_kaggle.py download    # fetch fvs_artifacts.tar → backend/artifacts/
    python ml/kaggle/run_kaggle.py logs        # fetch the build log only

Authentication uses the Kaggle CLI's own credentials (``~/.kaggle/access_token`` or
``kaggle.json``). Nothing secret is written to the repo. The kernel is private.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGE = ROOT / "ml" / "fvs_ml"
COMPAT = ROOT / "backend" / "app" / "data" / "compatibility.json"
DATASET = "thusharanair/deepfashion2-original-with-dataframes"
DEFAULT_SLUG = "fvs-build-index"


def kaggle_bin() -> str:
    exe = Path(sys.executable).with_name("kaggle")
    return str(exe) if exe.exists() else (shutil.which("kaggle") or "kaggle")


def kaggle(*args: str, capture: bool = True) -> str:
    res = subprocess.run([kaggle_bin(), *args], capture_output=capture, text=True)
    if res.returncode != 0:
        raise SystemExit(f"kaggle {' '.join(args)} failed:\n{res.stdout}\n{res.stderr}")
    return res.stdout if capture else ""


def username() -> str:
    if os.environ.get("KAGGLE_USERNAME"):
        return os.environ["KAGGLE_USERNAME"]
    m = re.search(r"username:\s*(\S+)", kaggle("config", "view"))
    if not m or m.group(1) == "None":
        raise SystemExit("Could not determine the Kaggle username; set KAGGLE_USERNAME.")
    return m.group(1)


def bundle() -> str:
    """base64 tar.gz of the fvs_ml sources + the compatibility map."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for f in sorted(PACKAGE.rglob("*.py")):
            tf.add(f, arcname=str(Path("fvs_ml") / f.relative_to(PACKAGE)))
        tf.add(COMPAT, arcname="compatibility.json")
    return base64.b64encode(buf.getvalue()).decode()


def cmd_push(a: argparse.Namespace) -> None:
    user = username()
    settings = {
        "target_items": a.target_items, "batch_size": a.batch_size, "num_workers": a.num_workers,
        "seed": a.seed, "finetune": not a.no_finetune, "ft_epochs": a.ft_epochs, "ft_max_items": a.ft_max_items,
    }
    src = (HERE / "kernel_template.py").read_text()
    src = src.replace("__BUNDLE__", bundle()).replace("__SETTINGS__", json.dumps(settings))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "build.py").write_text(src)
        (tmp / "kernel-metadata.json").write_text(json.dumps({
            "id": f"{user}/{a.slug}",
            "title": a.slug,
            "code_file": "build.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": True,
            "enable_gpu": True,
            "enable_tpu": False,
            "enable_internet": True,
            "dataset_sources": [DATASET],
            "competition_sources": [],
            "kernel_sources": [],
            "model_sources": [],
        }, indent=2))
        print(kaggle("kernels", "push", "-p", str(tmp), "--accelerator", a.accelerator))
    print(f"Pushed {user}/{a.slug} with {settings}")


def cmd_dry_run(a: argparse.Namespace) -> None:
    """Run the generated kernel locally against a small DF2-format folder."""
    work = Path(a.work).resolve()
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    settings = {"target_items": a.target_items, "batch_size": 32, "num_workers": 0, "seed": 42,
                "finetune": True, "ft_epochs": 3, "ft_max_items": 2_000}
    src = (HERE / "kernel_template.py").read_text()
    (work / "build.py").write_text(src.replace("__BUNDLE__", bundle()).replace("__SETTINGS__", json.dumps(settings)))
    env = {**os.environ, "FVS_KAGGLE_WORK": str(work), "FVS_KAGGLE_INPUT": str(Path(a.dataset).resolve()),
           "FVS_SKIP_PIP": "1"}
    subprocess.run([sys.executable, "-I", str(work / "build.py")], env=env, check=True)
    print(sorted(p.name for p in work.iterdir()))


def cmd_status(a: argparse.Namespace) -> None:
    print(kaggle("kernels", "status", f"{username()}/{a.slug}").strip())


def _fetch_output(a: argparse.Namespace, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    kaggle("kernels", "output", f"{username()}/{a.slug}", "-p", str(dest), "-o")


def cmd_logs(a: argparse.Namespace) -> None:
    last = HERE / "last_run"
    _fetch_output(a, last)
    for name in ("run_summary.json", "build.log"):
        p = last / name
        if p.exists():
            print(f"── {name}")
            print(p.read_text()[-4000:])


def cmd_download(a: argparse.Namespace) -> None:
    last = HERE / "last_run"
    _fetch_output(a, last)
    tar = last / "fvs_artifacts.tar"
    if not tar.exists():
        raise SystemExit(f"{tar} not found. Is the kernel complete? Try `status` and `logs`.")
    dest = Path(a.dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for child in dest.iterdir():                    # replace the previous catalogue completely
        if child.name == ".gitkeep":
            continue
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    with tarfile.open(tar) as tf:
        try:
            tf.extractall(dest, filter="data")
        except TypeError:
            tf.extractall(dest)
    tar.unlink()                                    # disk is tight; the extracted copy is enough
    manifest = json.loads((dest / "manifest.json").read_text())
    print(f"Extracted {manifest['item_count']} items into {dest} (adapter: {manifest.get('adapter')})")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--slug", default=DEFAULT_SLUG)
    sub = p.add_subparsers(dest="cmd", required=True)
    push = sub.add_parser("push")
    push.add_argument("--target-items", type=int, default=50_000)
    push.add_argument("--batch-size", type=int, default=512)
    push.add_argument("--num-workers", type=int, default=8)  # I/O-latency bound on Kaggle input
    push.add_argument("--seed", type=int, default=42)
    push.add_argument("--no-finetune", action="store_true")
    push.add_argument("--ft-epochs", type=int, default=40)
    push.add_argument("--ft-max-items", type=int, default=60_000)
    push.add_argument("--accelerator", default="NvidiaTeslaT4")
    dry = sub.add_parser("dry-run")
    dry.add_argument("--dataset", required=True)
    dry.add_argument("--work", required=True)
    dry.add_argument("--target-items", type=int, default=300)
    sub.add_parser("status")
    sub.add_parser("logs")
    dl = sub.add_parser("download")
    dl.add_argument("--dest", default=str(ROOT / "backend" / "artifacts"))
    a = p.parse_args()
    commands = {"push": cmd_push, "dry-run": cmd_dry_run, "status": cmd_status, "logs": cmd_logs,
                "download": cmd_download}
    commands[a.cmd](a)


if __name__ == "__main__":
    main()
