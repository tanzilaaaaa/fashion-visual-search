"""Export CLIP ViT-B/32 (OpenAI weights) to two int8 ONNX graphs for the API.

Runs once, at Docker build time, in a builder stage that has PyTorch; the final
image only ships ONNX Runtime. Writes into ``--out``:

* ``visual.int8.onnx``: pixels [N,3,224,224] float32 → image features [N,512]
* ``text.int8.onnx``: tokens [N,77] int64 → text features [N,512]
* ``config.json``: file names, dimension, model name, precision

Weight-only int8 quantisation (MatMulNBits) shrinks the transformer weights ~4×; maths stays float32. The
``--check`` flag compares the int8 graphs against PyTorch on sample inputs and
fails the build if the embeddings drift (cosine below ``--min-cos``).

    python scripts/export_onnx.py --out artifacts/onnx --check
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import numpy as np
import torch


class _Visual(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, pixels):
        return self.model.encode_image(pixels)


class _TextBody(torch.nn.Module):
    """open_clip's ``_encode_text`` minus the token-embedding lookup.

    Inputs: token embeddings [N,77,512] (looked up outside the graph from a
    memory-mapped float16 table) and the index of each row's <end_of_text> token.
    Keeping the 49,408×512 table out of the graph removes ~100 MB of weights from
    the text model; only the rows a query uses are ever paged in.
    """

    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, embeddings, eot_index):
        m = self.model
        x = embeddings + m.positional_embedding
        x = m.transformer(x, attn_mask=m.attn_mask)
        x = m.ln_final(x)
        x = x[torch.arange(x.shape[0]), eot_index]
        return x @ m.text_projection


def export(model_name: str, pretrained: str, out: Path, check: bool, min_cos: float, visual_bits: int = 8) -> dict:
    import onnx
    import open_clip
    from onnxruntime.quantization.matmul_nbits_quantizer import MatMulNBitsQuantizer

    out.mkdir(parents=True, exist_ok=True)
    model, _, preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained)
    model.eval()
    tokenizer = open_clip.get_tokenizer(model_name)

    pixels = torch.randn(2, 3, 224, 224)
    tokens = tokenizer(["a red summer dress", "blue denim jacket"])
    embeddings = model.token_embedding(tokens).detach()
    eot_index = tokens.argmax(dim=-1)
    np.save(out / "token_embedding.f16.npy", model.token_embedding.weight.detach().numpy().astype(np.float16))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for name, module, example, inputs in (
            ("visual", _Visual(model), (pixels,), ["pixels"]),
            ("text", _TextBody(model), (embeddings, eot_index), ["embeddings", "eot_index"]),
        ):
            fp32 = tmp / f"{name}.onnx"
            axes = {i: {0: "batch"} for i in inputs} | {"features": {0: "batch"}}
            torch.onnx.export(
                module, example, str(fp32), input_names=inputs, output_names=["features"],
                dynamic_axes=axes, opset_version=17, dynamo=False,
            )
            onnx.checker.check_model(str(fp32))
            # Weight-only 8-bit (MatMulNBits): weights stored in int8 blocks of 32, maths in
            # float32. Unlike dynamic quantisation it never quantises activations, which CLIP's
            # text transformer (activation outliers) does not tolerate.
            bits = visual_bits if name == "visual" else 8
            q = MatMulNBitsQuantizer(onnx.load(str(fp32)), bits=bits, block_size=32, is_symmetric=True)
            q.process()
            q.model.save_model_to_file(str(out / f"{name}.int8.onnx"), use_external_data_format=False)

    config = {
        "model_name": model_name, "pretrained": pretrained, "dim": int(model.visual.output_dim),
        "visual": "visual.int8.onnx", "text": "text.int8.onnx",
        "precision": f"int{visual_bits} visual / int8 text weights",
        "text_inputs": "embeddings", "token_embedding": "token_embedding.f16.npy",
    }
    (out / "config.json").write_text(json.dumps(config, indent=2))

    if check:
        report = compare(model, preprocess, tokenizer, out)
        config["check"] = report
        (out / "config.json").write_text(json.dumps(config, indent=2))
        worst = min(report["text_min_cos"], report["image_min_cos"])
        print(json.dumps(report, indent=2))
        if worst < min_cos:
            raise SystemExit(f"int8 export drifted: min cosine {worst:.4f} < {min_cos}")
    return config


@torch.no_grad()
def compare(model, preprocess, tokenizer, out: Path) -> dict:
    """Cosine between PyTorch fp32 and ONNX int8 embeddings on fixed samples."""
    import sys

    from PIL import Image

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.services.onnx_encoder import OnnxClipEncoder
    from app.services.onnx_encoder import preprocess as np_preprocess

    enc = OnnxClipEncoder(out)
    texts = ["a red casual summer dress", "blue denim jacket", "black leather trousers", "a pleated mini skirt",
             "white linen shirt with long sleeves", "a strappy camisole", "floral print maxi dress"]
    sample_dir = Path(__file__).resolve().parents[1] / "artifacts" / "images"
    files = sorted(sample_dir.glob("*.webp"))[:: max(1, len(list(sample_dir.glob("*.webp"))) // 24)][:24]
    images = [Image.open(f).convert("RGB") for f in files]
    images += [Image.new("RGB", (240, 320), c) for c in ((200, 20, 30), (20, 40, 160), (240, 240, 240))]

    def unit(x):
        x = np.asarray(x, dtype=np.float32)
        return x / np.linalg.norm(x, axis=1, keepdims=True)

    t_ref = unit(model.encode_text(tokenizer(texts)).numpy())
    t_onx = unit(enc.encode_texts(texts))
    i_ref = unit(model.encode_image(torch.stack([preprocess(im) for im in images])).numpy())
    i_onx = unit(enc.encode_images(images))
    pre_diff = max(float(np.abs(preprocess(im).numpy() - np_preprocess(im)).max()) for im in images)
    return {
        "text_min_cos": float((t_ref * t_onx).sum(1).min()),
        "text_mean_cos": float((t_ref * t_onx).sum(1).mean()),
        "image_min_cos": float((i_ref * i_onx).sum(1).min()),
        "image_mean_cos": float((i_ref * i_onx).sum(1).mean()),
        "preprocess_max_abs_diff": pre_diff,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model-name", default="ViT-B-32-quickgelu")
    ap.add_argument("--pretrained", default="openai")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--min-cos", type=float, default=0.97)
    ap.add_argument("--visual-bits", type=int, default=8, choices=(4, 8))
    a = ap.parse_args()
    print(json.dumps(export(a.model_name, a.pretrained, a.out, a.check, a.min_cos, a.visual_bits), indent=2))


if __name__ == "__main__":
    main()
