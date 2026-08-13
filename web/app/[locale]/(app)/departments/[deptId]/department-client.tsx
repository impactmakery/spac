"use client";

import { FileText, FolderKanban, MessageSquare, Trash2, Upload } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useRef, useState } from "react";
import {
  addPostComment,
  createDepartmentPost,
  deleteDepartmentFile,
  deleteDepartmentPost,
  deletePostComment,
  uploadDepartmentFile,
} from "@/app/[locale]/(app)/board-actions";
import { StatusChip } from "@/components/kb-doc-row";
import { PageHeader } from "@/components/page-header";
import { Bidi, Button, Card, FieldError, Input, cn } from "@/components/ui";
import { Linkify } from "@/components/linkify";
import { useRouter } from "@/i18n/navigation";
import type { DeptFile, DeptPost } from "@/lib/board-types";
import { formatBytes } from "@/lib/format";
import { useConfirm } from "@/components/confirm";
import { useToast } from "@/components/toast";

export function DepartmentClient({
  deptId,
  deptName,
  files,
  posts,
  apiBase,
}: {
  deptId: string;
  deptName: string;
  files: DeptFile[];
  posts: DeptPost[];
  apiBase: string;
}) {
  const t = useTranslations("departmentArea");
  const confirm = useConfirm();
  const toast = useToast();
  const tc = useTranslations("common");
  const tk = useTranslations("knowledge");
  const format = useFormatter();
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<"files" | "posts">("files");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [postBody, setPostBody] = useState("");
  const [commentDrafts, setCommentDrafts] = useState<Record<string, string>>({});

  async function onUpload(list: FileList | null) {
    if (!list?.length) return;
    const file = list[0];
    setError(null);
    if (file.size > 25 * 1024 * 1024) return setError(tk("fileTooLarge"));
    setBusy(true);
    const fd = new FormData();
    fd.append("file", file);
    const res = await uploadDepartmentFile(deptId, fd);
    setBusy(false);
    if ("error" in res) {
      setError(res.status === 415 ? tk("badType") : res.error);
      return;
    }
    router.refresh();
  }

  async function onDeleteFile(fileId: string) {
    if (!(await confirm({ title: tc("deleteTitle"), body: t("deleteConfirm") }))) return;
    const res = await deleteDepartmentFile(deptId, fileId);
    if ("error" in res) return toast(tc("error"));
    toast(tc("deleted"), "success");
    router.refresh();
  }

  async function onPost(e: React.FormEvent) {
    e.preventDefault();
    const body = postBody.trim();
    if (!body) return;
    if (body.length > 2000) return setError(t("postTooLong"));
    setBusy(true);
    await createDepartmentPost(deptId, body);
    setPostBody("");
    setBusy(false);
    router.refresh();
  }

  async function onDeletePost(postId: string) {
    if (!(await confirm({ title: tc("deleteTitle"), body: t("deleteConfirm") }))) return;
    const res = await deleteDepartmentPost(deptId, postId);
    if ("error" in res) return toast(tc("error"));
    toast(tc("deleted"), "success");
    router.refresh();
  }

  async function onComment(postId: string) {
    const body = (commentDrafts[postId] ?? "").trim();
    if (!body) return;
    await addPostComment(deptId, postId, body.slice(0, 1000));
    setCommentDrafts((prev) => ({ ...prev, [postId]: "" }));
    router.refresh();
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <PageHeader
        title={deptName}
        subtitle={t("membersOnly")}
        action={
          tab === "files" ? (
            <>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.docx,.pptx,.xlsx"
                className="hidden"
                onChange={(e) => onUpload(e.target.files)}
              />
              <Button disabled={busy} onClick={() => fileRef.current?.click()}>
                <Upload className="size-4" />
                {t("upload")}
              </Button>
            </>
          ) : undefined
        }
      />

      <div className="mb-6 flex gap-2 border-b border-border">
        {(["files", "posts"] as const).map((k) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={cn(
              "border-b-2 px-4 py-2 text-sm font-medium",
              tab === k
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {k === "files" ? t("filesTab") : t("postsTab")}
          </button>
        ))}
      </div>
      <FieldError>{error}</FieldError>

      {tab === "files" ? (
        files.length === 0 ? (
          <EmptyState
            icon={<FolderKanban className="size-7" />}
            title={t("noFiles")}
            body={t("noFilesBody")}
          />
        ) : (
          <div className="space-y-3">
            {files.map((f) => (
              <Card key={f.id} className="flex items-center gap-4 p-4">
                <span className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                  <FileText className="size-5" />
                </span>
                <a
                  href={`${apiBase}${f.download_url}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="min-w-0 flex-1"
                >
                  <p className="truncate font-medium text-foreground hover:underline">
                    {f.filename}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {formatBytes(f.size_bytes)} ·{" "}
                    {t("uploadedBy", { name: f.uploader.name ?? "—" })} ·{" "}
                    <Bidi>{format.dateTime(new Date(f.created_at), { dateStyle: "medium" })}</Bidi>
                  </p>
                </a>
                <StatusChip status={f.status} />
                {f.can_delete && (
                  <button
                    onClick={() => onDeleteFile(f.id)}
                    aria-label={t("deleteFile")}
                    className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-destructive"
                  >
                    <Trash2 className="size-4" />
                  </button>
                )}
              </Card>
            ))}
          </div>
        )
      ) : (
        <div>
          <form onSubmit={onPost} className="mb-6">
            <textarea
              rows={3}
              maxLength={2000}
              placeholder={t("postPlaceholder")}
              className="w-full rounded-lg border border-input bg-card px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-ring"
              value={postBody}
              onChange={(e) => setPostBody(e.target.value)}
            />
            <div className="mt-2 flex justify-end">
              <Button type="submit" disabled={busy || !postBody.trim()}>
                {t("post")}
              </Button>
            </div>
          </form>

          {posts.length === 0 ? (
            <EmptyState
              icon={<MessageSquare className="size-7" />}
              title={t("noPosts")}
              body={t("noPostsBody")}
            />
          ) : (
            <ul className="space-y-4">
              {posts.map((p) => (
                <li key={p.id}>
                  <Card className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm font-medium text-foreground">
                        {p.author.name ?? "—"}
                        <span className="ms-2 text-xs font-normal text-muted-foreground">
                          <Bidi>{format.dateTime(new Date(p.created_at), {
                            dateStyle: "short",
                            timeStyle: "short",
                          })}</Bidi>
                        </span>
                      </p>
                      {p.can_delete && (
                        <button
                          onClick={() => onDeletePost(p.id)}
                          aria-label={t("deletePost")}
                          className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-destructive"
                        >
                          <Trash2 className="size-4" />
                        </button>
                      )}
                    </div>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-foreground">
                      <Linkify text={p.body} />
                    </p>

                    {p.comments.length > 0 && (
                      <ul className="mt-3 space-y-2 border-t border-border pt-3">
                        {p.comments.map((c) => (
                          <li
                            key={c.id}
                            className="flex items-start justify-between gap-2 text-sm"
                          >
                            <span>
                              <span className="font-medium text-foreground">
                                {c.author.name ?? "—"}:
                              </span>{" "}
                              <span className="text-foreground">{c.body}</span>
                            </span>
                            {c.can_delete && (
                              <button
                                onClick={async () => {
                                  await deletePostComment(deptId, p.id, c.id);
                                  router.refresh();
                                }}
                                className="shrink-0 rounded p-1 text-muted-foreground hover:text-destructive"
                              >
                                <Trash2 className="size-3.5" />
                              </button>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}

                    <div className="mt-3 flex gap-2">
                      <Input
                        placeholder={t("commentPlaceholder")}
                        maxLength={1000}
                        value={commentDrafts[p.id] ?? ""}
                        onChange={(e) =>
                          setCommentDrafts((prev) => ({
                            ...prev,
                            [p.id]: e.target.value,
                          }))
                        }
                      />
                      <Button
                        variant="secondary"
                        onClick={() => onComment(p.id)}
                        disabled={!(commentDrafts[p.id] ?? "").trim()}
                      >
                        {t("post")}
                      </Button>
                    </div>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function EmptyState({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="mt-12 flex flex-col items-center text-center">
      <span className="flex size-16 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
        {icon}
      </span>
      <p className="mt-4 text-lg font-semibold text-foreground">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{body}</p>
    </div>
  );
}
