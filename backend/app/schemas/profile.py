"""Request/response contracts for the signed-in user's profile (`/me/*`)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .api import ItemSummary, ScoredItem, UserOut


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InterestsIn(Strict):
    categories: list[str] = Field(default_factory=list, max_length=13)
    colours: list[str] = Field(default_factory=list, max_length=13)
    styles: list[str] = Field(default_factory=list, max_length=12)


class InterestsOut(BaseModel):
    categories: list[str]
    colours: list[str]
    styles: list[str]


class ProfileInfo(BaseModel):
    bio: str
    location: str
    avatar_color: str


class ProfileStats(BaseModel):
    favorites: int
    collections: int
    searches: int


class ProfileResponse(BaseModel):
    user: UserOut
    profile: ProfileInfo
    interests: InterestsOut
    stats: ProfileStats
    member_since: float
    avatar_colors: list[str]
    style_presets: list[str]


class ProfileUpdate(Strict):
    name: str | None = Field(None, max_length=60)
    bio: str | None = Field(None, max_length=280)
    location: str | None = Field(None, max_length=60)
    avatar_color: str | None = Field(None, max_length=20)


class FavoriteItem(ItemSummary):
    saved_at: float


class FavoritesResponse(BaseModel):
    total: int
    items: list[FavoriteItem]


class FavoriteIdsResponse(BaseModel):
    ids: list[str]


class CollectionIn(Strict):
    name: str = Field(..., min_length=1, max_length=40)


class CollectionOut(BaseModel):
    id: int
    name: str
    created_at: float
    count: int
    cover: list[ItemSummary]


class CollectionDetail(CollectionOut):
    items: list[ItemSummary]


class CollectionsResponse(BaseModel):
    collections: list[CollectionOut]


class HistoryEntry(BaseModel):
    id: int
    query: str
    created_at: float


class HistoryResponse(BaseModel):
    entries: list[HistoryEntry]


class ForYouSectionOut(BaseModel):
    key: str
    title: str
    items: list[ScoredItem]


class ForYouResponse(BaseModel):
    sections: list[ForYouSectionOut]
    has_favorites: bool
    has_interests: bool


class EmailChange(Strict):
    email: str = Field(..., min_length=3, max_length=254)
    current_password: str = Field(..., min_length=1, max_length=128)


class PasswordChange(Strict):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=1, max_length=128)


class AccountDelete(Strict):
    password: str = Field(..., min_length=1, max_length=128)
