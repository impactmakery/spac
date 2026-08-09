"use client";

import {
  ArrowRight,
  Download,
  ExternalLink,
  Heart,
  MessageCircle,
  Pencil,
  Trash2,
} from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import {
  addComment,
  deleteBoardItem,
  deleteComment,
  editBoardItem,
  toggleLike,
} from "@/app/[locale]/(app)/board-actions";
import { Avatar } from "@/components/avatar";
import { CategoryChip } from "@/components/board/item-card";
import { PromptBlock } from "@/components/board/prompt-block";
import { Reactions } from "@/components/board/reactions";
import { Dialog } from "@/components/dialog";
import { Linkify } from "@/components/linkify";
import { Button, Card, FieldError, Input, Label, Select } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import type {
  BoardComment,
  BoardItemDetail,
  CategoryRef,
} from "@/lib/board-types";
import { formatBytes } from "@/lib/format";

export function ItemClient({
  item,
  categories,
  apiBase,
  startEditing = false,
}: {
  item: BoardItemDetail;
  categories: CategoryRef[];
  apiBase: string;
  /** Set by ?edit=1, so the edit action on a board card lands straight in the
   *  form rather than making the user find the button again. */
  startEditing?: boolean;
}) {
  const t = useTranslations("board");
  const format = useFormatter();
  const locale = useLocale();
  const router = useRouter();

  const [liked, setLiked] = useState(item.liked_by_me);
  const [likeCount, setLikeCount] = useState(item.like_count);
  const [comment, setComment] = useState("");
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const [replyBody, setReplyBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [editOpen, setEditOpen] = useState(startEditing && item.can_edit);
  const [externalOpen, setExternalOpen] = useState(false);
  const [title, setTitle] = useState(item.title);
  const [description, setDescription] = useState(item.description ?? "");
  const [categoryId, setCategoryId] = useState(item.category.id);
  const [error, setError] = useState<string | null>(null);

  const backHref = item.scope === "global" ? "/board" : "/municipality";
  const downloadUrl = item.download_url
    ? item.download_url.startsWith("/")
      ? `${apiBase}${item.download_url}`
      : item.download_url
    : null;

  async function onLike() {
    const res = await toggleLike(item.id);
    if ("ok" in res && res.data) {
      setLiked(res.data.liked);
      setLikeCount(res.data.like_count);
    }
  }

  async function onComment(e: React.FormEvent) {
    e.preventDefault();
    if (!comment.trim()) return;
    setBusy(true);
    await addComment(item.id, comment.trim().slice(0, 1000));
    setComment("");
    setBusy(false);
    router.refresh();
  }

  async function onReply(e: React.FormEvent, parentId: string) {
    e.preventDefault();
    if (!replyBody.trim()) return;
    setBusy(true);
    await addComment(item.id, replyBody.trim().slice(0, 1000), parentId);
    setReplyBody("");
    setReplyTo(null);
    setBusy(false);
    router.refresh();
  }

  async function onDeleteComment(commentId: string) {
    await deleteComment(item.id, commentId);
    router.refresh();
  }

  async function onDeleteItem() {
    if (!window.confirm(t("deleteConfirm"))) return;
    await deleteBoardItem(item.id);
    router.push(backHref);
    router.refresh();
  }

  async function onSaveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || title.length > 120) {
      setError(t("errTitle"));
      return;
    }
    setBusy(true);
    const res = await editBoardItem(item.id, {
      title: title.trim(),
      description: description.trim() || null,
      category_id: categoryId,
    });
    setBusy(false);
    if ("error" in res) {
      setError(res.error);
      return;
    }
    setEditOpen(false);
    router.refresh();
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <Link
        href={backHref}
        className="mb-4 inline-flex items-center gap-1 text-sm text-primary hover:underline"
      >
        <ArrowRight className="size-4 ltr:rotate-180" />
        {item.scope === "global" ? t("globalTitle") : t("municipalitySubtitle")}
      </Link>

      <Card className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <CategoryChip category={item.category} />
          <div className="flex gap-2">
            {item.can_edit && (
              <Button
                variant="ghost"
                className="px-2 py-1"
                onClick={() => setEditOpen(true)}
              >
                <Pencil className="size-4" />
                {t("edit")}
              </Button>
            )}
            {item.can_delete && (
              <Button
                variant="ghost"
                className="px-2 py-1 text-destructive"
                onClick={onDeleteItem}
              >
                <Trash2 className="size-4" />
                {t("delete")}
              </Button>
            )}
          </div>
        </div>

        <h1 className="mt-3 text-2xl font-bold text-foreground">{item.title}</h1>
        {item.description && (
          <p className="mt-2 whitespace-pre-wrap text-foreground">
            <Linkify text={item.description} />
          </p>
        )}

        {item.prompt_text && (
          <div className="mt-4">
            <PromptBlock text={item.prompt_text} />
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          {item.link_url && (
            <Button variant="secondary" onClick={() => setExternalOpen(true)}>
              <ExternalLink className="size-4" />
              {t("openLink")}
            </Button>
          )}
          {downloadUrl && (
            <Button
              variant="secondary"
              onClick={() => window.open(downloadUrl, "_blank", "noopener")}
            >
              <Download className="size-4" />
              {item.filename}
              {item.size_bytes != null && ` (${formatBytes(item.size_bytes)})`}
            </Button>
          )}
        </div>

        <div className="mt-5 flex items-center justify-between border-t border-border pt-4 text-sm text-muted-foreground">
          <span>
            {item.author.name ?? "—"}
            {item.author.inactive && ` (${t("inactiveAuthor")})`}
            {item.author.municipality_name && ` · ${item.author.municipality_name}`} ·{" "}
            {format.dateTime(new Date(item.created_at), { dateStyle: "medium" })}
          </span>
          <button
            onClick={onLike}
            className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 hover:bg-muted"
          >
            <Heart className={liked ? "size-4 fill-primary text-primary" : "size-4"} />
            {likeCount}
          </button>
        </div>
      </Card>

      <section className="mt-8">
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-foreground">
          <MessageCircle className="size-5" />
          {t("comments")} ({item.comments.length})
        </h2>

        {item.comments.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("noComments")}</p>
        ) : (
          <ul className="space-y-3">
            {item.comments
              .filter((c) => !c.parent_id)
              .map((c) => {
                const replies = item.comments.filter((r) => r.parent_id === c.id);
                return (
                  <li key={c.id}>
                    <CommentCard
                      comment={c}
                      itemId={item.id}
                      onChanged={() => router.refresh()}
                      onDelete={onDeleteComment}
                      onReplyClick={() => {
                        setReplyTo(replyTo === c.id ? null : c.id);
                        setReplyBody("");
                      }}
                    />

                    {(replies.length > 0 || replyTo === c.id) && (
                      <ul className="mt-2 space-y-2 border-s-2 border-border ps-4 ms-4">
                        {replies.map((r) => (
                          <li key={r.id}>
                            <CommentCard
                              comment={r}
                              itemId={item.id}
                              onChanged={() => router.refresh()}
                              onDelete={onDeleteComment}
                            />
                          </li>
                        ))}
                        {replyTo === c.id && (
                          <li>
                            <form
                              onSubmit={(e) => onReply(e, c.id)}
                              className="flex gap-2"
                            >
                              <Input
                                autoFocus
                                placeholder={t("replyPlaceholder")}
                                maxLength={1000}
                                value={replyBody}
                                onChange={(e) => setReplyBody(e.target.value)}
                              />
                              <Button type="submit" disabled={busy}>
                                {t("reply")}
                              </Button>
                            </form>
                          </li>
                        )}
                      </ul>
                    )}
                  </li>
                );
              })}
          </ul>
        )}

        <form onSubmit={onComment} className="mt-4 flex gap-2">
          <Input
            placeholder={t("commentPlaceholder")}
            maxLength={1000}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
          <Button type="submit" disabled={busy || !comment.trim()}>
            {t("addComment")}
          </Button>
        </form>
      </section>

      <Dialog open={editOpen} onClose={() => setEditOpen(false)} title={t("editTitle")}>
        <form onSubmit={onSaveEdit} className="space-y-4">
          <div>
            <Label htmlFor="edit-title">{t("fieldTitle")}</Label>
            <Input
              id="edit-title"
              required
              maxLength={120}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="edit-desc">{t("fieldDescription")}</Label>
            <textarea
              id="edit-desc"
              rows={3}
              maxLength={2000}
              className="w-full rounded-lg border border-input bg-card px-3 py-2 text-sm"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="edit-cat">{t("fieldCategory")}</Label>
            <Select
              id="edit-cat"
              className="w-full"
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {locale === "he" ? c.name_he : (c.name_en ?? c.name_he)}
                </option>
              ))}
            </Select>
          </div>
          <FieldError>{error}</FieldError>
          <Button type="submit" disabled={busy} className="w-full">
            {t("save")}
          </Button>
        </form>
      </Dialog>

      <Dialog
        open={externalOpen}
        onClose={() => setExternalOpen(false)}
        title={t("externalTitle")}
      >
        <p className="break-all text-sm text-muted-foreground">
          {t("externalBody", { url: item.link_url ?? "" })}
        </p>
        <div className="mt-4 flex gap-2">
          <Button
            onClick={() => {
              window.open(item.link_url ?? "", "_blank", "noopener,noreferrer");
              setExternalOpen(false);
            }}
          >
            {t("externalContinue")}
          </Button>
          <Button variant="ghost" onClick={() => setExternalOpen(false)}>
            {t("cancel")}
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

