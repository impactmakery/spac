"""Load a directory of per-municipality folders into the platform.

Each subdirectory of --root is one municipality. The folders are named
"<municipality> - <contact person>", e.g. "שלומי - אליהו", so the municipality
is the part before the dash and the rest is whoever owns the material. Files
inside — at any depth — go into that municipality's own knowledge base, where
only that municipality can read them and the assistant only cites them when
answering their staff.

Runs against the HTTP API rather than the database on purpose: the files are on
this machine and the platform is not, and going through the API means the
upload obeys the same size limit, type list, and permission checks as a person
clicking Upload. Nothing here can create access the product would not.

Usage:
    python scripts/import_folders.py --root "C:/.../קבצים אישיים-רשותיים" \\
        --api https://api.example.com --email admin@example.com --password ...

    # see exactly what would happen, touching nothing:
    python scripts/import_folders.py --root ... --dry-run

Skips and why is printed at the end, and written to --manifest as CSV, because
"369 files, 12 skipped" is only useful if you can see which 12.
"""

import argparse
import csv
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.uploads import CONTENT_TYPES, MAX_UPLOAD_BYTES  # noqa: E402

# Windows and Office leave these behind; they are not documents.
JUNK_NAMES = {"thumbs.db", ".ds_store", "desktop.ini"}
JUNK_PREFIXES = ("~$", "._")


@dataclass
class Skip:
    municipality: str
    path: str
    reason: str
    detail: str


@dataclass
class Plan:
    municipality: str
    contact: str
    folder: Path
    files: list[Path] = field(default_factory=list)
    skips: list[Skip] = field(default_factory=list)


def split_folder_name(name: str) -> tuple[str, str]:
    """"שלומי - אליהו" -> ("שלומי", "אליהו").

    Only the first dash splits: a municipality with a dash in its own name
    (Hebrew uses one in compound place names) keeps it if there is no contact
    suffix, and a contact with a dash keeps theirs.
    """
    for sep in (" - ", " – ", " — "):
        if sep in name:
            head, _, tail = name.partition(sep)
            return head.strip(), tail.strip()
    return name.strip(), ""


def classify(path: Path, municipality: str) -> Skip | None:
    """Why this file cannot go into a knowledge base, or None if it can."""
    lower = path.name.lower()
    if lower in JUNK_NAMES or lower.startswith(JUNK_PREFIXES):
        return Skip(municipality, str(path), "junk", path.name)
    ext = path.suffix.lstrip(".").lower()
    if ext not in CONTENT_TYPES:
        return Skip(municipality, str(path), "unsupported_type", f".{ext or 'none'}")
    size = path.stat().st_size
    if size > MAX_UPLOAD_BYTES:
        return Skip(municipality, str(path), "too_large", f"{size / 1_048_576:.1f} MB")
    if size == 0:
        return Skip(municipality, str(path), "empty", "0 bytes")
    return None


def build_plan(root: Path) -> list[Plan]:
    plans = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        name, contact = split_folder_name(folder.name)
        plan = Plan(municipality=name, contact=contact, folder=folder)
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            skip = classify(path, name)
            (plan.skips.append(skip) if skip else plan.files.append(path))
        plans.append(plan)
    return plans


def title_for(path: Path, folder: Path) -> str:
    """Filename, prefixed by any subfolder it sits in.

    A citation reading "תקציב 2026 — מצגות" tells you where the passage came
    from; one reading "מצגת 3" does not.
    """
    rel = path.relative_to(folder)
    parents = [p for p in rel.parent.parts if p not in (".", "")]
    return f"{rel.stem} — {' / '.join(parents)}" if parents else rel.stem


def titles_for(paths: list[Path], folder: Path) -> dict[Path, str]:
    """Titles for a whole folder at once, with collisions made distinct.

    Dropping the extension means a report saved as both .docx and .pdf lands on
    one title twice, and the library shows what looks like a duplicate of
    something that is not one — two different files, both real, indistinguishable
    in a list and in a citation. Where that happens the format is named; where it
    does not, the title stays clean.
    """
    titles: dict[Path, str] = {p: title_for(p, folder) for p in paths}
    counts = Counter(titles.values())
    return {
        path: (
            f"{title} ({path.suffix.lstrip('.').upper()})"
            if counts[title] > 1 and path.suffix
            else title
        )
        for path, title in titles.items()
    }


