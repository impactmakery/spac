"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { publishBoardItem } from "@/app/[locale]/(app)/board-actions";
import { Dialog } from "@/components/dialog";
import { Button, FieldError, Input, Label, Select, cn } from "@/components/ui";
import type { CategoryRef } from "@/lib/board-types";

const MAX_FILE_BYTES = 25 * 1024 * 1024;
const MAX_PROMPT = 20000;

type Mode = "link" | "file" | "prompt";

export function PublishDialog({
  open,
  onClose,
  onPublished,
  categories,
  defaultDestination,
  canChooseDestination,
}: {
  open: boolean;
  onClose: () => void;
  onPublished: () => void;
  categories: CategoryRef[];
  defaultDestination: "global" | "municipality";
  canChooseDestination: boolean;
}) {
  const t = useTranslations("board");
  const locale = useLocale();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState(categories[0]?.id ?? "");
  const [mode, setMode] = useState<Mode>("link");
  const [link, setLink] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [promptText, setPromptText] = useState("");
  const [destination, setDestination] = useState(defaultDestination);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const label = (c: CategoryRef) =>
    locale === "he" ? c.name_he : (c.name_en ?? c.name_he);

  function reset() {
    setTitle("");
    setDescription("");
    setLink("");
    setFile(null);
    setPromptText("");
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
    if (mode === "link" && !link.trim()) return setError(t("errContent"));
    if (mode === "file") {
      if (!file) return setError(t("errContent"));
      // Any file type is accepted; only the size is the client's business.
      if (file.size > MAX_FILE_BYTES) return setError(t("errFileSize"));
    }
    if (mode === "prompt") {
      if (!promptText.trim()) return setError(t("errContent"));
      if (promptText.length > MAX_PROMPT) return setError(t("errPromptLength"));
    }

    setBusy(true);
    const fd = new FormData();
    fd.append("title", title.trim());
    fd.append("category_id", categoryId);
    fd.append("destination", destination);
    if (description.trim()) fd.append("description", description.trim());
    if (link.trim()) fd.append("link_url", link.trim());
    if (mode === "file" && file) fd.append("file", file);
    if (mode === "prompt" && promptText.trim())
      fd.append("prompt_text", promptText.trim());

    const res = await publishBoardItem(fd);
    setBusy(false);
    if ("error" in res) {
      setError(
        res.status === 415
          ? t("errFileType")
          : res.status === 413
            ? t("errFileSize")
            : res.error === "link_must_be_https"
              ? t("errLink")
              : t("errContent"),
      );
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
        <div className="mt-4 flex justify-end">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t("close")}
          </Button>
        </div>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onClose={onClose} title={t("publishTitle")}>
      <form onSubmit={submit} className="space-y-4">
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
            onChange={(e) => setCategoryId(e.target.value)}
          >
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {label(c)}
              </option>
            ))}
          </Select>
        </div>

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
            <>
              {/* No `accept` filter: any file type may be shared. */}
              <input
                id="file"
                type="file"
                className="w-full text-sm"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              <p className="mt-1 text-xs text-muted-foreground">{t("fileHint")}</p>
            </>
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

        <FieldError>{error}</FieldError>
        <Button type="submit" disabled={busy} className="w-full">
          {t("send")}
        </Button>
      </form>
    </Dialog>
  );
}
