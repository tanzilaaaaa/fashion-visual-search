"""The signed-in user's profile: info, interests, favorites, collections, history,
personal recommendations and account settings. Every route needs a session for an
existing account (even when AUTH_ENABLED=false there is no anonymous profile)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from fastapi.concurrency import run_in_threadpool

from ...container import Container
from ...core.security import COOKIE_NAME
from ...schemas.api import UserOut
from ...schemas.profile import (
    AccountDelete,
    CollectionDetail,
    CollectionIn,
    CollectionOut,
    CollectionsResponse,
    EmailChange,
    FavoriteIdsResponse,
    FavoriteItem,
    FavoritesResponse,
    ForYouResponse,
    ForYouSectionOut,
    HistoryEntry,
    HistoryResponse,
    InterestsIn,
    InterestsOut,
    PasswordChange,
    ProfileInfo,
    ProfileResponse,
    ProfileStats,
    ProfileUpdate,
)
from ...services.profile import (
    AVATAR_COLORS,
    STYLE_PRESETS,
    Collection,
    CollectionNameTaken,
    CollectionNotFound,
    Interests,
    LimitReached,
)
from ...services.recommendation import for_user
from ...services.users import EmailTaken, User, normalise_email, password_problem, valid_email
from .. import serializers
from ..deps import current_user, get_container, get_recommendation
from ..errors import APIError, bad_request, not_found, unauthorized
from ..limiter import limiter

router = APIRouter(prefix="/me", tags=["profile"])

ItemId = Path(..., pattern=r"^[A-Za-z0-9_-]{1,64}$")


def me(user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise unauthorized("Sign in to use your profile.")
    return user


def _item_exists(c: Container, item_id: str) -> None:
    if c.metadata is None or c.metadata.position_of(item_id) is None:
        raise not_found(f"No item with id '{item_id}'.")


def _summaries(c: Container, item_ids: list[str]):
    """Item cards for ids still in the catalogue (a rebuilt index may drop some)."""
    out = []
    for i in item_ids:
        pos = c.metadata.position_of(i) if c.metadata else None
        if pos is not None:
            out.append(serializers.summary(c.metadata.get(pos)))
    return out


def _collection_out(c: Container, col: Collection, detail: bool = False):
    items = _summaries(c, col.item_ids)
    base = dict(id=col.id, name=col.name, created_at=col.created_at, count=len(items), cover=items[:4])
    return CollectionDetail(**base, items=items) if detail else CollectionOut(**base)


def _clean_name(name: str) -> str:
    name = " ".join(name.split())
    if not name:
        raise bad_request("Please enter a name.", "invalid_name")
    return name


def _limit(exc: LimitReached) -> APIError:
    return APIError(400, "limit_reached", str(exc))


# ------------------------------------------------------------------- profile
@router.get("/profile", response_model=ProfileResponse, summary="Profile, interests and stats")
def get_profile(user: User = Depends(me), c: Container = Depends(get_container)):
    p = c.profiles.get_profile(user.id)
    return ProfileResponse(
        user=UserOut(id=user.id, name=user.name, email=user.email),
        profile=ProfileInfo(bio=p.bio, location=p.location, avatar_color=p.avatar_color),
        interests=InterestsOut(**p.interests.as_dict()),
        stats=ProfileStats(**c.profiles.stats(user.id)),
        member_since=user.created_at,
        avatar_colors=list(AVATAR_COLORS),
        style_presets=list(STYLE_PRESETS),
    )


@router.patch("/profile", response_model=ProfileResponse, summary="Update name, bio, location, avatar colour")
def update_profile(body: ProfileUpdate, user: User = Depends(me), c: Container = Depends(get_container)):
    if body.avatar_color is not None and body.avatar_color not in AVATAR_COLORS:
        raise bad_request(f"Avatar colour must be one of: {', '.join(AVATAR_COLORS)}.", "invalid_avatar_color")
    if body.name is not None:
        user = c.users.update_name(user.id, _clean_name(body.name)) or user
    c.profiles.update_profile(
        user.id,
        bio=body.bio.strip() if body.bio is not None else None,
        location=" ".join(body.location.split()) if body.location is not None else None,
        avatar_color=body.avatar_color,
    )
    return get_profile(user, c)


@router.put("/interests", response_model=InterestsOut, summary="Replace interests")
def set_interests(body: InterestsIn, user: User = Depends(me), c: Container = Depends(get_container)):
    if c.metadata is None:
        raise APIError(503, "not_ready", "The catalogue is still loading. Try again shortly.")
    for field, values in (("category", body.categories), ("colour", body.colours)):
        known = set(c.metadata.values(field).tolist())
        bad = [v for v in values if v not in known]
        if bad:
            raise bad_request(f"Unsupported {field}: {', '.join(bad)}.", "unsupported_filter")
    styles = []
    for s in body.styles:
        s = " ".join(s.lower().split())
        if not s or len(s) > 24:
            raise bad_request("Style tags must be 1–24 characters.", "invalid_style")
        if s not in styles:
            styles.append(s)
    interests = Interests(sorted(set(body.categories)), sorted(set(body.colours)), styles)
    return InterestsOut(**c.profiles.set_interests(user.id, interests).interests.as_dict())


# ----------------------------------------------------------------- favorites
@router.get("/favorites", response_model=FavoritesResponse, summary="Saved items, newest first")
def list_favorites(user: User = Depends(me), c: Container = Depends(get_container)):
    items = []
    for item_id, saved_at in c.profiles.favorites(user.id):
        pos = c.metadata.position_of(item_id) if c.metadata else None
        if pos is not None:
            items.append(FavoriteItem(**serializers.summary(c.metadata.get(pos)).model_dump(), saved_at=saved_at))
    return FavoritesResponse(total=len(items), items=items)


@router.get("/favorites/ids", response_model=FavoriteIdsResponse, summary="Saved item ids (for heart icons)")
def favorite_ids(user: User = Depends(me), c: Container = Depends(get_container)):
    return FavoriteIdsResponse(ids=c.profiles.favorite_ids(user.id))


@router.put("/favorites/{item_id}", response_model=FavoriteIdsResponse, summary="Save an item")
def add_favorite(item_id: str = ItemId, user: User = Depends(me), c: Container = Depends(get_container)):
    _item_exists(c, item_id)
    try:
        c.profiles.add_favorite(user.id, item_id)
    except LimitReached as exc:
        raise _limit(exc) from exc
    return FavoriteIdsResponse(ids=c.profiles.favorite_ids(user.id))


@router.delete("/favorites/{item_id}", response_model=FavoriteIdsResponse, summary="Unsave an item")
def remove_favorite(item_id: str = ItemId, user: User = Depends(me), c: Container = Depends(get_container)):
    c.profiles.remove_favorite(user.id, item_id)
    return FavoriteIdsResponse(ids=c.profiles.favorite_ids(user.id))


# --------------------------------------------------------------- collections
@router.get("/collections", response_model=CollectionsResponse, summary="Collections with covers")
def list_collections(user: User = Depends(me), c: Container = Depends(get_container)):
    return CollectionsResponse(collections=[_collection_out(c, col) for col in c.profiles.collections(user.id)])


@router.post("/collections", response_model=CollectionDetail, status_code=201, summary="Create a collection")
def create_collection(body: CollectionIn, user: User = Depends(me), c: Container = Depends(get_container)):
    try:
        col = c.profiles.create_collection(user.id, _clean_name(body.name))
    except CollectionNameTaken:
        raise APIError(409, "collection_exists", "You already have a collection with that name.") from None
    except LimitReached as exc:
        raise _limit(exc) from exc
    return _collection_out(c, col, detail=True)


def _col(fn, *args):
    try:
        return fn(*args)
    except CollectionNotFound:
        raise not_found("Collection not found.") from None
    except CollectionNameTaken:
        raise APIError(409, "collection_exists", "You already have a collection with that name.") from None
    except LimitReached as exc:
        raise _limit(exc) from exc


@router.get("/collections/{collection_id}", response_model=CollectionDetail, summary="One collection")
def get_collection(collection_id: int, user: User = Depends(me), c: Container = Depends(get_container)):
    return _collection_out(c, _col(c.profiles.collection, user.id, collection_id), detail=True)


@router.patch("/collections/{collection_id}", response_model=CollectionDetail, summary="Rename a collection")
def rename_collection(collection_id: int, body: CollectionIn, user: User = Depends(me),
                      c: Container = Depends(get_container)):
    col = _col(c.profiles.rename_collection, user.id, collection_id, _clean_name(body.name))
    return _collection_out(c, col, detail=True)


@router.delete("/collections/{collection_id}", status_code=204, summary="Delete a collection")
def delete_collection(collection_id: int, user: User = Depends(me), c: Container = Depends(get_container)):
    _col(c.profiles.delete_collection, user.id, collection_id)
    return Response(status_code=204)


@router.put("/collections/{collection_id}/items/{item_id}", response_model=CollectionDetail,
            summary="Add an item (also saves it)")
def add_to_collection(collection_id: int, item_id: str = ItemId, user: User = Depends(me),
                      c: Container = Depends(get_container)):
    _item_exists(c, item_id)
    return _collection_out(c, _col(c.profiles.add_to_collection, user.id, collection_id, item_id), detail=True)


@router.delete("/collections/{collection_id}/items/{item_id}", response_model=CollectionDetail,
               summary="Remove an item from a collection")
def remove_from_collection(collection_id: int, item_id: str = ItemId, user: User = Depends(me),
                           c: Container = Depends(get_container)):
    col = _col(c.profiles.remove_from_collection, user.id, collection_id, item_id)
    return _collection_out(c, col, detail=True)


# ------------------------------------------------------------------- history
@router.get("/history", response_model=HistoryResponse, summary="Recent text searches")
def get_history(user: User = Depends(me), c: Container = Depends(get_container)):
    return HistoryResponse(entries=[HistoryEntry(**e) for e in c.profiles.history(user.id)])


@router.delete("/history", status_code=204, summary="Clear search history")
def clear_history(user: User = Depends(me), c: Container = Depends(get_container)):
    c.profiles.delete_history(user.id)
    return Response(status_code=204)


@router.delete("/history/{entry_id}", status_code=204, summary="Remove one search")
def delete_history_entry(entry_id: int, user: User = Depends(me), c: Container = Depends(get_container)):
    c.profiles.delete_history(user.id, entry_id)
    return Response(status_code=204)


# ----------------------------------------------------------- recommendations
@router.get("/recommendations", response_model=ForYouResponse, summary="Personal picks from favorites + interests")
async def recommendations(
    top_k: int = Query(12, ge=1, le=48),
    user: User = Depends(me),
    c: Container = Depends(get_container),
):
    rec = get_recommendation(c)
    fav = c.profiles.favorite_ids(user.id)
    interests = c.profiles.get_profile(user.id).interests
    sections = await run_in_threadpool(
        for_user, rec, fav, interests.categories, interests.colours, interests.styles, top_k
    )
    return ForYouResponse(
        sections=[ForYouSectionOut(key=s.key, title=s.title, items=serializers.scored(s.items, rec.search.metadata))
                  for s in sections],
        has_favorites=bool(fav),
        has_interests=not interests.empty,
    )


# ------------------------------------------------------------------- account
def _require_password(c: Container, user: User, password: str) -> None:
    if not c.users.check_password(user.id, password):
        raise APIError(401, "invalid_credentials", "Your current password is incorrect.")


@router.patch("/account", response_model=UserOut, summary="Change email")
@limiter.limit("10/minute")
def change_email(request: Request, body: EmailChange, user: User = Depends(me), c: Container = Depends(get_container)):
    _require_password(c, user, body.current_password)
    email = normalise_email(body.email)
    if not valid_email(email):
        raise bad_request("Please enter a valid email address.", "invalid_email")
    try:
        updated = c.users.update_email(user.id, email)
    except EmailTaken:
        raise APIError(409, "email_taken", "An account with this email already exists.") from None
    return UserOut(id=updated.id, name=updated.name, email=updated.email)


@router.post("/password", status_code=204, summary="Change password")
@limiter.limit("10/minute")
def change_password(request: Request, body: PasswordChange, user: User = Depends(me),
                    c: Container = Depends(get_container)):
    _require_password(c, user, body.current_password)
    if problem := password_problem(body.new_password):
        raise bad_request(problem, "weak_password")
    c.users.set_password(user.id, body.new_password)
    return Response(status_code=204)


@router.delete("/account", status_code=204, summary="Delete the account and all its data")
@limiter.limit("10/minute")
def delete_account(request: Request, body: AccountDelete, user: User = Depends(me),
                   c: Container = Depends(get_container)):
    _require_password(c, user, body.password)
    c.users.delete(user.id)
    response = Response(status_code=204)
    response.set_cookie(COOKIE_NAME, "", max_age=0, httponly=True, secure=c.settings.cookie_secure,
                        samesite="lax", path="/")
    return response
