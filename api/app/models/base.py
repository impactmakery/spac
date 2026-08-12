import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

EMBEDDING_DIM = 1536

ROLES = ("system_admin", "municipality_admin", "department_user")
LANGUAGES = ("he", "en")


class Municipality(Base):
    __tablename__ = "municipalities"
    __table_args__ = (CheckConstraint("status IN ('active','inactive')", name="ck_muni_status"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    departments: Mapped[list["Department"]] = relationship(back_populates="municipality")


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (
        CheckConstraint("status IN ('active','archived')", name="ck_dept_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    municipality_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("municipalities.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    archive_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    municipality: Mapped[Municipality] = relationship(back_populates="departments")
    users: Mapped[list["User"]] = relationship(
        secondary="user_departments", back_populates="departments"
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('system_admin','municipality_admin','department_user')",
            name="ck_users_role",
        ),
        CheckConstraint("language IN ('he','en')", name="ck_users_language"),
        CheckConstraint("status IN ('invited','active','inactive')", name="ck_users_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    municipality_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("municipalities.id"))
    language: Mapped[str] = mapped_column(Text, nullable=False, server_default="he")
    digest_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="invited")
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    municipality: Mapped[Municipality | None] = relationship()
    departments: Mapped[list[Department]] = relationship(
        secondary="user_departments", back_populates="users"
    )


class UserDepartment(Base):
    __tablename__ = "user_departments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True
    )


class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint(
            "role IN ('system_admin','municipality_admin','department_user')",
            name="ck_invitations_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    municipality_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("municipalities.id"))
    department_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Category(Base):
    """Global board categories, named bilingually. Removal only via merge-into."""

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name_he: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # Optional: the users are Hebrew-speaking, and the English name exists for
    # the people running the platform. Postgres allows many NULLs under a unique
    # constraint, so leaving it blank never collides.
    name_en: Mapped[str | None] = mapped_column(Text, unique=True)
    # A palette key such as "rose" or "teal", not a hex value. The interface
    # owns what each key looks like, so contrast stays controlled and the whole
    # palette can be restyled without touching stored data. Unset falls back to
    # a colour derived from the id, which is what every existing category has.
    color: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class KbDocument(Base):
    """A knowledge base document. Replace keeps the id so citations stay valid.

    Scope mirrors the boards: 'global' is the shared library every municipality
    reads, 'municipality' is one municipality's own library. The column is
    explicit rather than derived from municipality_id, which has always been set
    to the uploader's municipality even for shared documents — deriving would
    silently reclassify what is already there.
    """

    __tablename__ = "kb_documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','indexed','not_indexable')",
            name="ck_kb_documents_status",
        ),
        CheckConstraint(
            "scope IN ('global','municipality')", name="ck_kb_documents_scope"
        ),
        CheckConstraint(
            "scope != 'municipality' OR municipality_id IS NOT NULL",
            name="ck_kb_documents_muni_scope",
        ),
        # Declared here as well as in its migration, or autogenerate proposes
        # dropping an index it cannot see on the model.
        Index("ix_kb_documents_scope_municipality", "scope", "municipality_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    uploader_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    municipality_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("municipalities.id"))
    scope: Mapped[str] = mapped_column(Text, nullable=False, server_default="global")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Chunk(Base):
    """Embedded passage. The permission filter runs on these columns inside SQL."""

    __tablename__ = "chunks"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('kb','board','department','comment')",
            name="ck_chunks_source_type",
        ),
        CheckConstraint(
            "visibility IN ('global','municipality','department')",
            name="ck_chunks_visibility",
        ),
        Index("ix_chunks_source", "source_type", "source_id"),
        Index(
            "ix_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_search", "search", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    municipality_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("municipalities.id", ondelete="CASCADE")
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE")
    )
    visibility: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    # Lexical half of hybrid retrieval. 'english' rather than 'simple': it stems
    # English ("operates" matches "operate") and drops English stopwords, so an
    # OR query cannot match a document merely on "the". Postgres has no Hebrew
    # stemmer, so Hebrew tokens pass through unchanged either way.
    search: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', content)", persisted=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IngestionJob(Base):
    """Postgres-backed job queue, consumed with FOR UPDATE SKIP LOCKED."""

    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','done','failed')", name="ck_ingestion_status"
        ),
        Index("ix_ingestion_jobs_claim", "status", "run_after"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class BoardItem(Base):
    """Board post: global board or one municipality's board. File XOR link.

    `kind` is what sort of thing the post is, which is separate from what it
    carries: an event can still have a file attached, an announcement can still
    have a link. 'post' is what every existing row is and what the form still
    produces by default.
    """

    __tablename__ = "board_items"
    __table_args__ = (
        CheckConstraint("scope IN ('global','municipality')", name="ck_board_items_scope"),
        CheckConstraint(
            "kind IN ('post','announcement','event','question')",
            name="ck_board_items_kind",
        ),
        # An event without a date could not be listed among what is coming up,
        # which is the only reason to mark one.
        CheckConstraint(
            "kind != 'event' OR event_at IS NOT NULL", name="ck_board_items_event_at"
        ),
        # Only a question can have an answer accepted.
        CheckConstraint(
            "accepted_comment_id IS NULL OR kind = 'question'",
            name="ck_board_items_accepted_question",
        ),
        CheckConstraint(
            "scope != 'municipality' OR municipality_id IS NOT NULL",
            name="ck_board_items_muni_scope",
        ),
        CheckConstraint(
            "indexing_status IN ('none','pending','processing','indexed','not_indexable')",
            name="ck_board_items_indexing",
        ),
        Index("ix_board_items_scope", "scope", "municipality_id", "created_at"),
        # "what is coming up" is a scan of one kind ordered by date
        Index("ix_board_items_event", "kind", "event_at"),
        Index("ix_board_items_search", "search", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="post")
    # When and where an event happens. Time is optional — plenty of things are
    # announced as a day before an hour is settled.
    event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    event_has_time: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    event_location: Mapped[str | None] = mapped_column(Text)
    # The reply the asker marked as the one that answered it. Set null rather
    # than cascading when that comment goes: the question stays, unanswered.
    accepted_comment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("board_comments.id", ondelete="SET NULL")
    )
    municipality_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("municipalities.id", ondelete="CASCADE")
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    link_url: Mapped[str | None] = mapped_column(Text)
    # A shareable prompt or agent brief: the instructions themselves, kept as
    # text so colleagues can copy them and so the assistant can find them.
    prompt_text: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    content_type: Mapped[str | None] = mapped_column(Text)
    indexing_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="none")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    search: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', coalesce(title,'') || ' ' || "
            "coalesce(description,'') || ' ' || coalesce(prompt_text,''))",
            persisted=True,
        ),
        nullable=True,
    )


