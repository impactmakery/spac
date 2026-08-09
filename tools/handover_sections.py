"""Extra sections for the handover document: stack, uploads, page-by-page."""

STACK = [
    ["Frontend", "Next.js 16 (App Router) + TypeScript", "Renders every screen. Pages fetch on the server, so the browser never holds an API token."],
    ["Styling", "Tailwind CSS 4", "Right-to-left layout comes from logical properties, so Hebrew and English share one stylesheet."],
    ["Language", "next-intl", "Hebrew and English, Hebrew default. Every string lives in a translation file."],
    ["Sign-in", "NextAuth (Auth.js) v5", "Session cookie in the browser; credentials are checked by the API, never by the frontend."],
    ["Backend", "Python 3.12 + FastAPI", "All permission checks live here. The frontend is never the enforcement point."],
    ["Database", "PostgreSQL 16 + pgvector", "One database for application data and document embeddings, so a permission filter and a similarity search are the same query."],
    ["Migrations", "Alembic", "Every schema change is a migration, applied automatically on deploy."],
    ["File storage", "Cloudflare R2", "Uploads go through the server; downloads use short-lived signed links."],
    ["Text extraction", "pypdf, python-docx, python-pptx, openpyxl", "One library per format, no heavyweight document toolkit."],
    ["Scanned documents", "Tesseract OCR (Hebrew + English) with PDFium", "Reads PDFs that are images rather than text."],
    ["AI models", "Any OpenAI-compatible provider (OpenAI, OpenRouter…)", "Chat and embeddings configured separately, each with its own key, and a fallback chain when a model is rate-limited."],
    ["Email", "Resend", "Invitations, password resets and the weekly digest. Live, sending from updates.impactmakery.com."],
    ["Hosting", "Vercel (frontend), Railway (API, worker, cron), Amsterdam region", "Region chosen for latency to Israel."],
]

UPLOADS_TYPES = [
    ["PDF", ".pdf", "Reports, circulars, signed letters, scanned paper"],
    ["Word", ".docx", "Procedures, guidelines, meeting notes"],
    ["PowerPoint", ".pptx", "Presentations, training decks"],
    ["Excel", ".xlsx", "Budgets, tables, lists"],
    ["Images", ".png .jpg .webp .gif", "Screenshots, photographed notices — text inside them is read"],
    ["Plain text", ".txt .csv .md", "Notes, exports, lists"],
]

UPLOAD_RULES = [
    ("Maximum size", "25 MB per file, everywhere."),
    ("The shared board accepts any file type at all",
     "images, video, archives, anything a colleague needs to pass on. The four "
     "formats above are simply the ones whose text can be read for search."),
    ("The knowledge base and department areas are stricter",
     "they hold the material the assistant reads, so they accept documents, "
     "images and plain text only. The check is not based on the file name: the "
     "server inspects the actual contents, so renaming a .zip to .pdf still fails."),
    ("Files that are not documents still download safely",
     "only documents and images are displayed inside the page. Everything else "
     "downloads instead — a file that could run code in the browser is never "
     "rendered, which stops one person's upload affecting another person's session."),
    ("Uploads are not scanned for viruses",
     "the board will pass an executable or an archive from one municipality to "
     "another unexamined. This is a known gap, not an oversight; virus scanning "
     "can be added without narrowing what people may share."),
    ("Where you can upload",
     "the knowledge base (shared with every municipality), a board post as an "
     "attachment, or a department area (visible to that department only)."),
    ("What happens next",
     "the file is stored, its text is extracted, split into passages and indexed so "
     "the assistant can quote it. Status moves from Pending to Indexed, usually in "
     "seconds. A large scanned file takes longer because every page is read visually."),
    ("Scanned documents",
     "a PDF that contains only images is read with optical character recognition in "
     "Hebrew and English, up to the first 40 pages. Before this existed such files "
     "were marked 'not indexable' and the assistant could not use them at all."),
    ("When indexing fails",
     "the file is marked 'not indexable' with the reason shown to whoever uploaded it, "
     "and can be retried after replacing it. The usual cause is a corrupt file."),
    ("Deleting",
     "removing a file also removes everything the assistant learned from it, in the "
     "same operation. It cannot be quoted afterwards."),
]

