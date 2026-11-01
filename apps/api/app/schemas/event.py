"""Events as organizers create and edit them (SRS 4.2)."""

import uuid
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    computed_field,
    model_validator,
)

from app.enums import EventStatus, EventVisibility, SeatingMode


def _valid_timezone(name: str) -> str:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Use an IANA time zone name such as Asia/Almaty.") from exc
    return name


TimeZoneName = Annotated[str, Field(max_length=64), AfterValidator(_valid_timezone)]


class VenueInput(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    address_line1: str = Field(min_length=1, max_length=300)
    address_line2: str | None = Field(default=None, max_length=300)
    city: str = Field(min_length=1, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=20)


class VenueRead(VenueInput):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_code: str


class _EventFields(BaseModel):
    """Times may be sent with a UTC offset, or without one. A time without an offset is read
    as local time in the event's `timezone`, which is what an organizer types into a form."""

    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=20000)
    category: str | None = Field(default=None, max_length=100)
    cover_image_url: HttpUrl | None = None
    venue: VenueInput
    starts_at: datetime
    ends_at: datetime
    timezone: TimeZoneName = "Asia/Almaty"


class EventCreate(_EventFields):
    @model_validator(mode="after")
    def _ends_after_start(self) -> "EventCreate":
        tz = ZoneInfo(self.timezone)
        self.starts_at = localize(self.starts_at, tz)
        self.ends_at = localize(self.ends_at, tz)
        if self.ends_at < self.starts_at:
            raise ValueError("The event must end after it starts.")
        return self


class EventUpdate(BaseModel):
    """Every field optional. Times without an offset use the event's (possibly new) zone;
    the service resolves them, because the current zone lives in the database."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=20000)
    category: str | None = Field(default=None, max_length=100)
    cover_image_url: HttpUrl | None = None
    venue: VenueInput | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    timezone: TimeZoneName | None = None


def localize(value: datetime, tz: ZoneInfo) -> datetime:
    return value.replace(tzinfo=tz) if value.tzinfo is None else value


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    description: str | None
    category: str | None
    cover_image_url: str | None
    status: EventStatus
    visibility: EventVisibility
    seating_mode: SeatingMode
    venue: VenueRead | None
    starts_at: datetime
    ends_at: datetime
    timezone: str
    registration_opens_at: datetime | None
    registration_closes_at: datetime | None
    capacity: int | None
    published_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def starts_at_local(self) -> str:
        """Start in the event's own time zone, without an offset, e.g. for form inputs."""
        return self.starts_at.astimezone(ZoneInfo(self.timezone)).strftime("%Y-%m-%dT%H:%M")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ends_at_local(self) -> str:
        return self.ends_at.astimezone(ZoneInfo(self.timezone)).strftime("%Y-%m-%dT%H:%M")
