import { backendBaseUrl } from "@/lib/techBackend";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

type RouteParams = {
  params: Promise<{ session_id: string }>;
};

export async function POST(request: Request, { params }: RouteParams) {
  const { session_id } = await params;

  try {
    const payload = await request.json();
    const res = await fetch(`${backendBaseUrl()}/tech/sessions/${encodeURIComponent(session_id)}/finalize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    const raw = await res.text();
    let data: any;
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      data = {
        detail: raw || "Backend returned a non-JSON error.",
      };
    }

    if (res.ok && data?.say) {
      try {
        const ttsRes = await fetch(`${backendBaseUrl()}/tech/tts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: data.say }),
        });
        if (ttsRes.ok) {
          const audio = await ttsRes.arrayBuffer();
          data.audio_base64 = Buffer.from(audio).toString("base64");
          data.audio_mime_type = ttsRes.headers.get("content-type") || "audio/wav";
        }
      } catch {
        // Keep text response usable even if TTS pre-generation fails.
      }
    }

    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    return NextResponse.json({ error: (error as Error).message }, { status: 500 });
  }
}