# (page, route, who, what it can do, APIs it calls)
PAGES = [
    ["Sign in", "/login", "Everyone",
     "Email and password, in Hebrew or English. Wrong details give the same message whether or not the account exists. Ten failed attempts in fifteen minutes are blocked. Link to password reset. On success each role lands on its own home screen.",
     "POST /api/auth/login"],
    ["Forgot password", "/forgot-password", "Everyone",
     "Requests a reset link by email. The reply is identical whether or not the address is registered, so the page cannot be used to discover who has an account.",
     "POST /api/auth/forgot"],
    ["Reset password", "/reset-password", "Everyone with a link",
     "Sets a new password. The link expires and works only once.",
     "POST /api/auth/reset"],
    ["Accept invitation", "/accept-invite", "Invited users",
     "Shows who invited you, the municipality and departments you are joining. Sets your name, password and interface language, then signs you in.",
     "GET /api/auth/invite-info · POST /api/auth/accept-invite"],
    ["Assistant", "/chat", "Everyone",
     "Ask questions in Hebrew or English and get an answer built only from documents you are allowed to see, with numbered links to the sources. The answer streams word by word. Conversations are private to you, are titled automatically, and can be renamed or deleted. Sample questions are offered when a conversation is empty. Sixty messages per hour per person.",
     "GET /api/conversations · POST /api/conversations · PATCH & DELETE /api/conversations/{id} · POST /api/chat/{id}/messages · GET /api/chat/sample-questions"],
    ["Knowledge base", "/knowledge", "Everyone",
     "Browse and search documents shared across all municipalities. Shows title, uploader, date and indexing status. Municipality admins can upload here; they may edit or delete only their own uploads.",
     "GET /api/kb-documents · POST /api/kb-documents"],
    ["Document page", "/knowledge/[id]", "Everyone",
     "Preview the document in the page, download it through a short-lived signed link, and see its indexing status. The uploader and system admin can replace the file, retry a failed indexing, or delete it.",
     "GET /api/kb-documents/{id} · POST /api/kb-documents/{id}/replace · POST /api/kb-documents/{id}/retry · DELETE /api/kb-documents/{id} · GET /api/files/{key}"],
    ["Shared board", "/board", "Everyone",
     "Posts shared by every municipality. Filter by category, sort by newest or most liked, search in Hebrew and English. A post can carry a link, a file of any type, or Text — a prompt for an AI assistant, an agent's instructions, or anything else worth passing on — and Text may travel with a link alongside it. Text is searchable both on the board and by the assistant, so a colleague can be pointed at a prompt someone else wrote. Authors edit and delete their own posts; municipality admins can remove any post from their own municipality.",
     "GET /api/board-items · POST /api/board-items · GET /api/categories"],
    ["Board post", "/board/[id]", "Everyone",
     "Full post with its attachment, link or Text, plus comments, replies and emoji reactions. Text is shown in full with a copy button. Leaving to an external link shows a warning first. Comment authors and admins can delete comments.",
     "GET /api/board-items/{id} · PATCH & DELETE /api/board-items/{id} · POST /api/board-items/{id}/like · POST & DELETE /api/board-items/{id}/comments"],
    ["My municipality", "/municipality", "Members of a municipality",
     "The same board, restricted to your own municipality. Nothing published here reaches another municipality, in the interface or through the assistant.",
     "GET /api/board-items · GET /api/municipalities · GET /api/categories"],
    ["Department area", "/departments/[id]", "Department members, their municipality admin, system admin",
     "Two tabs. Files: upload, list with uploader, date and indexing status, delete. Posts: short text posts with comments. Everything here is visible only to the department — and the assistant will quote it only for department members, even though an admin can read it here.",
     "GET /api/departments/{id}/info · GET & POST & DELETE /api/departments/{id}/files · GET & POST & DELETE /api/departments/{id}/posts"],
    ["My profile", "/profile", "Everyone",
     "Change your display name, interface language and weekly digest preference, and change your password. Shows which departments you belong to.",
     "GET /api/users/me/departments · PATCH /api/users/me · POST /api/auth/change-password"],
    ["Users", "/admin/users", "Municipality admin",
     "Everyone in your municipality. Invite by email as a municipality admin or department user, assign one or more departments, deactivate or reactivate, promote or demote. Deactivating signs the person out everywhere immediately. Users left with no department are flagged for reassignment.",
     "GET /api/admin/users · POST /api/invitations · POST /api/invitations/{id}/resend · PUT /api/admin/users/{id}/departments · POST /api/admin/users/{id}/deactivate|reactivate|promote|demote"],
    ["Departments", "/admin/departments", "Municipality admin",
     "Create and rename departments. Archiving hides a department and its content immediately, including from the assistant; it can be restored for 90 days, after which it is deleted permanently. Deleting requires typing the department name.",
     "GET & POST /api/departments · PATCH /api/departments/{id} · POST /api/departments/{id}/archive · POST /api/departments/{id}/restore"],
    ["Usage", "/admin/stats", "Municipality admin",
     "Your municipality only: active users, assistant conversations and messages, board posts, and how many questions went unanswered. Broken down per department, with a date range picker and CSV export. Figures come from a nightly roll-up, so today is not yet included.",
     "GET /api/stats/municipality"],
    ["Municipalities", "/system/municipalities", "System admin",
     "Every municipality with user and department counts. Add one, rename it, invite its first administrator, or deactivate it — which blocks its users from signing in and hides its content from the assistant, reversibly.",
     "GET & POST /api/municipalities · PATCH /api/municipalities/{id} · POST /api/municipalities/{id}/deactivate|reactivate"],
    ["Knowledge base admin", "/system/knowledge-base", "System admin",
     "Manage every document in the shared knowledge base regardless of who uploaded it, including replacing, retrying and deleting.",
     "GET & POST /api/kb-documents · POST /api/kb-documents/{id}/replace|retry · DELETE /api/kb-documents/{id}"],
    ["Categories", "/system/categories", "System admin",
     "The category list used when publishing to a board. Add, rename, and merge one category into another so existing posts are moved rather than orphaned.",
     "GET & POST /api/categories · PATCH /api/categories/{id} · POST /api/categories/{id}/merge-into/{target}"],
    ["All users", "/system/users", "System admin",
     "Every user across every municipality, with the same actions as the municipality view but unrestricted in scope.",
     "GET /api/admin/users · GET /api/municipalities"],
    ["Platform usage", "/system/stats", "System admin",
     "All municipalities side by side, with drill-down into any one of them, and the panel showing the actual wording of questions the assistant could not answer — the clearest signal of what content is missing.",
     "GET /api/stats/platform"],
]

