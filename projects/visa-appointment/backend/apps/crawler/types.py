"""Value objects shared by HTTP adapters and booking orchestration."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Slot:
    slot_id: str
    starts_at: datetime


@dataclass(frozen=True)
class ObservationResult:
    status: str
    slots: tuple[Slot, ...] = ()
    detail: str = ""
    retry_after: int | None = None


@dataclass(frozen=True)
class BookingRequest:
    operation_id: str
    case_reference: str
    slot_id: str


@dataclass(frozen=True)
class SubmissionResult:
    status: str
    confirmation_reference: str = ""
    detail: str = ""
