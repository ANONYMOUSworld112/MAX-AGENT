"""Handler for get_time_date tool."""
from datetime import datetime, timezone
import time


def handle(params: dict) -> dict:
    del params
    now = datetime.now()
    return {
        "datetime": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day": now.strftime("%A"),
        "timezone": time.tzname[0],
    }
