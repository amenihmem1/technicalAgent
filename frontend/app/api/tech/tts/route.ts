import { backendBaseUrl } from "@/lib/techBackend";
export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    const res = await fetch(`${backendBaseUrl()}/tech/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const raw = await res.text();
      return new Response(raw || "TTS unavailable", { status: res.status });
    }

    const audio = await res.arrayBuffer();
    return new Response(audio, {
      status: 200,
      headers: {
        "Content-Type": "audio/wav",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return new Response((error as Error).message, { status: 500 });
  }
}
