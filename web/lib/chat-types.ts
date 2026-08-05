export interface ConversationRow {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface Citation {
  index: number;
  title: string;
  source_type: "kb" | "board" | "department";
  source_id: string;
  href: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  created_at: string;
}
