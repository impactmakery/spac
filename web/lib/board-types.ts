export interface CategoryRef {
  id: string;
  name_he: string;
  name_en: string | null;
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
  author: AuthorRef;
  link_url: string | null;
  /** A shared prompt or agent brief, kept as copyable text. */
  prompt_text: string | null;
  filename: string | null;
  size_bytes: number | null;
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
}

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
export function categoryTint(categoryId: string): { bg: string; fg: string } {
  let hash = 0;
  for (const ch of categoryId) hash = (hash * 31 + ch.charCodeAt(0)) % 360;
  return {
    bg: `hsl(${hash} 70% 93%)`,
    fg: `hsl(${hash} 55% 30%)`,
  };
}