class BoardComment(Base):
    __tablename__ = "board_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("board_items.id", ondelete="CASCADE"), nullable=False
    )
    # Replies are one level deep: a reply to a reply attaches to the same
    # parent. Deeper threads are hard to read on a phone and, in a workplace
    # discussion, rarely say anything a flat reply could not.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("board_comments.id", ondelete="CASCADE")
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BoardLike(Base):
    __tablename__ = "board_likes"

    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("board_items.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BoardCommentReaction(Base):
    """One emoji from one person on one comment.

    The primary key is the triple, so a person may react in several ways to the
    same comment but cannot double-count any one of them — the toggle is then
    just an insert or a delete, with no read-modify-write to race on.

    The emoji is validated against a fixed set in the router rather than stored
    freely: it is rendered directly, and a free-text column would invite both
    junk and abuse.
    """

    __tablename__ = "board_comment_reactions"

    comment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("board_comments.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    emoji: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DepartmentFile(Base):
    __tablename__ = "department_files"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','indexed','not_indexable')",
            name="ck_department_files_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), nullable=False
    )
    uploader_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DepartmentPost(Base):
    __tablename__ = "department_posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DepartmentPostComment(Base):
    __tablename__ = "department_post_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("department_posts.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Conversation(Base):
    """Private per-user chat thread. No admin surface may expose these."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="ck_messages_role"),
        Index("ix_messages_conversation", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MessageDebug(Base):
    """Retrieval audit trail per answer. Purged after 90 days by the nightly cron."""

    __tablename__ = "message_debug"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    retrieval_sql: Mapped[str | None] = mapped_column(Text)
    chunk_ids: Mapped[list | None] = mapped_column(JSONB)
    scores: Mapped[list | None] = mapped_column(JSONB)
    prompt: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UnansweredQuestion(Base):
    """Questions the available material did not cover — feeds KB curation."""

    __tablename__ = "unanswered_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    municipality_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("municipalities.id", ondelete="CASCADE")
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UserLogin(Base):
    """One row per successful login — the source for daily active users."""

    __tablename__ = "user_logins"
    __table_args__ = (Index("ix_user_logins_day", "created_at", "municipality_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    municipality_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("municipalities.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DailyMetric(Base):
    """Nightly rollup. Dashboards read only from here — never live heavy queries.

    municipality_id NULL = platform total; department_id NULL = municipality total.
    """

    __tablename__ = "daily_metrics"
    __table_args__ = (
        Index(
            "uq_daily_metrics_scope",
            "day",
            "municipality_id",
            "department_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    municipality_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("municipalities.id", ondelete="CASCADE")
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE")
    )
    active_users: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    chat_sessions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    chat_messages: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    unanswered: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    board_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    comments: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    likes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    files_uploaded: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CronRun(Base):
    """Idempotency ledger + audit for scheduled jobs."""

    __tablename__ = "cron_runs"
    __table_args__ = (
        Index("uq_cron_runs_period", "job", "period_key", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job: Mapped[str] = mapped_column(Text, nullable=False)
    period_key: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    counts: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    """Append-only. No code path may UPDATE or DELETE rows in this table."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str | None] = mapped_column(Text)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# --- knowledge graph ---------------------------------------------------------
# Entities and relationships extracted from chunks, for traversal that answers
# "who is connected to what" rather than "which passage looks similar".
#
# The permission columns live on the MENTION and the RELATION, never on the
# entity. An entity is just a name — "Department of Welfare" may be mentioned in
# a global circular and in a confidential department file, and those two facts
# carry different visibility. Putting the scope on the entity would collapse them
# and let a traversal surface a relationship the user cannot see.


class GraphEntity(Base):
    """A canonical thing: a person, a body, a place, a regulation."""

    __tablename__ = "graph_entities"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('person','organization','location','regulation','date','other')",
            name="ck_graph_entities_kind",
        ),
        Index("ix_graph_entities_normalized", "normalized"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # lowercased, whitespace-collapsed: the key two spellings collide on
    normalized: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="other")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class GraphMention(Base):
    """An entity occurring in one chunk. Carries that chunk's visibility."""

    __tablename__ = "graph_mentions"
    __table_args__ = (
        CheckConstraint(
            "visibility IN ('global','municipality','department')",
            name="ck_graph_mentions_visibility",
        ),
        Index("ix_graph_mentions_entity", "entity_id"),
        Index("ix_graph_mentions_chunk", "chunk_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("graph_entities.id", ondelete="CASCADE"), nullable=False
    )
    # Deleting a document deletes its chunks, which must delete their graph rows
    # in the same transaction — otherwise a deleted file stays traversable.
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )
    municipality_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("municipalities.id", ondelete="CASCADE")
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE")
    )
    visibility: Mapped[str] = mapped_column(Text, nullable=False)


class GraphRelation(Base):
    """subject --predicate--> object, evidenced by one chunk whose scope it takes."""

    __tablename__ = "graph_relations"
    __table_args__ = (
        CheckConstraint(
            "visibility IN ('global','municipality','department')",
            name="ck_graph_relations_visibility",
        ),
        Index("ix_graph_relations_subject", "subject_id"),
        Index("ix_graph_relations_object", "object_id"),
        Index("ix_graph_relations_chunk", "chunk_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("graph_entities.id", ondelete="CASCADE"), nullable=False
    )
    object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("graph_entities.id", ondelete="CASCADE"), nullable=False
    )
    predicate: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )
    municipality_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("municipalities.id", ondelete="CASCADE")
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE")
    )
    visibility: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="1.0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
