"use client";

import { Loader2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { createCategory } from "@/app/[locale]/(app)/admin-actions";
import { publishBoardItem } from "@/app/[locale]/(app)/board-actions";
import { Dialog } from "@/components/dialog";
import { useToast } from "@/components/toast";
import { FileDrop } from "@/components/board/file-drop";
import { Button, FieldError, Input, Label, Select, cn } from "@/components/ui";
import type { BoardKind, CategoryRef } from "@/lib/board-types";
import { attempt, MAX_SEND_BYTES, tooBigParams, tooBigToSend, TRANSPORT_FAILED } from "@/lib/actions";
import { formatBytes, isolated } from "@/lib/format";

const MAX_FILE_BYTES = 25 * 1024 * 1024;
const MAX_PROMPT = 20000;

type Mode = "link" | "file" | "prompt";

// A <select> cannot contain a link, so the option carries a sentinel value
// and selecting it navigates instead of setting a category.
const ADD_CATEGORY = "__add_category__";

export function PublishDialog({
  open,
  onClose,
  onPublished,
  onCategoryAdded,
  categories,
  defaultDestination,
  canChooseDestination,
}: {
  open: boolean;
  onClose: () => void;
  onPublished: () => void;
  /** Refetch the list after one is added here, so it can be selected. */
  onCategoryAdded: () => void;
  categories: CategoryRef[];
  defaultDestination: "global" | "municipality";
  canChooseDestination: boolean;
}) {
  const t = useTranslations("board");
  const tc = useTranslations("common");
  const toast = useToast();
  const locale = useLocale();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState(categories[0]?.id ?? "");
  const [kind, setKind] = useState<BoardKind>("post");
  const [eventDate, setEventDate] = useState("");
  const [eventTime, setEventTime] = useState("");
  const [eventLocation, setEventLocation] = useState("");
  const [mode, setMode] = useState<Mode>("link");
  const [link, setLink] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [promptText, setPromptText] = useState("");
  const [destination, setDestination] = useState(defaultDestination);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Adding a category happens here rather than on a separate screen: the need
  // for one arrives mid-thought, while filling this form in.
  const [newCategory, setNewCategory] = useState<string | null>(null);
  const [savingCategory, setSavingCategory] = useState(false);

  async function addCategory() {
    const name = (newCategory ?? "").trim();
    if (!name) return;
    setSavingCategory(true);
    const res = await createCategory(name, null, null);
    setSavingCategory(false);
    if ("error" in res) {
      setError(res.status === 409 ? t("categoryExists") : tc("somethingWentWrong"));
      return;
    }
    setNewCategory(null);
    // The list comes from the server, so it has to be refetched before the new
    // category can be selected.
    onCategoryAdded();
  }

  const label = (c: CategoryRef) =>
    locale === "he" ? c.name_he : (c.name_en ?? c.name_he);

  function reset() {
    setTitle("");
    setDescription("");
    setLink("");
    setFile(null);
    setPromptText("");
    setKind("post");
    setEventDate("");
    setEventTime("");
    setEventLocation("");
    setError(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!title.trim() || title.length > 120) return setError(t("errTitle"));
    if (!categoryId) return setError(t("errCategory"));
    // A link may accompany a prompt — "here is the brief, and here is where the
    // agent lives" — so the link is validated whenever one was typed.
    if (link.trim() && !link.startsWith("https://")) return setError(t("errLink"));
    if (kind === "event" && !eventDate) return setError(t("eventDateRequired"));

    // Only a plain post must carry something. For the other kinds the words
    // are the point, and an attachment is welcome but not demanded.
    const needsContent = kind === "post";
    if (needsContent && mode === "link" && !link.trim()) return setError(t("errContent"));
    if (mode === "file") {
      if (needsContent && !file) return setError(t("errContent"));
      // Any file type is accepted; only the size is the client's business.
      if (file && file.size > MAX_FILE_BYTES) return setError(t("errFileSize"));
      if (file && tooBigToSend(file)) {
        const message = t("errFileTooBigToSend", tooBigParams(file));
        toast(message, "error");
        return setError(message);
      }
    }
    if (mode === "prompt") {
      if (needsContent && !promptText.trim()) return setError(t("errContent"));
      if (promptText.length > MAX_PROMPT) return setError(t("errPromptLength"));
    }

    setBusy(true);
    const fd = new FormData();
    fd.append("title", title.trim());
    fd.append("category_id", categoryId);
    fd.append("destination", destination);
    if (description.trim()) fd.append("description", description.trim());
    fd.append("kind", kind);
    if (kind === "event") {
      // Time is sent only when given, so the server can record that the day
      // was announced without an hour rather than inventing midnight.
      fd.append("event_at", eventTime ? `${eventDate}T${eventTime}` : eventDate);
      if (eventLocation.trim()) fd.append("event_location", eventLocation.trim());
    }
    if (link.trim()) fd.append("link_url", link.trim());
    if (mode === "file" && file) fd.append("file", file);
    if (mode === "prompt" && promptText.trim())
      fd.append("prompt_text", promptText.trim());

    // A server action can fail before it runs — the platform rejects an
    // oversized body with a 413 the action never sees, and the promise
    // rejects. Without this the button stayed disabled for good and said
    // nothing, which reads as "it is still uploading" forever.
    const res = await attempt(() => publishBoardItem(fd));
    setBusy(false);
    if ("error" in res) {
      const message =
        res.error === TRANSPORT_FAILED
          ? file
            ? t("errFileTooBigToSend", tooBigParams(file))
            : tc("somethingWentWrong")
          : res.status === 415
            ? t("errFileType")
            : res.status === 413
              ? t("errFileSize")
              : res.error === "link_must_be_https"
                ? t("errLink")
                : res.error === "event_date_required" ||
                    res.error === "invalid_event_date"
                  ? t("eventDateRequired")
                  : t("errContent");
      toast(message, "error");
      setError(message);
      return;
    }
    reset();
    onPublished();
  }

  // Category is required, so an empty list makes the form unsubmittable. Saying
  // so beats presenting an empty dropdown and a validation error on submit.
  if (open && categories.length === 0) {
    return (
      <Dialog open={open} onClose={onClose} title={t("publishTitle")}>
        <p className="text-sm text-muted-foreground">{t("noCategories")}</p>
        {/* Anyone can make the first one, rather than being told to find an
            administrator before they can post at all. */}
        <div className="mt-3 flex gap-2">
          <Input
            placeholder={t("newCategoryPlaceholder")}
            value={newCategory ?? ""}
            onChange={(e) => setNewCategory(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addCategory();
              }
            }}
          />
          <Button type="button" onClick={addCategory} disabled={savingCategory}>
            {tc("add")}
          </Button>
        </div>
        <FieldError>{error}</FieldError>
        <div className="mt-4 flex justify-end">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t("close")}
          </Button>
        </div>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onClose={onClose} title={t("publishTitle")} wide>
      {/* Two columns on a wide screen: what the post *is* on the left, what it
          *carries* on the right. As one column this was a long scroll, and the
          publish button sat below the fold on a laptop. One column below md,
          where side by side would be worse than scrolling. */}
      <form onSubmit={submit} className="grid gap-x-6 gap-y-4 md:grid-cols-2">
        <div className="space-y-4">
        <div>
          <Label htmlFor="title">{t("fieldTitle")}</Label>
          <Input
            id="title"
            required
            maxLength={120}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="description">{t("fieldDescription")}</Label>
          <textarea
            id="description"
            rows={3}
            maxLength={2000}
            className="w-full rounded-lg border border-input bg-card px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-ring"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="category">{t("fieldCategory")}</Label>
          <Select
            id="category"
            className="w-full"
            value={categoryId}
            onChange={(e) => {
              if (e.target.value === ADD_CATEGORY) {
                setNewCategory("");
                return;
              }
              setCategoryId(e.target.value);
            }}
          >
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {label(c)}
              </option>
            ))}
            {/* Anyone may add one; it opens a field below rather than sending
                them to a screen most people cannot reach. */}
            <option value={ADD_CATEGORY}>+ {t("addCategory")}</option>
          </Select>

          {newCategory !== null && (
            <div className="mt-2 flex gap-2">
              <Input
                autoFocus
                placeholder={t("newCategoryPlaceholder")}
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                onKeyDown={(e) => {
                  // Enter here must add the category, not submit the post
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addCategory();
                  }
                  if (e.key === "Escape") setNewCategory(null);
                }}
              />
              <Button type="button" onClick={addCategory} disabled={savingCategory}>
                {tc("add")}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setNewCategory(null)}
              >
                {t("close")}
              </Button>
            </div>
          )}
        </div>

        <div>
          <Label>{t("kindLabel")}</Label>
          <div className="flex flex-wrap gap-2">
            {(["post", "announcement", "event", "question"] as const).map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setKind(k)}
                className={cn(
                  "rounded-full px-4 py-1.5 text-sm font-medium",
                  kind === k
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-accent",
                )}
              >
                {k === "post"
                  ? t("kindPost")
                  : k === "announcement"
                    ? t("kindAnnouncement")
                    : k === "event"
                      ? t("kindEvent")
                      : t("kindQuestion")}
              </button>
            ))}
          </div>
        </div>

        {kind === "event" && (
          <div className="space-y-3 rounded-lg border border-border bg-muted/20 p-3">
            <div className="flex flex-wrap gap-3">
              <div className="min-w-40 flex-1">
                <Label htmlFor="event-date">{t("eventDate")}</Label>
                <Input
                  id="event-date"
                  type="date"
                  value={eventDate}
                  onChange={(e) => setEventDate(e.target.value)}
                />
              </div>
              <div className="min-w-32">
                <Label htmlFor="event-time">{t("addTimeOptional")}</Label>
                <Input
                  id="event-time"
                  type="time"
                  value={eventTime}
                  onChange={(e) => setEventTime(e.target.value)}
                />
              </div>
            </div>
            <div>
              <Label htmlFor="event-place">{t("eventLocation")}</Label>
              <Input
                id="event-place"
                placeholder={t("eventLocationPlaceholder")}
                value={eventLocation}
                onChange={(e) => setEventLocation(e.target.value)}
              />
            </div>
          </div>
        )}

        </div>

        <div className="space-y-4">
        <div>
          <Label>{t("contentType")}</Label>
          <div className="mb-2 flex gap-2">
            {(["link", "file", "prompt"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={cn(
                  "rounded-full px-4 py-1.5 text-sm font-medium",
                  mode === m
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-accent",
                )}
              >
                {m === "link"
                  ? t("typeLink")
                  : m === "file"
                    ? t("typeFile")
                    : t("typePrompt")}
              </button>
            ))}
          </div>
          {mode === "link" && (
            <Input
              id="link"
              type="url"
              dir="ltr"
              placeholder="https://"
              value={link}
              onChange={(e) => setLink(e.target.value)}
            />
          )}
          {mode === "file" && (
            /* No type filter: any file may be shared. */
            <FileDrop file={file} onFile={setFile} hint={t("fileHint", { size: isolated(formatBytes(MAX_SEND_BYTES)) })} />
          )}
          {mode === "prompt" && (
            <div className="space-y-2">
              <textarea
                id="prompt"
                rows={8}
                maxLength={MAX_PROMPT}
                placeholder={t("promptPlaceholder")}
                className="w-full rounded-lg border border-input bg-card px-3 py-2 font-mono text-sm focus-visible:outline-2 focus-visible:outline-ring"
                value={promptText}
                onChange={(e) => setPromptText(e.target.value)}
              />
              <div>
                <Label htmlFor="prompt-link">{t("promptLinkOptional")}</Label>
                <Input
                  id="prompt-link"
                  type="url"
                  dir="ltr"
                  placeholder="https://"
                  value={link}
                  onChange={(e) => setLink(e.target.value)}
                />
              </div>
            </div>
          )}
        </div>

        {canChooseDestination && (
          <div>
            <Label htmlFor="destination">{t("destination")}</Label>
            <Select
              id="destination"
              className="w-full"
              value={destination}
              onChange={(e) =>
                setDestination(e.target.value as "global" | "municipality")
              }
            >
              <option value="global">{t("destGlobal")}</option>
              <option value="municipality">{t("destMunicipality")}</option>
            </Select>
          </div>
        )}

        </div>

        <div className="space-y-3 md:col-span-2">
          <FieldError>{error}</FieldError>
          {/* A file takes seconds to travel, and a button that only greys out
              looks like nothing happened. */}
          <Button type="submit" disabled={busy} className="w-full">
            {busy && <Loader2 className="size-4 animate-spin" />}
            {busy ? (mode === "file" && file ? t("uploading") : t("sending")) : t("send")}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
