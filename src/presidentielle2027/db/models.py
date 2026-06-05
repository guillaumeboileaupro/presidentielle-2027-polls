from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )


class Source(Base, TimestampMixin):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="webpage", nullable=False)
    language: Mapped[str | None] = mapped_column(String(10))
    raw_storage_path: Mapped[str | None] = mapped_column(String(512))
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    polls: Mapped[list[Poll]] = relationship(back_populates="source")


class PollingCompany(Base, TimestampMixin):
    __tablename__ = "polling_companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    website_url: Mapped[str | None] = mapped_column(String(2048))
    notes: Mapped[str | None] = mapped_column(Text)

    polls: Mapped[list[Poll]] = relationship(back_populates="polling_company")


class Poll(Base, TimestampMixin):
    __tablename__ = "polls"
    __table_args__ = (UniqueConstraint("poll_id", name="uq_polls_poll_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    polling_company_id: Mapped[int | None] = mapped_column(ForeignKey("polling_companies.id"))
    commissioner: Mapped[str | None] = mapped_column(String(255))
    media_partner: Mapped[str | None] = mapped_column(String(255))
    fieldwork_start_date: Mapped[date | None] = mapped_column(Date)
    fieldwork_end_date: Mapped[date | None] = mapped_column(Date)
    publication_date: Mapped[date | None] = mapped_column(Date)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    population: Mapped[str | None] = mapped_column(String(255))
    collection_method: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False)
    quota_method: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    round: Mapped[str] = mapped_column(String(50), nullable=False)
    undecided_percent: Mapped[float | None] = mapped_column(Float)
    abstention_estimate: Mapped[float | None] = mapped_column(Float)
    registered_voters_basis: Mapped[bool | None] = mapped_column(Boolean)
    raw_text_context: Mapped[str | None] = mapped_column(Text)
    extraction_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    source: Mapped[Source] = relationship(back_populates="polls")
    polling_company: Mapped[PollingCompany | None] = relationship(back_populates="polls")
    scenarios: Mapped[list[PollScenario]] = relationship(back_populates="poll", cascade="all, delete-orphan")
    adjustments: Mapped[list[Adjustment]] = relationship(back_populates="poll")


class PollScenario(Base, TimestampMixin):
    __tablename__ = "poll_scenarios"
    __table_args__ = (UniqueConstraint("poll_id", "scenario_name", name="uq_poll_scenario"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("polls.id"), nullable=False)
    scenario_name: Mapped[str] = mapped_column(String(255), nullable=False)
    round: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    poll: Mapped[Poll] = relationship(back_populates="scenarios")
    results: Mapped[list[PollResult]] = relationship(back_populates="scenario", cascade="all, delete-orphan")
    smoothed_estimates: Mapped[list[ForecastOrSmoothedEstimate]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )


class Candidate(Base, TimestampMixin):
    __tablename__ = "candidates"
    __table_args__ = (UniqueConstraint("candidate_name", "candidate_party", name="uq_candidate_name_party"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    candidate_party: Mapped[str | None] = mapped_column(String(255))
    political_family: Mapped[str | None] = mapped_column(String(255))

    results: Mapped[list[PollResult]] = relationship(back_populates="candidate")
    smoothed_estimates: Mapped[list[ForecastOrSmoothedEstimate]] = relationship(back_populates="candidate")


class PollResult(Base, TimestampMixin):
    __tablename__ = "poll_results"
    __table_args__ = (UniqueConstraint("scenario_id", "candidate_id", name="uq_scenario_candidate"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("poll_scenarios.id"), nullable=False)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    estimate_percent: Mapped[float] = mapped_column(Float, nullable=False)
    lower_bound_percent: Mapped[float | None] = mapped_column(Float)
    upper_bound_percent: Mapped[float | None] = mapped_column(Float)
    margin_of_error: Mapped[float | None] = mapped_column(Float)

    scenario: Mapped[PollScenario] = relationship(back_populates="results")
    candidate: Mapped[Candidate] = relationship(back_populates="results")


class Adjustment(Base, TimestampMixin):
    __tablename__ = "adjustments"

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("polls.id"), nullable=False)
    adjustment_type: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[dict[str, Any] | None]
    notes: Mapped[str | None] = mapped_column(Text)

    poll: Mapped[Poll] = relationship(back_populates="adjustments")


class ModelRun(Base, TimestampMixin):
    __tablename__ = "model_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_name: Mapped[str] = mapped_column(String(255), default="poll_bias", nullable=False)
    metrics: Mapped[dict[str, Any] | None]
    artifact_path: Mapped[str | None] = mapped_column(String(512))
    training_data_path: Mapped[str | None] = mapped_column(String(512))
    notes: Mapped[str | None] = mapped_column(Text)


class ForecastOrSmoothedEstimate(Base, TimestampMixin):
    __tablename__ = "forecasts_or_smoothed_estimates"

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("poll_scenarios.id"), nullable=False)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    estimate_date: Mapped[date] = mapped_column(Date, nullable=False)
    estimate_kind: Mapped[str] = mapped_column(String(100), nullable=False)
    estimate_percent: Mapped[float] = mapped_column(Float, nullable=False)
    uncertainty_low: Mapped[float | None] = mapped_column(Float)
    uncertainty_high: Mapped[float | None] = mapped_column(Float)
    metadata_json: Mapped[dict[str, Any] | None]

    scenario: Mapped[PollScenario] = relationship(back_populates="smoothed_estimates")
    candidate: Mapped[Candidate] = relationship(back_populates="smoothed_estimates")


class IngestionLog(Base, TimestampMixin):
    __tablename__ = "ingestion_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[dict[str, Any] | None]
    message: Mapped[str | None] = mapped_column(Text)
