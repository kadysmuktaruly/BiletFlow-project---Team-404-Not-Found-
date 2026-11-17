"""Promotional campaigns and promo codes (SRS 4.14).

`router`: the organizer's campaign management, under their own event (404 otherwise).
`public_router`: what attendees use: preview a code, and resolve a Campaign QR link.
"""

import uuid

from fastapi import APIRouter, status

from app.deps import CurrentUser, OptionalUser, OwnedEvent, SessionDep
from app.errors import error_responses
from app.schemas.promo import (
    CampaignCreate,
    CampaignRead,
    CampaignResolution,
    CampaignUpdate,
    PromoQuote,
    PromoValidateRequest,
)
from app.services import promotions

router = APIRouter(
    prefix="/organizer/events/{event_id}/campaigns",
    tags=["campaigns"],
    responses=error_responses(401, 403, 404),
)
public_router = APIRouter(tags=["promotions"])


@router.get("", response_model=list[CampaignRead], summary="This event's campaigns, newest first")
async def list_campaigns(event: OwnedEvent, session: SessionDep) -> list[CampaignRead]:
    return await promotions.list_for_event(session, event)


@router.post(
    "",
    response_model=CampaignRead,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409, 422),
    summary="Create a campaign with its promo code and Campaign QR link",
    description=(
        "A percentage (1–100) or fixed-KZT discount, optional validity dates, an optional "
        "redemption limit and optional eligible ticket types (empty = all). Leave `code` "
        "empty to get a generated one. Codes are case-insensitive and unique across "
        "BiletFlow (`409 promo_code_taken`)."
    ),
)
async def create_campaign(
    data: CampaignCreate, event: OwnedEvent, user: CurrentUser, session: SessionDep
) -> CampaignRead:
    campaign = await promotions.create(session, event, user, data)
    return await promotions.to_read(session, campaign)


@router.get(
    "/{campaign_id}",
    response_model=CampaignRead,
    summary="One campaign with its sales report",
)
async def read_campaign(
    campaign_id: uuid.UUID, event: OwnedEvent, session: SessionDep
) -> CampaignRead:
    campaign = await promotions.get_for_event(session, event, campaign_id)
    return await promotions.to_read(session, campaign)


@router.patch(
    "/{campaign_id}",
    response_model=CampaignRead,
    responses=error_responses(409, 422),
    summary="Change a campaign's name, dates or redemption limit",
    description="The discount and eligible ticket types can't change after creation.",
)
async def update_campaign(
    campaign_id: uuid.UUID,
    data: CampaignUpdate,
    event: OwnedEvent,
    user: CurrentUser,
    session: SessionDep,
) -> CampaignRead:
    campaign = await promotions.get_for_event(session, event, campaign_id)
    campaign = await promotions.update_campaign(session, event, campaign, user, data)
    return await promotions.to_read(session, campaign)


@router.post(
    "/{campaign_id}/disable",
    response_model=CampaignRead,
    summary="Disable a campaign and its code",
    description="New checkouts get `promo_disabled`. Orders already placed keep their discount.",
)
async def disable_campaign(
    campaign_id: uuid.UUID, event: OwnedEvent, user: CurrentUser, session: SessionDep
) -> CampaignRead:
    campaign = await promotions.get_for_event(session, event, campaign_id)
    campaign = await promotions.disable(session, event, campaign, user)
    return await promotions.to_read(session, campaign)


@public_router.post(
    "/promo/validate",
    response_model=PromoQuote,
    responses=error_responses(404, 409, 422),
    summary="Preview what a promo code is worth for these tickets",
    description=(
        "No sign-in needed. Returns the discount and new total computed on the server, or "
        "an error whose `code` says why the code can't be used: `promo_not_found`, "
        "`promo_disabled`, `promo_not_started`, `promo_expired`, `promo_exhausted` or "
        "`promo_not_applicable`. Checkout recomputes everything; this is only a preview."
    ),
)
async def validate_promo(
    data: PromoValidateRequest, session: SessionDep, user: OptionalUser
) -> PromoQuote:
    return await promotions.quote(session, user, data)


@public_router.get(
    "/campaigns/resolve/{token}",
    response_model=CampaignResolution,
    responses=error_responses(404),
    summary="Resolve a Campaign QR link to its event and code",
    description=(
        "The `/c/{token}` page calls this. When the campaign can be used, `code` is set so "
        "the event page can apply it; otherwise `code` is null and `rejection` says why. "
        "The token carries no discount: everything is read from the campaign on the server."
    ),
)
async def resolve_campaign(
    token: str, session: SessionDep, user: OptionalUser
) -> CampaignResolution:
    return await promotions.resolve(session, token, user)
