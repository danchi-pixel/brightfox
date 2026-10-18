"""Moje napake: spaced review of the tasks that needed help.

A task that wasn't right first time (or needed the solution) goes into box 1, due the next day. Right first
time moves it up a box (due after 1, 3, 7, 14 days); after the last box it is "popravljeno" for good. A
wrong answer sends it back to box 1. Before a test (3 days or less) every item of the test's topics is due.
At most 10 a day.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

INTERVALS = {1: 1, 2: 3, 3: 7, 4: 14}  # days until the next look, by box
LAST_BOX = 4
PER_DAY = 10


def after_answer(box: int, good: bool, today: date) -> tuple[int, date, bool]:
    """(new box, next due date, cleared) after answering a review item."""
    if not good:
        return 1, today + timedelta(days=INTERVALS[1]), False
    if box >= LAST_BOX:
        return box, today, True
    nb = box + 1
    return nb, today + timedelta(days=INTERVALS[nb]), False


def now() -> datetime:
    return datetime.now(timezone.utc)
