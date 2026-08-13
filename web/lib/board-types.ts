export type BoardKind = "post" | "announcement" | "event" | "question";

export interface CategoryRef {
  id: string;
  name_he: string;
  name_en: string | null;
  color: string | null;
}

export interface AuthorRef {
  id: string | null;
  name: string | null;
  municipality_name: string | null;
  inactive: boolean;
}

export interface BoardItemRow {
  id: string;
  title: string;
  description: string | null;
  category: CategoryRef;
  scope: "global" | "municipality";
  /** What sort of thing this is, separate from what it carries. */
  kind: BoardKind;
  event_at: string | null;
  /** False when only a day was given, so no invented hour is shown. */
  event_has_time: boolean;
  event_location: string | null;
  /** On a question: the reply its author marked as the answer. */
  accepted_comment_id: string | null;
  /** Decided by the server, not inferred here: only the asker may mark it. */
  can_accept_answer: boolean;
  author: AuthorRef;
  link_url: string | null;
  /** A shared prompt or agent brief, kept as copyable text. */
  prompt_text: string | null;
  filename: string | null;
  size_bytes: number | null;
  /** Set only when the attachment is an image, so it can be shown rather than
   *  offered for download. Signed and short-lived. */
  image_url: string | null;
  like_count: number;
  comment_count: number;
  liked_by_me: boolean;
  can_edit: boolean;
  can_delete: boolean;
  created_at: string;
}

export interface BoardComment {
  id: string;
  author: AuthorRef;
  body: string;
  can_delete: boolean;
  created_at: string;
  /** Replies are one level deep; a top-level comment has null here. */
  parent_id: string | null;
  reactions: CommentReaction[];
}

export interface CommentReaction {
  emoji: string;
  count: number;
  /** Whether the signed-in person is one of the reactors. */
  mine: boolean;
}

/** Mirrors REACTIONS in the API; the server rejects anything else. */
export const REACTIONS = ["👍", "❤️", "😄", "🎉", "🙏", "👀"] as const;

export interface BoardItemDetail extends BoardItemRow {
  download_url: string | null;
  comments: BoardComment[];
}

export interface BoardPage {
  items: BoardItemRow[];
  has_more: boolean;
}

export interface DeptFile {
  id: string;
  filename: string;
  size_bytes: number;
  status: "pending" | "processing" | "indexed" | "not_indexable";
  uploader: { id: string | null; name: string | null; inactive: boolean };
  download_url: string;
  can_delete: boolean;
  created_at: string;
}

export interface DeptPostComment {
  id: string;
  author: { id: string | null; name: string | null; inactive: boolean };
  body: string;
  can_delete: boolean;
  created_at: string;
}

export interface DeptPost {
  id: string;
  author: { id: string | null; name: string | null; inactive: boolean };
  body: string;
  can_delete: boolean;
  comments: DeptPostComment[];
  created_at: string;
}

/** Deterministic pastel tint per category, like the prototype's category chips. */
