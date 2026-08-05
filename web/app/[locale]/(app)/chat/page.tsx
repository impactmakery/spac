import { ChatClient } from "@/components/chat/chat-client";
import { apiFetch } from "@/lib/api";
import type { ConversationRow } from "@/lib/chat-types";

export default async function ChatPage() {
  const [conversations, sampleQuestions] = await Promise.all([
    apiFetch<ConversationRow[]>("/api/conversations"),
    apiFetch<string[]>("/api/chat/sample-questions"),
  ]);
  return (
    <ChatClient
      conversations={conversations}
      conversationId={null}
      initialMessages={[]}
      sampleQuestions={sampleQuestions}
    />
  );
}
