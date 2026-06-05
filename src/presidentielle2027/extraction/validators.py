from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

CollectionMethod = Literal["online", "phone", "mixed", "unknown"]
QuotaMethod = Literal["true", "false", "unknown"]
RoundName = Literal["first_round", "second_round"]


class NormalizedPollRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    poll_id: str
    source_url: HttpUrl | str
    source_name: str
    polling_company: str
    commissioner: str | None = None
    media_partner: str | None = None
    fieldwork_start_date: date | None = None
    fieldwork_end_date: date | None = None
    publication_date: date | None = None
    sample_size: int | None = None
    population: str | None = None
    collection_method: CollectionMethod = "unknown"
    quota_method: QuotaMethod = "unknown"
    round: RoundName
    scenario_name: str
    candidate_name: str
    candidate_party: str | None = None
    political_family: str | None = None
    estimate_percent: float
    lower_bound_percent: float | None = None
    upper_bound_percent: float | None = None
    margin_of_error: float | None = None
    undecided_percent: float | None = None
    abstention_estimate: float | None = None
    registered_voters_basis: bool | None = None
    raw_text_context: str | None = None
    extraction_confidence: float = Field(ge=0, le=1)
    created_at: datetime | None = None
    updated_at: datetime | None = None

