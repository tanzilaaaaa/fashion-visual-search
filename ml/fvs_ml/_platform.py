"""macOS-only shim: the faiss-cpu and torch wheels each bundle libomp.

Loading faiss first segfaults when CLIP initialises; loading torch first and
allowing the duplicate runtime works, provided FAISS runs single-threaded. Linux (Docker, Hugging Face, Kaggle) is
unaffected, so this is a no-op there.
"""

import os
import sys

if sys.platform == "darwin":
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    try:
        import torch  # noqa: F401  (must be imported before faiss)
    except ImportError:
        pass
    try:
        import faiss

        # Two OpenMP runtimes in one process crash under multi-threaded search.
        faiss.omp_set_num_threads(1)
    except ImportError:
        pass
