export interface KbDocRow {
  id: string;
  title: string;
  filename: string;
  size_bytes: number;
  content_type: string;
  status: "pending" | "processing" | "indexed" | "not_indexable";
  /** "global" is the shared library; "municipality" is one municipality's own. */
  scope: "global" | "municipality";
  uploader_name: string | null;
  municipality_name: string | null;
  municipality_id: string | null;
  uploader_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface KbDocDetail extends KbDocRow {
  download_url: string;
  error: string | null;
}

/** The document's text, for formats a browser cannot render in a frame. */
export interface TextPreview {
  text: string;
  truncated: boolean;
  available: boolean;
}
