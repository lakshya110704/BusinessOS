"""Pydantic models for Meta WhatsApp Cloud API inbound webhook payloads.

Meta nests messages deeply: entry[].changes[].value.messages[]. These models
parse that shape and expose `WebhookPayload.iter_messages()` to walk every
inbound message regardless of how Meta batched them.

Models are permissive (`extra="allow"`) because Meta adds fields over time and
we don't want a new field to 500 the webhook.
"""
from __future__ import annotations

from typing import Iterator, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TextBody(BaseModel):
    body: str


class MediaObject(BaseModel):
    # Covers audio / image / document / video — Meta sends a media id we later fetch.
    model_config = ConfigDict(extra="allow")
    id: str
    mime_type: Optional[str] = None
    filename: Optional[str] = None  # documents only
    sha256: Optional[str] = None


class ButtonReply(BaseModel):
    id: str
    title: Optional[str] = None


class ListReply(BaseModel):
    id: str
    title: Optional[str] = None


class Interactive(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str
    button_reply: Optional[ButtonReply] = None
    list_reply: Optional[ListReply] = None


class ButtonObject(BaseModel):
    payload: Optional[str] = None
    text: Optional[str] = None


class InboundMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    from_: str = Field(alias="from")
    id: str
    timestamp: Optional[str] = None
    type: str

    # Only the sub-object matching `type` is populated.
    text: Optional[TextBody] = None
    audio: Optional[MediaObject] = None
    image: Optional[MediaObject] = None
    document: Optional[MediaObject] = None
    interactive: Optional[Interactive] = None
    button: Optional[ButtonObject] = None


class Metadata(BaseModel):
    model_config = ConfigDict(extra="allow")
    display_phone_number: Optional[str] = None
    phone_number_id: Optional[str] = None


class ChangeValue(BaseModel):
    model_config = ConfigDict(extra="allow")
    messaging_product: Optional[str] = None
    metadata: Optional[Metadata] = None
    messages: Optional[List[InboundMessage]] = None


class Change(BaseModel):
    model_config = ConfigDict(extra="allow")
    value: ChangeValue
    field: Optional[str] = None


class Entry(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: Optional[str] = None
    changes: List[Change] = Field(default_factory=list)


class WebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    object: Optional[str] = None
    entry: List[Entry] = Field(default_factory=list)

    def iter_messages(self) -> Iterator[InboundMessage]:
        for entry in self.entry:
            for change in entry.changes:
                for message in (change.value.messages or []):
                    yield message
