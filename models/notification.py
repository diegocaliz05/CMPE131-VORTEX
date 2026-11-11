from dataclasses import dataclass
from typing import Optional


@dataclass
class Notification:
    user_id: int
    message: str
    event_id: Optional[int] = None
    read_status: bool = False
    notification_id: Optional[int] = None

    @classmethod
    def from_row(cls, row):
        return cls(notification_id=row["notification_id"], user_id=row["user_id"],
                   event_id=row["event_id"], message=row["message"],
                   read_status=bool(row["read_status"]))
