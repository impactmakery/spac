import { auth } from "@/auth";

/** Streams the assistant's SSE response, keeping the API token server-side. */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ conversationId: string }> },
) {
  const session = await auth();
  if (!session) return new Response("unauthorized", { status: 401 });

  const { conversationId } = await params;
  const body = await request.text();

  const upstream = await fetch(
    `${process.env.API_BASE_URL}/api/chat/${conversationId}/messages`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.apiToken}`,
      },
      body,
    },
  );

  if (!upstream.ok || !upstream.body) {
    return new Response(await upstream.text(), { status: upstream.status });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
