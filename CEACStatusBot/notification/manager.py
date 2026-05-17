import json
import os
import datetime

import pytz

from CEACStatusBot.captcha import CaptchaHandle, OnnxCaptchaHandle
from CEACStatusBot.request import query_status

from .handle import NotificationHandle

DEFAULT_ACTIVE_HOURS = "00:00-23:59"

_AP_KEYWORDS = [
    "administrative processing",
    "undergoing such processing",
    "will remain refused while undergoing",
]


def _classify_refused(description: str) -> str:
    lower = description.lower()
    for kw in _AP_KEYWORDS:
        if kw in lower:
            return "Refused (AP)"
    return "Refused (Final)"


def _is_refused(status: str) -> bool:
    return status in ("Refused (AP)", "Refused (Final)")


class NotificationManager:
    def __init__(
        self,
        location: str,
        number: str,
        passport_number: str,
        surname: str,
        captchaHandle: CaptchaHandle = OnnxCaptchaHandle("captcha.onnx"),
    ) -> None:
        self.__handleList: list[NotificationHandle] = []
        self.__location = location
        self.__number = number
        self.__captchaHandle = captchaHandle
        self.__passport_number = passport_number
        self.__surname = surname
        self.__status_file = "status_record.json"

    def _get_hour_range(self):
        active_hours = os.getenv("ACTIVE_HOURS") or DEFAULT_ACTIVE_HOURS
        start_str, end_str = active_hours.split("-")
        start = datetime.datetime.strptime(start_str, "%H:%M").time()
        end = datetime.datetime.strptime(end_str, "%H:%M").time()
        if start > end:
            raise ValueError(f"Start time must be before end time, got start: {start}, end: {end}")
        return start, end

    def addHandle(self, notificationHandle: NotificationHandle) -> None:
        self.__handleList.append(notificationHandle)

    def hasHandles(self) -> bool:
        return len(self.__handleList) > 0

    def send(self) -> None:
        res = query_status(
            self.__location,
            self.__number,
            self.__passport_number,
            self.__surname,
            self.__captchaHandle,
        )
        if not res["success"]:
            raise RuntimeError("Query status failed, no notification sent.")

        raw_status = res["status"]
        description = res.get("description", "")
        current_last_updated = res["case_last_updated"]

        if raw_status == "Refused":
            current_status = _classify_refused(description)
        else:
            current_status = raw_status

        print(f"Current status: {current_status} - Last updated: {current_last_updated}")

        record = self.__load_record()
        previous_status = record.get("current", "UNKNOWN")
        previous_last_updated = record.get("last_updated", "")

        # Status changed → always notify
        if current_status != previous_status:
            self.__record_transition(previous_status, current_status, current_last_updated)
            self.__send_notifications(
                res, previous_status, current_status, record.get("history", []),
                is_status_change=True,
            )
            return

        # Status unchanged, but last_updated changed → notify with different message
        if current_last_updated and current_last_updated != previous_last_updated:
            print(f"Status unchanged ({current_status}) but last_updated changed: "
                  f"{previous_last_updated} -> {current_last_updated}")
            self.__record_case_update(current_status, previous_last_updated, current_last_updated)
            self.__send_notifications(
                res, previous_status, current_status, record.get("history", []),
                is_status_change=False, previous_last_updated=previous_last_updated,
            )
            return

        print(f"Status unchanged ({current_status}). No notification sent.")

    def __load_record(self) -> dict:
        if not os.path.exists(self.__status_file):
            return {"current": "UNKNOWN", "last_updated": "", "history": []}
        try:
            with open(self.__status_file) as file:
                data = json.load(file)
        except (json.JSONDecodeError, IOError):
            print("Warning: status_record.json is corrupted, starting fresh.")
            return {"current": "UNKNOWN", "last_updated": "", "history": []}

        if "current" not in data:
            return {"current": "UNKNOWN", "last_updated": "", "history": []}
        return data

    def __record_transition(self, from_status: str, to_status: str, last_updated: str) -> None:
        record = self.__load_record()
        timestamp = datetime.datetime.now().isoformat()
        record["current"] = to_status
        record["last_updated"] = last_updated
        record["history"].append({
            "type": "status",
            "from": from_status,
            "to": to_status,
            "at": timestamp,
        })
        with open(self.__status_file, "w") as file:
            json.dump(record, file, indent=2)

    def __record_case_update(self, current_status: str, previous_last_updated: str, new_last_updated: str) -> None:
        record = self.__load_record()
        timestamp = datetime.datetime.now().isoformat()
        record["last_updated"] = new_last_updated
        record["history"].append({
            "type": "case_updated",
            "status": current_status,
            "previous_last_updated": previous_last_updated,
            "new_last_updated": new_last_updated,
            "at": timestamp,
        })
        with open(self.__status_file, "w") as file:
            json.dump(record, file, indent=2)

    def __send_notifications(
        self, res: dict, from_status: str, to_status: str, history: list,
        is_status_change: bool, previous_last_updated: str = "",
    ) -> None:
        # Active-hours gating for Refused variants
        if _is_refused(to_status) and not self.__is_within_active_hours():
            print(
                f"Outside active hours {os.getenv('ACTIVE_HOURS') or DEFAULT_ACTIVE_HOURS}. "
                "No notification sent."
            )
            return

        notification = {
            "from_status": from_status,
            "to_status": to_status,
            "is_status_change": is_status_change,
            "visa_type": res.get("visa_type", ""),
            "case_created": res.get("case_created", ""),
            "case_last_updated": res.get("case_last_updated", ""),
            "description": res.get("description", ""),
            "history": history,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        if not is_status_change:
            notification["previous_last_updated"] = previous_last_updated

        for handle in self.__handleList:
            handle.send(notification)

    def __is_within_active_hours(self) -> bool:
        try:
            TIMEZONE = os.environ["TIMEZONE"]
            local_tz = pytz.timezone(TIMEZONE)
            local_time = datetime.datetime.now(local_tz)
        except (pytz.exceptions.UnknownTimeZoneError, KeyError):
            print("TIMEZONE not set or unknown, using system local time.")
            local_time = datetime.datetime.now()

        active_hour_start, active_hour_end = self._get_hour_range()
        start_dt = datetime.datetime.combine(local_time.date(), active_hour_start, tzinfo=local_time.tzinfo)
        end_dt = datetime.datetime.combine(local_time.date(), active_hour_end, tzinfo=local_time.tzinfo)
        return start_dt <= local_time <= end_dt
