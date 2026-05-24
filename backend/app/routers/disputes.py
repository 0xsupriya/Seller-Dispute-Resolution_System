from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.analysis_pipeline import analyze_all, analyze_dispute, save_human_review
from backend.app.database import get_db
from backend.app.dispute_service import import_disputes
from backend.app.excel_parser import parse_excel
from backend.app.image_service import download_all_images, download_dispute_images
from backend.app.models import AnalysisResult, Dispute

router = APIRouter(prefix="/api/disputes", tags=["disputes"])


class ReviewRequest(BaseModel):
    decision: str = "approved"
    final_compensation_pct: Optional[float] = None
    notes: str = ""


@router.post("/upload")
async def upload_disputes(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Please upload an Excel file (.xlsx)")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    rows = parse_excel(file_bytes)
    if not rows:
        raise HTTPException(status_code=400, detail="No dispute rows found in Excel")

    result = import_disputes(db, rows)
    return {"message": "Excel imported successfully", **result}


@router.get("")
def list_disputes(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)) -> dict:
    total = db.query(Dispute).count()
    disputes = (
        db.query(Dispute)
        .order_by(Dispute.id.desc())
        .offset(skip)
        .limit(min(limit, 100))
        .all()
    )
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [
            {
                "transaction_id": d.transaction_id,
                "seller_name": d.seller_name,
                "product_name": d.product_name,
                "dispute_reason": d.dispute_reason,
                "status": d.status,
                "image_count": len(d.images),
            }
            for d in disputes
        ],
    }


@router.post("/download-all")
def download_all(limit: int = 10, db: Session = Depends(get_db)) -> dict:
    return download_all_images(db, limit=limit if limit > 0 else None)


@router.post("/analyze-all")
def analyze_all_disputes(limit: int = 10, db: Session = Depends(get_db)) -> dict:
    return analyze_all(db, limit=limit if limit > 0 else None)


@router.get("/{transaction_id}")
def get_dispute(transaction_id: str, db: Session = Depends(get_db)) -> dict:
    dispute = db.query(Dispute).filter(Dispute.transaction_id == transaction_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    images = {"seller": [], "pdp": [], "dsqc": []}
    for image in dispute.images:
        bucket = images.get(image.image_type, [])
        bucket.append(
            {
                "source_url": image.source_url,
                "file_path": image.file_path,
                "url": f"/files/{image.file_path.replace(chr(92), '/')}" if image.file_path else None,
            }
        )
        images[image.image_type] = bucket

    latest = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.dispute_id == dispute.id)
        .order_by(AnalysisResult.id.desc())
        .first()
    )

    review = dispute.human_review
    return {
        "transaction_id": dispute.transaction_id,
        "seller_name": dispute.seller_name,
        "product_name": dispute.product_name,
        "dispute_reason": dispute.dispute_reason,
        "product_cost_inr": float(dispute.product_cost_inr) if dispute.product_cost_inr else None,
        "status": dispute.status,
        "images": images,
        "latest_analysis": latest.result_json if latest else None,
        "human_review": {
            "decision": review.decision,
            "final_compensation_pct": float(review.final_compensation_pct)
            if review and review.final_compensation_pct
            else None,
            "notes": review.notes if review else None,
        }
        if review
        else None,
    }


@router.post("/{transaction_id}/download-images")
def download_images(transaction_id: str, db: Session = Depends(get_db)) -> dict:
    dispute = db.query(Dispute).filter(Dispute.transaction_id == transaction_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return download_dispute_images(db, dispute)


@router.post("/{transaction_id}/analyze")
def analyze(transaction_id: str, db: Session = Depends(get_db)) -> dict:
    dispute = db.query(Dispute).filter(Dispute.transaction_id == transaction_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return analyze_dispute(db, dispute)


@router.post("/{transaction_id}/review")
def review_dispute(
    transaction_id: str,
    body: ReviewRequest,
    db: Session = Depends(get_db),
) -> dict:
    dispute = db.query(Dispute).filter(Dispute.transaction_id == transaction_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return save_human_review(
        db,
        dispute,
        body.decision,
        body.final_compensation_pct,
        body.notes,
    )
