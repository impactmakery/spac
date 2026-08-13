import { getLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { ChatClient } from "@/components/chat/chat-client";
import { ApiError, apiFetch } from "@/lib/api";
import type { ChatMessage, ConversationRow } from "@/lib/chat-types";

export default async function ConversationPage({
  params,
}: PageProps<"/[locale]/chat/[conversationId]">) {
  const { conversationId } = await params;
  let messages: ChatMessage[];
  try {
    messages = await apiFetch<ChatMessage[]>(
      `/api/conversations/${conversationId}/messages`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const [conversations, sampleQuestions] = await Promise.all([
    apiFetch<ConversationRow[]>("/api/conversations"),
    apiFetch<string[]>(`/api/chat/sample-questions?lang=${await getLocale()}`),
  ]);

  return (
    <ChatClient
      conversations={conversations}
      conversationId={conversationId}
      initialMessages={messages}
      sampleQuestions={sampleQuestions}
    />
  );
}
