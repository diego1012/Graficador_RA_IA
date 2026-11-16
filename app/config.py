"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os

APP_VERSION = "1.8.0"

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))
MAX_ROWS = int(os.getenv("MAX_ROWS", "500000"))
MAX_VARIABLES = int(os.getenv("MAX_VARIABLES", "50"))
DATASET_TTL_SECONDS = int(os.getenv("DATASET_TTL_SECONDS", "1800"))
MAX_DATASETS = int(os.getenv("MAX_DATASETS", "5"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
