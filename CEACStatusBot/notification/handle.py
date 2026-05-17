from abc import ABC, abstractmethod


class NotificationHandle(ABC):
    @abstractmethod
    def send(self, notification: dict) -> None:
        """Send a de-identified notification.

        notification keys (none contain PII):
            from_status:   str  -- previous CEAC status
            to_status:     str  -- new CEAC status
            visa_type:     str
            case_created:  str
            case_last_updated: str
            description:   str
            history:       list[dict] -- full transition timeline,
                              each {"from": str, "to": str, "at": str}
            timestamp:     str  -- ISO-8601 when this notification was generated
        """
