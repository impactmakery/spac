"""Cron entrypoint for the Railway cron service.

Railway triggers a service on a schedule; this decides which job to run from
CRON_JOB and calls the endpoint on the API. The endpoints are idempotent per
period, so a duplicate trigger is a no-op.

Usage: CRON_JOB=metrics-rollup python scripts/run_crons.py
"""

import os
import sys
import urllib.error
import urllib.request

JOBS = {"metrics-rollup", "weekly-digest", "archive-purge"}


def main() -> None:
    job = os.environ.get("CRON_JOB", "").strip()
    if job not in JOBS:
        sys.exit(f"CRON_JOB must be one of {sorted(JOBS)}, got {job!r}")

    base = os.environ.get("API_BASE_URL", "").rstrip("/")
    secret = os.environ.get("CRON_SECRET", "")
    if not base or not secret:
        sys.exit("API_BASE_URL and CRON_SECRET are required")

    req = urllib.request.Request(
        f"{base}/api/cron/{job}",
        method="POST",
        headers={"Authorization": f"Bearer {secret}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as res:
            print(f"{job}: {res.status} {res.read().decode()[:500]}")
    except urllib.error.HTTPError as e:
        sys.exit(f"{job} failed: {e.code} {e.read().decode()[:500]}")


if __name__ == "__main__":
    main()
