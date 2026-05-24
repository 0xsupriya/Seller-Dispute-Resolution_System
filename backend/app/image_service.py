from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.image_downloader import download_source, safe_name
from backend.app.models import Dispute, DisputeImage


def _storage_root() -> Path:
    return Path(settings.storage_path)


def download_dispute_images(db: Session, dispute: Dispute) -> Dict:
    root = _storage_root()
    transaction_dir = root / safe_name(dispute.transaction_id)
    downloaded = 0
    errors: List[str] = []

    for image in dispute.images:
        if image.file_path and Path(image.file_path).exists():
            downloaded += 1
            continue

        target_dir = transaction_dir / image.image_type
        try:
            saved = download_source(image.source_url, target_dir, f"{image.image_type}_{image.id}")
            if saved:
                saved_path = Path(saved[0])
                try:
                    image.file_path = str(saved_path.relative_to(root))
                except ValueError:
                    image.file_path = str(saved_path)
                downloaded += 1
            else:
                errors.append(f"{image.image_type}: no file from {image.source_url}")
        except Exception as exc:
            errors.append(f"{image.image_type}: {image.source_url} -> {exc}")

    if downloaded > 0:
        dispute.status = "images_downloaded"

    db.commit()
    return {
        "transaction_id": dispute.transaction_id,
        "downloaded": downloaded,
        "total_images": len(dispute.images),
        "errors": errors,
    }


def download_all_images(db: Session, limit: Optional[int] = None) -> Dict:
    query = db.query(Dispute).order_by(Dispute.id.asc())
    if limit:
        query = query.limit(limit)
    disputes = query.all()

    results = []
    for dispute in disputes:
        results.append(download_dispute_images(db, dispute))

    return {
        "processed": len(results),
        "results": results,
    }
