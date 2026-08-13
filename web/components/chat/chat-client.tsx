"use client";

import { MessageCircle, Pencil, Plus, Send, Sparkles, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import {
  createConversation,
  deleteConversation,
  renameConversation,
} from "@/app/[locale]/(app)/chat-actions";
import { LogoChip } from "@/components/logo";
import { Button, Card, cn } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import type { ChatMessage, Citation, ConversationRow } from "@/lib/chat-types";
import { useConfirm } from "@/components/confirm";
import { AnswerText } from "@/components/chat/answer-text";
import { attempt } from "@/lib/actions";

interface Pending {
  content: string;
  citations: Citation[] | null;
}

export function ChatClient({
  conversations,
  conversationId,
  initialMessages,
  sampleQuestions,
}: {
  conversations: ConversationRow[];
  conversationId: string | null;
  initialMessages: ChatMessage[];
  sampleQuestions: string[];
}) {
  const t = useTranslations("chat");
  const confirm = useConfirm();
  const tc = useTranslations("common");
  const router = useRouter();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // Server data replaces local state when the route refreshes or changes
  // conversation — adjusted during render, not in an effect.
  const [syncedFrom, setSyncedFrom] = useState(initialMessages);
  if (syncedFrom !== initialMessages) {
    setSyncedFrom(initialMessages);
    setMessages(initialMessages);
    setPendingUser(null);
    setPending(null);
  }

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  async function send(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    setError(null);
    setBusy(true);
    setInput("");

    let targetId = conversationId;
    if (!targetId) {
      // Outside the try that owns the finally below, so a rejection here would
      // leave the composer disabled with the question already cleared.
      const created = await attempt(() => createConversation());
      if ("error" in created || !created.data) {
        setError(t("errorSend"));
        setBusy(false);
        return;
      }
      targetId = created.data.id;
    }

    setPendingUser(text);
    setPending({ content: "", citations: null });

    try {
      const res = await fetch(`/api/chat/${targetId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text }),
      });
      if (res.status === 429) {
        setError(t("rateLimited"));
        setBusy(false);
        setPendingUser(null);
        setPending(null);
        return;
      }
      if (!res.ok || !res.body) throw new Error("stream failed");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let answer = "";
      let citations: Citation[] | null = null;

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          const lines = block.split("\n");
          const event = lines[0]?.replace("event: ", "");
          const dataLine = lines[1]?.replace("data: ", "");
          if (!event || !dataLine) continue;
          const payload = JSON.parse(dataLine);
          if (event === "token") {
            answer += payload as string;
            setPending({ content: answer, citations });
          } else if (event === "citations") {
            citations = payload as Citation[];
            setPending({ content: answer, citations });
          }
        }
      }

      if (!conversationId) {
        router.push(`/chat/${targetId}`);
      }
      router.refresh();
    } catch {
      setError(t("errorSend"));
      setPendingUser(null);
      setPending(null);
    } finally {
      setBusy(false);
    }
  }

  async function onNewChat() {
    const created = await attempt(() => createConversation());
    if ("ok" in created && created.data) {
      router.push(`/chat/${created.data.id}`);
      router.refresh();
    }
  }

  async function onRename(convo: ConversationRow) {
    const next = window.prompt(t("renamePrompt"), convo.title ?? "");
    if (!next?.trim()) return;
    await renameConversation(convo.id, next.trim());
    router.refresh();
  }

  async function onDelete(convo: ConversationRow) {
    if (!(await confirm({ title: tc("deleteTitle"), body: t("deleteConfirm") }))) return;
    await deleteConversation(convo.id);
    if (convo.id === conversationId) router.push("/chat");
    router.refresh();
  }

  const showEmptyState = messages.length === 0 && !pendingUser;

  return (
    <div className="flex h-[calc(100vh-0px)] min-h-0 flex-col md:flex-row">
      {/* conversation rail */}
      <aside className="hidden w-64 shrink-0 flex-col border-e border-border bg-card/60 lg:flex">
        <div className="p-3">
          <Button className="w-full" onClick={onNewChat}>
            <Plus className="size-4" />
            {t("newChat")}
          </Button>
        </div>
        <p className="px-4 pb-2 text-xs font-medium text-muted-foreground">
          {t("conversations")}
        </p>
        <nav className="flex-1 space-y-1 overflow-y-auto px-2 pb-3">
          {conversations.length === 0 && (
            <p className="px-2 text-sm text-muted-foreground">{t("noConversations")}</p>
          )}
          {conversations.map((c) => (
            <div
              key={c.id}
              className={cn(
                "group flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm",
                c.id === conversationId
                  ? "bg-accent text-accent-foreground"
                  : "text-foreground hover:bg-muted",
              )}
            >
              <Link href={`/chat/${c.id}`} className="min-w-0 flex-1 truncate">
                {c.title ?? t("newChat")}
              </Link>
              <button
                onClick={() => onRename(c)}
                className="opacity-0 transition group-hover:opacity-100"
                aria-label={t("rename")}
              >
                <Pencil className="size-3.5 text-muted-foreground hover:text-foreground" />
              </button>
              <button
                onClick={() => onDelete(c)}
                className="opacity-0 transition group-hover:opacity-100"
                aria-label={t("delete")}
              >
                <Trash2 className="size-3.5 text-muted-foreground hover:text-destructive" />
              </button>
            </div>
          ))}
        </nav>
        <p className="border-t border-border p-3 text-xs text-muted-foreground">
          {t("privateNote")}
        </p>
      </aside>

      {/* thread */}
      <div className="flex min-h-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-border bg-card/60 px-6 py-4">
          <LogoChip />
          <div>
            <p className="font-bold text-foreground">{t("title")}</p>
            <p className="text-xs text-muted-foreground">{t("subtitle")}</p>
          </div>
        </header>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-6">
          {showEmptyState ? (
            <div className="mx-auto max-w-2xl">
              <AssistantBubble content={t("greeting")} citations={null} />
              {sampleQuestions.length > 0 && (
                <div className="mt-6 grid gap-2 sm:grid-cols-2">
                  {sampleQuestions.map((q) => (
                    <button
                      key={q}
                      onClick={() => send(q)}
                      className="rounded-xl border border-border bg-card p-3 text-start text-sm text-foreground shadow-sm transition hover:border-primary"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="mx-auto max-w-2xl space-y-4">
              {messages.map((m) =>
                m.role === "user" ? (
                  <UserBubble key={m.id} content={m.content} />
                ) : (
                  <AssistantBubble
                    key={m.id}
                    content={m.content}
                    citations={m.citations}
                  />
                ),
              )}
              {pendingUser && <UserBubble content={pendingUser} />}
              {pending && (
                <AssistantBubble
                  content={pending.content || t("thinking")}
                  citations={pending.citations}
                />
              )}
            </div>
          )}
          <div ref={endRef} />
        </div>

        <div className="border-t border-border bg-card/60 px-6 py-4">
          <div className="mx-auto max-w-2xl">
            {error && <p className="mb-2 text-sm text-destructive">{error}</p>}
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                send(input);
              }}
            >
              <textarea
                rows={1}
                value={input}
                placeholder={t("placeholder")}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send(input);
                  }
                }}
                className="min-h-11 flex-1 resize-none rounded-lg border border-input bg-card px-3 py-2.5 text-sm focus-visible:outline-2 focus-visible:outline-ring"
              />
              <Button
                type="submit"
                disabled={busy || !input.trim()}
                className="size-11 shrink-0 p-0"
                aria-label={t("send")}
              >
                <Send className="size-4 ltr:rotate-180" />
              </Button>
            </form>
            <p className="mt-2 text-center text-xs text-muted-foreground">
              {t("grounding")}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] whitespace-pre-wrap rounded-xl bg-accent px-4 py-3 text-sm text-accent-foreground">
        {content}
      </div>
    </div>
  );
}

function AssistantBubble({
  content,
  citations,
}: {
  content: string;
  citations: Citation[] | null;
}) {
  const t = useTranslations("chat");
  return (
    <div className="flex items-start gap-3">
      <span className="mt-1 flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Sparkles className="size-4" />
      </span>
      <Card className="max-w-[85%] p-4">
        <AnswerText content={content} />
        {citations && citations.length > 0 && (
          <div className="mt-3 border-t border-border pt-3">
            <p className="mb-1.5 text-xs font-medium text-muted-foreground">
              {t("sources")}
            </p>
            <div className="flex flex-wrap gap-2">
              {citations.map((c) => (
                <Link
                  key={`${c.source_id}-${c.index}`}
                  href={c.href}
                  className="inline-flex items-center gap-1 rounded-full bg-accent px-2.5 py-1 text-xs text-accent-foreground hover:underline"
                >
                  <MessageCircle className="size-3" />[{c.index}] {c.title}
                </Link>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
