"""Cron entrypoint: calls every scheduled job on each tick.

One service runs them all rather than one service per schedule, because each
endpoint is idempotent per period and decides whether it is due: the rollup
and purge run once a day, the digest only at Monday 08:00 Asia/Jerusalem. A
repeated tick is a no-op, so an hourly schedule is safe and DST-proof.

Set CRON_JOB to run a single job instead of all of them.

Usage: python scripts/run_crons.py
"""

import os
import sys
import urllib.error
import urllib.request

JOBS = ("metrics-rollup", "archive-purge", "weekly-digest")


def call(base: str, secret: str, job: str) -> bool:
    req = urllib.request.Request(
        f"{base}/api/cron/{job}",
        method="POST",
        headers={"Authorization": f"Bearer {secret}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as res:
            print(f"{job}: {res.status} {res.read().decode()[:400]}", flush=True)
        return True
    except urllib.error.HTTPError as e:
        print(f"{job}: FAILED {e.code} {e.read().decode()[:400]}", flush=True)
        return False


def main() -> None:
    base = os.environ.get("API_BASE_URL", "").rstrip("/")
    secret = os.environ.get("CRON_SECRET", "")
    if not base or not secret:
        sys.exit("API_BASE_URL and CRON_SECRET are required")

    only = os.environ.get("CRON_JOB", "").strip()
    jobs = (only,) if only else JOBS
    if only and only not in JOBS:
        sys.exit(f"CRON_JOB must be one of {list(JOBS)}, got {only!r}")

    # Run every job even if an earlier one fails, then fail the run if any did,
    # so a broken job is visible in Railway without silencing the others.
    failures = [job for job in jobs if not call(base, secret, job)]
    if failures:
        sys.exit(f"failed: {', '.join(failures)}")


if __name__ == "__main__":
    main()
