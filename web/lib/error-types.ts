export interface ServerError {
  id: number;
  occurred_at: string;
  method: string;
  path: string;
  error_type: string;
  message: string;
  traceback: string | null;
  user_email: string | null;
}

export interface FailedDocument {
  id: string;
  title: string;
  filename: string;
  /** Empty for the shared library and for department files. */
  library: string;
  error: string | null;
  attempts: number;
  updated_at: string;
}

export interface FailedJob {
  job: string;
  period_key: string;
  started_at: string;
  error: string | null;
}

export interface SystemErrors {
  server_errors: ServerError[];
  failed_documents: FailedDocument[];
  failed_jobs: FailedJob[];
}
