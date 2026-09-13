# ml/src/agent/llm_explainer.py

from __future__ import annotations

import os
from typing import Optional

from google import genai
from google.genai import types

# Stronger than the flash-lite model used for bulk merchant labeling —
# that stage was simple closed-set classification; this stage needs to
# produce coherent, well-reasoned prose that correctly weighs multiple
# inputs against each other for a real end user, which benefits from a
# more capable model.
MODEL = "gemini-3.6-flash"


def _build_prompt(risk_assessment: dict, recommendations: dict, anomaly_flags: list[dict],
                   account_label: str) -> str:
    factors_text = "\n".join(
        f"- {f['name']}: {f['explanation']} (contributes {f['contribution']} risk points, weight {f['weight']})"
        for f in risk_assessment["factors"]
    )

    recs_text = "\n".join(
        f"- [{r['priority']}] {r['title']}: {r['rationale']}"
        for r in recommendations["recommendations"]
    )

    if anomaly_flags:
        anomalies_text = "\n".join(
            f"- {a['txn_date']} {a['clean_merchant']} ({a['category']}): {a['amount']} — flagged for {a['anomaly_types']}"
            for a in anomaly_flags[:5]
        )
    else:
        anomalies_text = "No unusual or flagged transactions were detected."

    confidence_note = f"\nNote on data: {risk_assessment['summary_note']}" if risk_assessment.get("summary_note") else ""

    return f"""You are writing a short, plain-language financial summary for a user of a personal finance app, based on an automated analysis of their transaction history.

ACCOUNT: {account_label}

RISK ASSESSMENT:
Overall risk level: {risk_assessment['risk_level']} (score {risk_assessment['overall_score']}/100)
Data confidence: {risk_assessment['data_confidence']}{confidence_note}

Contributing factors, ranked by how much each affects the score:
{factors_text}

RECOMMENDATIONS GENERATED (already ordered by priority — the first one is the most important):
{recs_text}

FLAGGED TRANSACTIONS:
{anomalies_text}

Write a warm, clear, non-judgmental summary (3-4 short paragraphs, under 200 words total) that:
1. States the overall risk level and the ONE or TWO biggest drivers behind it, in plain language — no jargon like "z-score," "coefficient of variation," or "isolation forest."
2. Leads with the single most important recommendation (the first one listed above) and briefly explains why it matters most right now, before mentioning any others.
3. Mentions flagged transactions only if genuinely worth a second look — skip this section entirely if the flagged list is empty or clearly minor.
4. Ends on an encouraging, forward-looking note. This is meant to help someone improve their financial position, not to make them feel judged for past spending.

Hard constraints:
- Do NOT recommend specific investment products, specific amounts to invest, or make any guarantees about financial outcomes.
- Do NOT invent any numbers, transactions, or details not present in the data above.
- Address the reader directly as "you".
- Do not repeat the disclaimer text — the app displays that separately."""


def generate_explanation(risk_assessment: dict, recommendations: dict, anomaly_flags: list[dict],
                          account_label: str = "your account") -> dict:
    """risk_assessment: output of risk_rubric.assessment_to_dict()
    recommendations: output of recommendation_engine.generate_recommendations()
    anomaly_flags: list of dict records for this account only (e.g. from
    anomaly_flags.parquet filtered to one source_file) — pass [] if none."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Add it to your .env and load it "
            "(e.g. via python-dotenv) before calling generate_explanation()."
        )

    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(risk_assessment, recommendations, anomaly_flags, account_label)

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.4),
    )

    return {
        "explanation": response.text.strip(),
        "disclaimer": recommendations.get("disclaimer", ""),
    }