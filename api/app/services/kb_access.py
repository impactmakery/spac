"""Who may see which knowledge base document, as one reusable WHERE clause.

This lives on its own because more than one place needs it and they must not
drift: the library listing, opening a single document, and the starter
questions offered in chat. The starter questions were built without it and
offered every user the titles of the four most recently uploaded documents on
the platform — including other municipalities' — which is how it was found.
"""

from sqlalchemy import ColumnElement, or_

from app.models import KbDocument, User


def readable_kb_documents(user: User) -> ColumnElement[bool]:
    """Documents this person may read.

    The shared library is readable by everyone; a municipality's library only
    by that municipality. A system admin reads everything.
    """
    if user.role == "system_admin":
        return KbDocument.id.is_not(None)
    return or_(
        KbDocument.scope == "global",
        KbDocument.municipality_id == user.municipality_id,
    )
