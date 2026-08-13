import { getLocale } from "next-intl/server";
import { ChatClient } from "@/components/chat/chat-client";
import { redirect } from "@/i18n/navigation";
import { apiFetch } from "@/lib/api";
import type { ConversationRow } from "@/lib/chat-types";

export default async function ChatPage() {
  const conversations = await apiFetch<ConversationRow[]>("/api/conversations");

  // Reopen where they left off. Conversations come back most-recently-updated
  // first, so the newest is the one they were last in. "New chat" creates its
  // conversation and goes straight to its own address, so it never arrives
  // here and cannot be bounced away.
  if (conversations.length > 0) {
    redirect({ href: `/chat/${conversations[0].id}`, locale: await getLocale() });
  }

  // Only someone with no conversations at all sees the starter questions,
  // which is exactly who they are for.
  const sampleQuestions = await apiFetch<string[]>(`/api/chat/sample-questions?lang=${await getLocale()}`);
  return (
    <ChatClient
      conversations={conversations}
      conversationId={null}
      initialMessages={[]}
      sampleQuestions={sampleQuestions}
    />
  );
}
