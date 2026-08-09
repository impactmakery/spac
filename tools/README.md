# tools

## The handover document

`build_handover_doc.py` generates *Tomorrow Agent Hub — Accounts, Access and Open
Items*: production accounts, what each role can reach, every screen and what it
does, file types, the AI models in use, and what is still outstanding.

The document is **generated, not hand-edited**. Editing the `.docx` directly
means the next build silently discards the change, so edit
`handover_sections.py` (the content) or `build_handover_doc.py` (the structure)
and rebuild.

```bash
python tools/build_handover_doc.py                       # to ~/Downloads
python tools/build_handover_doc.py --out ./handover.docx  # somewhere else
```

The document lists the demo logins so it is usable on its own, but this
repository is public and passwords do not belong in it. They are supplied at
build time and default to a placeholder:

```bash
DEMO_MUNI_ADMIN_PASSWORD=... DEMO_DEPT_USER_PASSWORD=... \
  python tools/build_handover_doc.py
```

Requires `python-docx`, which the API already depends on:

```bash
api/.venv/Scripts/python tools/build_handover_doc.py     # Windows
api/.venv/bin/python tools/build_handover_doc.py         # macOS / Linux
```
