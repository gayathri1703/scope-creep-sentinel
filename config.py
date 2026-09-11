"""
Shared configuration and model-provider bootstrap helpers.
"""

from __future__ import annotations

import os
from pathlib import Path

from strands.models import BedrockModel
from strands.models.gemini import GeminiModel


PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"

SOW_PATH = DATA_DIR / "sample_sow.json"
HISTORY_PATH = DATA_DIR / "history_ecommerce_website.json"


# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

BEDROCK_MODEL_ID = "anthropic.claude-sonnet-4-6"
BEDROCK_REGION = "ap-south-1"

# Current Gemini model available for new users.
GEMINI_MODEL_ID = "gemini-3.6-flash"


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


# ---------------------------------------------------------------------------
# Runtime configuration
# ---------------------------------------------------------------------------

# MOCK_MODE=false -> use a real Strands model.
# MOCK_MODE=true  -> use deterministic mock agents.

MOCK_MODE = _parse_bool(
    os.environ.get("MOCK_MODE", "true")
)

MODEL_PROVIDER = os.environ.get(
    "MODEL_PROVIDER",
    "bedrock",
).strip().lower()


def build_model():
    """Build the selected real Strands model provider."""

    if MODEL_PROVIDER == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set."
            )

        return GeminiModel(
            client_args={
                "api_key": api_key,
            },
            model_id=GEMINI_MODEL_ID,
            params={
                "max_output_tokens": 2048,
            },
        )

    if MODEL_PROVIDER == "bedrock":
        return BedrockModel(
            model_id=BEDROCK_MODEL_ID,
            region_name=BEDROCK_REGION,
        )

    raise ValueError(
        f"Unsupported MODEL_PROVIDER: {MODEL_PROVIDER!r}"
    )