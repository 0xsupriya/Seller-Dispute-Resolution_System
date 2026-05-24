from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.analysis_service import analyze_with_mock, analyze_with_openai
from backend.app.config import settings
from backend.app.models import AnalysisResult, Dispute, HumanReview
from backend.app.similarity import compute_similarity_scores


def _images_by_type(dispute: Dispute) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {"pdp": [], "dsqc": [], "seller": []}
    for image in dispute.images:
        if image.file_path:
            grouped.setdefault(image.image_type, []).append(image.file_path)
    return grouped


def analyze_dispute(db: Session, dispute: Dispute) -> Dict:
    images_by_type = _images_by_type(dispute)
    scores = compute_similarity_scores(images_by_type)

    if settings.ai_provider == "openai" and settings.openai_api_key:
        result = analyze_with_openai(dispute, images_by_type, scores)
        provider = result.get("provider", "openai")
    else:
        result = analyze_with_mock(dispute, images_by_type)
        provider = "mock"

    compensation = result.get("compensation", {})
    record = AnalysisResult(
        dispute_id=dispute.id,
        provider=provider,
        similarity_scores=scores,
        result_json=result,
        recommended_compensation_pct=compensation.get("recommended_pct"),
        recommended_amount_inr=compensation.get("recommended_amount_inr"),
        status="completed",
    )
    db.add(record)
    dispute.status = "analyzed"
    db.commit()
    db.refresh(record)

    return {
        "analysis_id": record.id,
        "transaction_id": dispute.transaction_id,
        "provider": provider,
        "similarity_scores": scores,
        "result": result,
    }


def analyze_all(db: Session, limit: Optional[int] = None) -> Dict:
    query = db.query(Dispute).order_by(Dispute.id.asc())
    if limit:
        query = query.limit(limit)
    disputes = query.all()

    results = []
    errors = []
    for dispute in disputes:
        try:
            results.append(analyze_dispute(db, dispute))
        except Exception as exc:
            errors.append({"transaction_id": dispute.transaction_id, "error": str(exc)})

    return {"processed": len(results), "results": results, "errors": errors}


def save_human_review(
    db: Session,
    dispute: Dispute,
    decision: str,
    final_compensation_pct: Optional[float],
    notes: str,
) -> Dict:
    review = dispute.human_review
    if review is None:
        review = HumanReview(dispute_id=dispute.id)
        db.add(review)

    review.decision = decision
    review.final_compensation_pct = final_compensation_pct
    review.notes = notes
    dispute.status = "reviewed"
    db.commit()

    return {
        "transaction_id": dispute.transaction_id,
        "decision": decision,
        "final_compensation_pct": final_compensation_pct,
        "notes": notes,
    }
