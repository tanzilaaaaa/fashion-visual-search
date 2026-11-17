"""Request/response contracts between the React frontend and the API (PRD §8)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Filters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: list[str] = Field(default_factory=list)
    colour: list[str] = Field(default_factory=list)
    source: list[str] = Field(default_factory=list)
    viewpoint: list[str] = Field(default_factory=list)

    def as_dict(self) -> dict[str, list[str]]:
        return {k: v for k, v in self.model_dump().items() if v}


class TextSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., description="Natural-language description, e.g. 'black oversized hoodie'")
    top_k: int | None = Field(None, ge=1, le=100)
    filters: Filters = Field(default_factory=Filters)
    alpha: float | None = Field(None, ge=0, le=1, description="Weight of embedding similarity")
    beta: float | None = Field(None, ge=0, le=1, description="Weight of attribute match")


class ItemSummary(BaseModel):
    item_id: str
    image_url: str
    category: str
    category_key: str
    colour: str
    source: str
    viewpoint: str


class ScoredItem(ItemSummary):
    score: float = Field(..., description="Final ranking score (higher is better)")
    similarity: float = Field(..., description="Cosine similarity from FAISS")
    attribute_match: float = 0.0
    reason: str | None = None


class ItemDetail(ItemSummary):
    occlusion: str
    scale: str
    zoom_in: str
    colour_confidence: float
    pair_id: int
    style: int
    worn_with: list[str]


class Ranking(BaseModel):
    alpha: float
    beta: float
    attribute_signal_used: bool


class SearchResponse(BaseModel):
    mode: str
    query: str | None = None
    total: int
    results: list[ScoredItem]
    applied_filters: dict[str, list[str]]
    detected: dict
    inferred: dict | None = None
    ranking: Ranking
    candidates_considered: int
    latency_ms: float


class SimilarResponse(BaseModel):
    source: ItemSummary
    total: int
    results: list[ScoredItem]


class LookGroupOut(BaseModel):
    group: str
    label: str
    items: list[ScoredItem]


class RecommendationsResponse(BaseModel):
    source: ItemSummary
    groups: list[LookGroupOut]


class FilterOption(BaseModel):
    value: str
    label: str
    count: int


class FilterField(BaseModel):
    label: str
    options: list[FilterOption]


class FiltersResponse(BaseModel):
    fields: dict[str, FilterField]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    index_loaded: bool
    item_count: int
    model: str | None = None
    startup_error: str | None = None
    stats: dict


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class SessionResponse(BaseModel):
    authenticated: bool
    username: str | None = None
    auth_enabled: bool


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
