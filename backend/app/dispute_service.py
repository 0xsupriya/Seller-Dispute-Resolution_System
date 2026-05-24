from typing import Dict, List

from sqlalchemy.orm import Session

from backend.app.models import Dispute, DisputeImage


def import_disputes(db: Session, rows: List[Dict]) -> Dict:
    imported = 0
    updated = 0
    errors = []

    for row in rows:
        transaction_id = row["transaction_id"]
        try:
            dispute = db.query(Dispute).filter(Dispute.transaction_id == transaction_id).first()
            is_new = dispute is None

            if is_new:
                dispute = Dispute(transaction_id=transaction_id)
                db.add(dispute)
                imported += 1
            else:
                updated += 1

            dispute.seller_name = row.get("seller_name", "")
            dispute.product_name = row.get("product_name", "")
            dispute.dispute_reason = row.get("dispute_reason", "")
            dispute.status = "pending"

            db.flush()

            db.query(DisputeImage).filter(DisputeImage.dispute_id == dispute.id).delete()

            for image_type, urls in row.get("images", {}).items():
                for url in urls:
                    db.add(
                        DisputeImage(
                            dispute_id=dispute.id,
                            image_type=image_type,
                            source_url=url,
                        )
                    )

            db.commit()
        except Exception as exc:
            db.rollback()
            errors.append({"transaction_id": transaction_id, "error": str(exc)})

    return {
        "imported": imported,
        "updated": updated,
        "total_rows": len(rows),
        "errors": errors,
    }
