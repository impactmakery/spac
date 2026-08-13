"""Recompute the daily usage rows for a window of past days.

The dashboard reads stored rollups, not live counts, so changing what a metric
means only affects days rolled up afterwards — leaving a chart whose definition
changes partway along the line. Rebuilding the window makes the whole series
mean one thing.

rollup_day deletes and rebuilds the day it is given, so running this twice is
the same as running it once.

Usage:
    python scripts/rebuild_rollups.py            # the last 90 days
    python scripts/rebuild_rollups.py 30         # the last 30 days
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import get_db  # noqa: E402
from app.services.metrics import TZ, rollup_day  # noqa: E402

DEFAULT_DAYS = 90


def main() -> None:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DAYS
    if days < 1:
        sys.exit("days must be at least 1")

    today = datetime.now(TZ).date()
    db = next(get_db())
    # Oldest first, so an interrupted run leaves the recent days — the ones
    # anybody is looking at — still holding their old numbers rather than none.
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        counts = rollup_day(db, day)
        print(f"{day}: {counts['rows']} rows", flush=True)


if __name__ == "__main__":
    main()
