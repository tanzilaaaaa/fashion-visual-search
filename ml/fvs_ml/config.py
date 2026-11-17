"""Central configuration and vocabulary for the offline pipeline.

Everything that defines *which* catalogue gets built lives here, so a build is
reproducible from (dataset version, this file, seed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------- #
# DeepFashion2 vocabulary
# --------------------------------------------------------------------------- #
# Official category ids → names (DeepFashion2 annotation schema).
CATEGORIES: dict[int, str] = {
    1: "short sleeve top",
    2: "long sleeve top",
    3: "short sleeve outwear",
    4: "long sleeve outwear",
    5: "vest",
    6: "sling",
    7: "shorts",
    8: "trousers",
    9: "skirt",
    10: "short sleeve dress",
    11: "long sleeve dress",
    12: "vest dress",
    13: "sling dress",
}
CATEGORY_NAMES: list[str] = [CATEGORIES[i] for i in sorted(CATEGORIES)]

SCALE = {1: "small", 2: "moderate", 3: "large"}
OCCLUSION = {1: "slight", 2: "medium", 3: "heavy"}
VIEWPOINT = {1: "not worn", 2: "frontal", 3: "side or back"}
ZOOM_IN = {1: "none", 2: "medium", 3: "large"}

# Colour vocabulary for zero-shot tagging (DeepFashion2 has no colour labels).
COLOURS: list[str] = [
    "black", "white", "grey", "red", "pink", "orange", "yellow",
    "green", "blue", "navy", "purple", "brown", "beige",
]
# Below this softmax confidence an item is tagged "multicolour" instead.
COLOUR_MIN_CONFIDENCE = 0.35


def slug(name: str) -> str:
    """'short sleeve top' -> 'short_sleeve_top' (stable machine key)."""
    return "_".join(name.lower().replace("-", " ").split())


@dataclass
class PipelineConfig:
    """Parameters of one catalogue build."""

    dataset_root: Path
    output_dir: Path
    splits: tuple[str, ...] = ("train", "validation")
    target_items: int = 50_000
    eval_fraction_of_validation: float = 0.25
    eval_max_images: int = 4_000
    seed: int = 42
    model_name: str = "ViT-B-32-quickgelu"
    pretrained: str = "openai"
    batch_size: int = 256
    num_workers: int = 2
    io_workers: int = 32          # threads for reading annotation files (latency-bound on network FS)
    thumb_size: int = 256
    crop_padding: float = 0.06
    min_box_side: int = 32
    work_dir: Path = field(default=Path("work"))

    @property
    def images_dir(self) -> Path:
        return self.output_dir / "images"
