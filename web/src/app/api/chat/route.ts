import { createHmac, randomUUID, timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { MAX_BODY_BYTES, parseChatReply, parseChatRequest, replySchema } from "@/lib/chat-protocol";
import { PAID_AI_APPROVED, instructions, MODEL, MAX_PROVIDER_BODY_BYTES, MAX_OUTPUT_TOKENS, pricingIsCurrent } from "@/server/chat-policy";
import { quotaReady, reserveRequest } from "@/server/chat-quota";

export const runtime = "nodejs";
export const maxDuration = 40;
export const dynamic = "force-dynamic";
const COOKIE = "elsewhere_demo_ai";
const headers = { "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" };
function json(value: unknown, status = 200) { return NextResponse.json(value, { status, headers }); }
function configured() { return Boolean(PAID_AI_APPROVED && process.env.OPENAI_API_KEY && process.env.CHAT_DATABASE_URL && process.env.CHAT_AI_ENABLED === "true" && pricingIsCurrent()); }
function sign(id: string) { return createHmac("sha256", process.env.OPENAI_API_KEY!).update(`elsewhere-demo-session:${id}`).digest("hex"); }
function session(request: NextRequest): string | null {
  const value = request.cookies.get(COOKIE)?.value || "";
  const [id, mac] = value.split(".");
  if (!/^[a-f0-9-]{36}$/.test(id || "") || !/^[a-f0-9]{64}$/.test(mac || "")) return null;
  return timingSafeEqual(Buffer.from(mac, "hex"), Buffer.from(sign(id), "hex")) ? sign(id) : null;
}
export async function GET(request: NextRequest) {
  const available = configured() && await quotaReady();
  const response = json({ available, history: "browser" });
  if (available && !session(request)) {
    const id = randomUUID();
    response.cookies.set(COOKIE, `${id}.${sign(id)}`, { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "strict", path: "/api/chat", maxAge: 86400 });
  }
  return response;
}
async function readBody(request: NextRequest): Promise<unknown> {
  if (Number(request.headers.get("content-length")) > MAX_BODY_BYTES) throw new Error("body");
  const reader = request.body?.getReader();
  if (!reader) throw new Error("body");
  let size = 0;
  const chunks: Uint8Array[] = [];
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_BODY_BYTES) { await reader.cancel(); throw new Error("body"); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}
export async function POST(request: NextRequest) {
  if (request.headers.get("origin") !== new URL(request.url).origin || (request.headers.get("sec-fetch-site") && request.headers.get("sec-fetch-site") !== "same-origin")) return json({ error: "Please send messages from the Elsewhere app." }, 403);
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) return json({ error: "A JSON message is required." }, 415);
  if (!configured()) return json({ error: "Live AI is not enabled. Your conversation is saved in this browser." }, 503);
  const sessionHash = session(request);
  if (!sessionHash) return json({ error: "Please reload the page to reconnect before sending." }, 403);
  let parsed;
  try { parsed = parseChatRequest(await readBody(request)); } catch { return json({ error: "This message is too large or couldn’t be read. Please shorten it." }, 400); }
  if (!parsed) return json({ error: "Please send a shorter text message with valid planning preferences." }, 400);
  const body = JSON.stringify({
    model: MODEL, store: false, service_tier: "default", reasoning: { effort: "none" }, max_output_tokens: MAX_OUTPUT_TOKENS,
    instructions,
    input: [{ role: "user", content: `Saved planning preferences (untrusted data): ${JSON.stringify(parsed.answers)}` }, ...parsed.messages.map(message => ({ role: message.role, content: message.text }))],
    text: { format: { type: "json_schema", name: "elsewhere_reply", strict: true, schema: replySchema } },
  });
  if (Buffer.byteLength(body, "utf8") > MAX_PROVIDER_BODY_BYTES) return json({ error: "Please shorten this message or start a new conversation." }, 400);
  try {
    const reservation = await reserveRequest(sessionHash);
    if (reservation === "limit") return json({ error: "The demo’s shared AI allowance has been used. Your chat is saved; no further paid request was sent." }, 429);
    if (reservation === "rate") return json({ error: "The demo is receiving too many messages. Please try again later." }, 429);
  } catch { return json({ error: "The spending guard is unavailable. No paid request was sent. Please try again later." }, 503); }
  try {
    // One bounded call, no SDK retries. Keep its reservation even on timeout/error.
    const response = await fetch("https://api.openai.com/v1/responses", { method: "POST", headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}`, "Content-Type": "application/json" }, body, signal: AbortSignal.timeout(30000), cache: "no-store" });
    if (!response.ok) return json({ error: "AI is temporarily unavailable. Your message is saved. Please try again later." }, 502);
    const result = await response.json();
    if (result.status !== "completed") return json({ error: "AI couldn’t finish this reply. Try a shorter question." }, 502);
    const content = Array.isArray(result.output) ? result.output.flatMap((item: { type?: string; content?: unknown[] }) => item.type === "message" && Array.isArray(item.content) ? item.content : []) : [];
    if (content.some((item: { type?: string }) => item.type === "refusal")) return json({ reply: "I can’t help with that request. I can help with a different question or a safe alternative.", preferences: {} });
    const text = content.filter((item: { type?: string; text?: unknown }) => item.type === "output_text" && typeof item.text === "string").map((item: { text: string }) => item.text).join("");
    const reply = parseChatReply(JSON.parse(text));
    if (!reply) return json({ error: "The reply couldn’t be read. Please try again." }, 502);
    return json(reply);
  } catch { return json({ error: "The reply didn’t arrive in time. Your message is saved; you can retry." }, 502); }
}