AI_MODELS = [
    ["Answering questions", "OpenRouter", "google/gemma-4-26b-a4b-it (free tier)", "None"],
    ["   ↳ if rate-limited", "OpenRouter", "nvidia/nemotron-3-super-120b-a12b (free tier)", "None"],
    ["   ↳ then", "OpenRouter", "nvidia/nemotron-3-ultra-550b-a55b (free tier)", "None"],
    ["Understanding documents for search", "OpenAI", "text-embedding-3-large", "Paid, per document"],
    ["Building the knowledge graph", "OpenRouter", "same chain as answering", "None"],
]

AI_NOTES = [
    ("The only recurring AI cost today is the document understanding step",
     "and it is charged when a document is uploaded, not when someone asks a "
     "question. Asking questions currently costs nothing, because the answering "
     "models are on a free tier."),
    ("Free models are rate-limited, which is why there are three",
     "when the first model refuses, the request falls through to the second and "
     "then the third. A user sees a slightly slower answer rather than an error."),
    ("Answer quality is currently capped by the free models",
     "finding the right passages is one job and writing the answer is another. The "
     "search side has been tested thoroughly; the writing side runs on a free model. "
     "Moving to a paid model — the original plan named GPT-4.1 — is a configuration "
     "change of one line and would noticeably improve Hebrew answers. The free "
     "models can stay as the fallback."),
    ("Switching providers is configuration, not development",
     "each key travels with its own address, so chat and document understanding can "
     "sit with different providers, and moving everything to OpenAI needs no code "
     "change."),
    ("One setting must never be changed casually",
     "the document-understanding model. Documents indexed with one model cannot be "
     "compared against another, so changing it silently degrades search rather than "
     "failing visibly. If it ever changes, every document must be re-indexed."),
]

BACKGROUND = [
    ("Indexing worker",
     "runs continuously, picking up uploaded files and preparing them for the "
     "assistant. Retries three times before marking a file as not indexable."),
    ("Nightly usage roll-up, 02:00",
     "calculates the figures behind both dashboards."),
    ("Nightly archive purge, 03:00",
     "permanently deletes departments archived more than 90 days ago."),
    ("Weekly digest, Monday 08:00 Israel time",
     "emails each user a summary, if they have not opted out. Needs Resend."),
]


# What the assistant is and is not given, as a table plus the exclusions.
ASSISTANT_SOURCES = [
    ["Knowledge base", "The full text of every document, including scanned pages read by OCR", "Everyone"],
    ["Shared board", "Post title, description, Text, and the contents of any attached file", "Everyone"],
    ["Municipality board", "Post title, description, Text, and the contents of any attached file", "That municipality only"],
    ["Board comments and replies", "The text of the comment, with its post's title for context", "Whoever can see the post"],
    ["Department files", "The full text of every file", "That department's members only"],
    ["Department posts", "The text of the post", "That department's members only"],
]

ASSISTANT_EXCLUSIONS = [
    ("Comments on department posts are not searched",
     "board comments are, but the equivalent discussion inside a department "
     "area is not yet. The same work would cover it."),
    ("A file attached to a board post is read in full",
     "the same way a knowledge-base document is: its text is extracted, scanned "
     "pages included, so the assistant can quote what is inside the file rather "
     "than only the post's description."),
    ("Links on board posts are not followed",
     "a post's link is stored and clickable, but the page behind it is not read. "
     "Fetching a web address supplied by a user is a security decision in its "
     "own right and was deliberately left out."),
    ("Nothing else is visible to it",
     "no user or municipality records, no chat history, no usage figures, no "
     "category names. The assistant knows only the sources above."),
    ("New material is searchable within seconds",
     "uploads and posts are indexed by a background worker rather than "
     "instantly, so there is a short delay before the assistant can quote "
     "something just added."),
]
