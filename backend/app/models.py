from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Dispute(Base):
    """One seller claim row from the Excel sheet."""

    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True)
    transaction_id = Column(String(64), unique=True, nullable=False, index=True)
    seller_name = Column(String(255), nullable=False, default="")
    product_name = Column(Text, nullable=False, default="")
    dispute_reason = Column(String(128), nullable=False, default="")
    product_cost_inr = Column(Numeric(12, 2), nullable=True)
    status = Column(String(32), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    images = relationship("DisputeImage", back_populates="dispute", cascade="all, delete-orphan")
    analysis_results = relationship(
        "AnalysisResult", back_populates="dispute", cascade="all, delete-orphan"
    )
    human_review = relationship(
        "HumanReview", back_populates="dispute", uselist=False, cascade="all, delete-orphan"
    )


class DisputeImage(Base):
    """PDP, DSQC, or seller photo — URL from Excel, local path after download."""

    __tablename__ = "dispute_images"

    id = Column(Integer, primary_key=True)
    dispute_id = Column(Integer, ForeignKey("disputes.id", ondelete="CASCADE"), nullable=False)
    image_type = Column(String(16), nullable=False)  # pdp | dsqc | seller
    source_url = Column(Text, nullable=False, default="")
    file_path = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    dispute = relationship("Dispute", back_populates="images")


class AnalysisResult(Base):
    """AI output for a dispute (similarity scores + full JSON verdict)."""

    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True)
    dispute_id = Column(Integer, ForeignKey("disputes.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(32), nullable=False, default="mock")
    similarity_scores = Column(JSONB, nullable=True)
    result_json = Column(JSONB, nullable=True)
    recommended_compensation_pct = Column(Numeric(5, 2), nullable=True)
    recommended_amount_inr = Column(Numeric(12, 2), nullable=True)
    status = Column(String(32), nullable=False, default="completed")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    dispute = relationship("Dispute", back_populates="analysis_results")


class HumanReview(Base):
    """Human override after AI recommendation."""

    __tablename__ = "human_reviews"

    id = Column(Integer, primary_key=True)
    dispute_id = Column(
        Integer, ForeignKey("disputes.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    decision = Column(String(32), nullable=False, default="pending")  # approved | overridden | rejected
    final_compensation_pct = Column(Numeric(5, 2), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    dispute = relationship("Dispute", back_populates="human_review")
