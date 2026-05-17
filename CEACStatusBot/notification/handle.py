from abc import ABC, abstractmethod


class NotificationHandle(ABC):
    @abstractmethod
    def send(self, notification: dict) -> None:
        """Send a de-identified notification.

        notification keys (none contain PII):
            from_status:        str  -- previous CEAC status
            to_status:          str  -- new CEAC status
            is_status_change:   bool -- True if status changed; False if only
                                      case_last_updated changed
            visa_type:          str
            case_created:       str
            case_last_updated:  str  -- current last-updated date from CEAC
            description:        str  -- CEAC status description text
            history:            list[dict] -- full transition timeline
            timestamp:          str  -- ISO-8601
            previous_last_updated: str -- only present when is_status_change=False
        """
