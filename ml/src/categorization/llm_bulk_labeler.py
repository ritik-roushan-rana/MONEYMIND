# ml/src/categorization/llm_bulk_labeler.py

from __future__ import annotations

import json
import os
import re

from google import genai
from google.genai import types

from categorization.taxonomy import CATEGORIES

MODEL = "gemini-3.1-flash-lite"
BATCH_SIZE = 60


def _build_prompt(merchants: list[str], hints: dict[str, bool]) -> str:
    lines = []
    for i, m in enumerate(merchants):
        tag = " [P2P TRANSFER FRAGMENT]" if hints.get(m) else ""
        lines.append(f"{i+1}. {m}{tag}")
    numbered = "\n".join(lines)

    categories = "\n".join(f"- {c}" for c in CATEGORIES)
    return f"""You are labeling bank transaction merchant strings with a spending category.

Categories (pick exactly one per merchant, using this exact spelling):
{categories}

Merchant strings to label (these are already-cleaned fragments from Indian and UK \
bank statements — some are partial names, bank names, or person names from peer-to-peer \
transfers rather than clean business names; use your best judgement). Items tagged \
[P2P TRANSFER FRAGMENT] came from a UPI/NEFT/IMPS person-to-person transfer whose merchant \
name got stripped during cleaning — for these, default to "UPI transfer", "NEFT transfer", \
or "IMPS transfer" rather than guessing a business category from the leftover fragment:
{numbered}

Respond with ONLY a JSON array of exactly {len(merchants)} objects, no other text, no \
markdown fences. Each object must have this exact shape: {{"i": <the number from the \
list above>, "category": "<one category from the list>"}}. Include every number from 1 \
to {len(merchants)} exactly once — do not skip any, do not repeat any."""


def _extract_json_array(text: str) -> list[dict]:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def _label_batch(client: genai.Client, merchants: list[str], hints: dict[str, bool]) -> dict[str, str]:
    prompt = _build_prompt(merchants, hints)

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0),
    )
    raw_text = response.text

    def try_parse(text):
        entries = _extract_json_array(text)
        by_index: dict[int, str] = {}
        for entry in entries:
            idx = entry.get("i")
            cat = entry.get("category")
            if isinstance(idx, int) and 1 <= idx <= len(merchants):
                by_index[idx] = cat  # last write wins if the model duplicated an index
        return by_index

    try:
        by_index = try_parse(raw_text)
    except (json.JSONDecodeError, AttributeError, TypeError):
        by_index = {}

    missing = [i for i in range(1, len(merchants) + 1) if i not in by_index]

    if missing:
        missing_merchants = [merchants[i - 1] for i in missing]
        print(f"  Retrying {len(missing)} merchants missing/malformed from first pass...")
        retry_prompt = _build_prompt(missing_merchants, {m: hints.get(m, False) for m in missing_merchants})
        retry_response = client.models.generate_content(
            model=MODEL,
            contents=retry_prompt,
            config=types.GenerateContentConfig(temperature=0),
        )
        try:
            retry_by_index = try_parse(retry_response.text)  # indices here are local to the retry sub-batch
            for local_idx, cat in retry_by_index.items():
                original_idx = missing[local_idx - 1]
                by_index[original_idx] = cat
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass  # anything still missing after retry falls through to "Other" below

    result = {}
    for i, merchant in enumerate(merchants, start=1):
        label = by_index.get(i)
        result[merchant] = label if label in CATEGORIES else "Other"
    return result


def label_merchants(merchants: list[str], hints: dict[str, bool] | None = None) -> dict[str, str]:
    hints = hints or {}
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Add it to your .env and load it "
            "(e.g. via python-dotenv) before calling label_merchants()."
        )

    client = genai.Client(api_key=api_key)
    all_labels: dict[str, str] = {}

    for i in range(0, len(merchants), BATCH_SIZE):
        batch = merchants[i : i + BATCH_SIZE]
        batch_hints = {m: hints.get(m, False) for m in batch}
        print(f"Labeling batch {i // BATCH_SIZE + 1} ({len(batch)} merchants)...")
        all_labels.update(_label_batch(client, batch, batch_hints))

    return all_labels