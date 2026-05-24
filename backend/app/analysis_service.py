import base64
import json
from pathlib import Path
from typing import Dict, List, Optional

from backend.app.config import settings
from backend.app.similarity import compute_similarity_scores

DEFAULT_PRODUCT_COST = 5000.0


def _avg_score(scores: Dict[str, Optional[float]]) -> Optional[float]:
    values = [v for v in scores.values() if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _compensation_pct(dispute_reason: str, scores: Dict[str, Optional[float]]) -> float:
    reason = dispute_reason.lower()
    avg = _avg_score(scores) or 0.5
    pdp_seller = scores.get("pdp_vs_seller")

    if "wrong product" in reason or (pdp_seller is not None and pdp_seller < 0.35):
        return 100.0
    if "empty box" in reason or "partial product" in reason or "missing" in reason:
        return 100.0
    if "damaged" in reason:
        return 25.0 if avg >= 0.5 else 100.0
    if "used" in reason:
        return 100.0 if avg < 0.55 else 30.0
    return 30.0 if avg >= 0.5 else 100.0


def _build_result(dispute, scores: Dict[str, Optional[float]], provider: str) -> Dict:
    product_cost = float(dispute.product_cost_inr or DEFAULT_PRODUCT_COST)
    pct = _compensation_pct(dispute.dispute_reason, scores)
    amount = round(product_cost * pct / 100, 2)
    avg = _avg_score(scores)
    pdp_seller = scores.get("pdp_vs_seller")

    same_product = pdp_seller is None or pdp_seller >= 0.4
    condition = "refurbishable" if pct <= 30 else "unsellable"

    return {
        "transaction_id": dispute.transaction_id,
        "provider": provider,
        "product_match": {
            "same_product": same_product,
            "confidence": round(avg or 0.5, 2),
            "evidence": "Visual similarity across PDP, DSQC, and seller photos.",
        },
        "similarity_scores": scores,
        "observations": {
            "visible_damage": ["See dispute reason: " + dispute.dispute_reason],
            "packaging": "Assessed from available photos",
            "accessories": "Not fully verified in MVP",
            "condition": condition,
        },
        "dispute_validation": {
            "claimed_reason": dispute.dispute_reason,
            "validated": True,
            "severity": "minor" if pct <= 30 else "major",
        },
        "attribution": {
            "likely_source": "inconclusive",
            "confidence": "medium",
            "rationale": "MVP rules-based assessment from photo similarity and claim type.",
        },
        "compensation": {
            "recommended_pct": pct,
            "recommended_amount_inr": amount,
            "tier": "refurbishable" if pct <= 30 else "full",
            "product_cost_inr": product_cost,
        },
        "review": {
            "status": "pending_human_review",
            "flags": [],
            "summary": f"Recommend {pct}% compensation ({amount} INR) for {dispute.dispute_reason}.",
        },
    }


def analyze_with_mock(dispute, images_by_type: Dict[str, List[str]]) -> Dict:
    scores = compute_similarity_scores(images_by_type)
    return _build_result(dispute, scores, provider="mock")


def _encode_image(path: str) -> Optional[str]:
    file_path = Path(path)
    if not file_path.exists():
        return None
    mime = "image/jpeg"
    if file_path.suffix.lower() == ".png":
        mime = "image/png"
    encoded = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def analyze_with_openai(dispute, images_by_type: Dict[str, List[str]], scores: Dict) -> Dict:
    try:
        import urllib.request

        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        content = [
            {
                "type": "text",
                "text": (
                    "You are a seller dispute assessor for an e-commerce returns platform. "
                    "Compare PDP (catalog), DSQC (pickup), and seller (received) photos. "
                    f"Dispute reason: {dispute.dispute_reason}. Product: {dispute.product_name}. "
                    f"Similarity scores: {json.dumps(scores)}. "
                    "Return JSON with keys: product_match, observations, dispute_validation, "
                    "attribution, compensation (recommended_pct, recommended_amount_inr, tier), review."
                ),
            }
        ]

        for label, paths in images_by_type.items():
            for path in paths[:1]:
                data_url = _encode_image(path)
                if data_url:
                    content.append({"type": "text", "text": f"{label.upper()} image:"})
                    content.append({"type": "image_url", "image_url": {"url": data_url}})

        payload = {
            "model": "gpt-4o-mini",
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 1200,
        }

        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=90) as response:
            body = json.loads(response.read().decode("utf-8"))

        ai_json = json.loads(body["choices"][0]["message"]["content"])
        ai_json["transaction_id"] = dispute.transaction_id
        ai_json["provider"] = "openai"
        ai_json["similarity_scores"] = scores

        product_cost = float(dispute.product_cost_inr or DEFAULT_PRODUCT_COST)
        comp = ai_json.get("compensation", {})
        if "recommended_amount_inr" not in comp and "recommended_pct" in comp:
            comp["recommended_amount_inr"] = round(product_cost * float(comp["recommended_pct"]) / 100, 2)
        comp["product_cost_inr"] = product_cost
        ai_json["compensation"] = comp
        return ai_json
    except Exception:
        result = analyze_with_mock(dispute, images_by_type)
        result["provider"] = "mock_fallback"
        result["review"]["flags"] = ["openai_failed_used_mock"]
        return result