class Api:
    def __init__(self, base: str, email: str, password: str) -> None:
        self.base = base.rstrip("/")
        # Big presentations over a slow link need far longer than the default.
        self.client = httpx.Client(timeout=300.0)
        r = self.client.post(
            f"{self.base}/api/auth/login", json={"email": email, "password": password}
        )
        r.raise_for_status()
        self.token = r.json()["access_token"]
        if r.json()["user"]["role"] != "system_admin":
            raise SystemExit("that account is not a system admin")

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def municipality_id(self, name: str) -> str:
        r = self.client.get(f"{self.base}/api/municipalities", headers=self.headers)
        r.raise_for_status()
        for m in r.json():
            if m["name"] == name:
                return m["id"]
        r = self.client.post(
            f"{self.base}/api/municipalities", json={"name": name}, headers=self.headers
        )
        r.raise_for_status()
        print(f"  created municipality {name}")
        return r.json()["id"]

    def existing_titles(self, municipality_id: str) -> set[str]:
        """So a re-run after a failure does not duplicate what already landed."""
        r = self.client.get(
            f"{self.base}/api/kb-documents",
            params={"scope": "municipality", "municipality_id": municipality_id},
            headers=self.headers,
        )
        r.raise_for_status()
        return {d["title"] for d in r.json()}

    def upload(self, path: Path, title: str, municipality_id: str) -> None:
        ext = path.suffix.lstrip(".").lower()
        with path.open("rb") as fh:
            r = self.client.post(
                f"{self.base}/api/kb-documents",
                files={"file": (path.name, fh, CONTENT_TYPES[ext])},
                data={
                    "title": title,
                    "scope": "municipality",
                    "municipality_id": municipality_id,
                },
                headers=self.headers,
            )
        if r.status_code != 201:
            raise RuntimeError(f"{r.status_code} {r.text[:200]}")


def main() -> None:
    # Every municipality name here is Hebrew, and the Windows console defaults
    # to a codepage that cannot encode it.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--email")
    ap.add_argument("--password")
    ap.add_argument("--only", action="append", default=[],
                    help="import only these municipalities (repeatable)")
    ap.add_argument("--manifest", type=Path, default=Path("import-manifest.csv"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.root.is_dir():
        raise SystemExit(f"no such directory: {args.root}")

    plans = build_plan(args.root)
    if args.only:
        plans = [p for p in plans if p.municipality in args.only]

    total_files = sum(len(p.files) for p in plans)
    total_bytes = sum(f.stat().st_size for p in plans for f in p.files)
    print(f"{len(plans)} municipalities, {total_files} files, "
          f"{total_bytes / 1_048_576:.0f} MB to upload")
    for plan in plans:
        line = f"  {plan.municipality:20} {len(plan.files):4} files"
        if plan.contact:
            line += f"   contact: {plan.contact}"
        if plan.skips:
            line += f"   ({len(plan.skips)} skipped)"
        print(line)

    all_skips = [s for p in plans for s in p.skips]
    if all_skips:
        args.manifest.write_text(
            _manifest_csv(all_skips), encoding="utf-8-sig"  # BOM so Excel reads Hebrew
        )
        print(f"\n{len(all_skips)} files skipped — see {args.manifest}")
        for reason in sorted({s.reason for s in all_skips}):
            n = sum(1 for s in all_skips if s.reason == reason)
            print(f"  {reason:18} {n}")

    if args.dry_run:
        print("\ndry run — nothing was uploaded")
        return
    if not (args.email and args.password):
        raise SystemExit("--email and --password are required unless --dry-run")

    api = Api(args.api, args.email, args.password)
    failures: list[tuple[Path, str]] = []
    uploaded = 0
    skipped_existing = 0
    started = time.monotonic()
    for plan in plans:
        if not plan.files:
            print(f"\n{plan.municipality}: no files")
            continue
        print(f"\n{plan.municipality}: {len(plan.files)} files")
        muni_id = api.municipality_id(plan.municipality)
        already = api.existing_titles(muni_id)
        titles = titles_for(plan.files, plan.folder)
        for path in plan.files:
            title = titles[path]
            if title in already:
                skipped_existing += 1
                continue
            try:
                api.upload(path, title, muni_id)
            except Exception as exc:  # noqa: BLE001 — one bad file must not stop 368
                failures.append((path, str(exc)))
                print(f"  FAILED {path.name}: {exc}", flush=True)
                continue
            uploaded += 1
            if uploaded % 25 == 0:
                rate = uploaded / max(time.monotonic() - started, 1)
                done = uploaded + skipped_existing
                print(f"  {done}/{total_files} ({rate:.1f}/s uploading)", flush=True)

    print(f"\nuploaded {uploaded} of {total_files}")
    if skipped_existing:
        print(f"{skipped_existing} were already there and were left alone")
    if failures:
        print(f"{len(failures)} failed:")
        for path, err in failures[:20]:
            print(f"  {path.name}: {err}")
    print("Indexing runs in the ingestion worker; the library shows each "
          "document's status as it finishes.")


def _manifest_csv(skips: list[Skip]) -> str:
    import io

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["municipality", "file", "reason", "detail"])
    for s in skips:
        w.writerow([s.municipality, s.path, s.reason, s.detail])
    return buf.getvalue()


if __name__ == "__main__":
    main()