function CommentCard({
  comment,
  itemId,
  onDelete,
  onReplyClick,
  onChanged,
}: {
  comment: BoardComment;
  itemId: string;
  onDelete: (id: string) => void;
  /** Only top-level comments offer a reply: threads are one level deep. */
  onReplyClick?: () => void;
  onChanged: () => void;
}) {
  const t = useTranslations("board");
  const format = useFormatter();
  return (
    <Card className="flex items-start gap-3 p-4">
      <Avatar name={comment.author.name} seed={comment.author.id} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">
          {comment.author.name ?? "—"}
          {comment.author.inactive && ` (${t("inactiveAuthor")})`}
          <span className="ms-2 text-xs font-normal text-muted-foreground">
            {format.dateTime(new Date(comment.created_at), {
              dateStyle: "short",
              timeStyle: "short",
            })}
          </span>
        </p>
        <p className="mt-1 whitespace-pre-wrap text-sm text-foreground">
          <Linkify text={comment.body} />
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Reactions
            itemId={itemId}
            commentId={comment.id}
            reactions={comment.reactions}
            onChanged={onChanged}
          />
          {onReplyClick && (
            <button
              type="button"
              onClick={onReplyClick}
              className="mt-1.5 text-xs font-medium text-primary hover:underline"
            >
              {t("reply")}
            </button>
          )}
        </div>
      </div>
      {comment.can_delete && (
        <button
          onClick={() => onDelete(comment.id)}
          aria-label={t("delete")}
          className="shrink-0 rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-destructive"
        >
          <Trash2 className="size-4" />
        </button>
      )}
    </Card>
  );
}
