import { backendBaseUrl } from "@/lib/techBackend";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(
  request: Request,
  { params }: { params: { session_id: string } }
) {
  try {
    const payload = await request.json();
    const backendUrl = `${backendBaseUrl()}/tech/sessions/${encodeURIComponent(params.session_id)}/message`;
    console.log("[api/tech/session/[id]/message] Posting to:", backendUrl);

    const res = await fetch(backendUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    console.log("[api/tech/session/[id]/message] Backend status:", res.status);

    if (!res.ok) {
      const raw = await res.text();
      console.error("[api/tech/session/[id]/message] Backend error response:", raw);
      return NextResponse.json(
        { error: `Backend returned ${res.status}: ${raw}` },
        { status: res.status }
      );
    }

    const raw = await res.text();
    let data: any;
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch (jsonError) {
      console.error("[api/tech/session/[id]/message] Failed to parse JSON:", jsonError);
      data = {
        detail: raw || "Backend returned a non-JSON response.",
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
      } catch (ttsError) {
        console.error("[api/tech/session/[id]/message] TTS pre-generation failed:", ttsError);
        // Keep text response usable even if TTS pre-generation fails.
      }
    }

    return NextResponse.json(data, { status: 200 });
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    console.error("[api/tech/session/[id]/message] Exception:", errorMsg, error);
    return NextResponse.json({ error: errorMsg }, { status: 500 });
  }
}
