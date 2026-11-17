# Load torch before faiss on macOS (see app/_platform.py) — runs before conftest.
import app._platform  # noqa: F401
