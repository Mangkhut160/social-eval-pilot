from datetime import datetime

from src.core.time import utc_now


def test_utc_now_returns_naive_datetime() -> None:
    value = utc_now()

    assert isinstance(value, datetime)
    assert value.tzinfo is None
