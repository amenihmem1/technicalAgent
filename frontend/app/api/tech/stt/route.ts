import { NextResponse } from "next/server";

export const runtime = "nodejs";

function backendBaseUrl() {
  return process.env.TECH_API_BASE_URL || "http://127.0.0.1:8001";
}

function normalizeSttLanguage(value: unknown) {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "fr" || normalized === "en" || normalized === "multi") {
    return normalized;
  }
  return "";
}

function sttProxyTimeoutMs() {
  const parsed = Number(process.env.STT_PROXY_TIMEOUT_MS || "");
  return Number.isFinite(parsed) && parsed >= 3000 ? parsed : 12000;
}

export async function POST(request: Request) {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  try {
    const form = await request.formData();
    const file = form.get("file");
    const requestedLanguage = normalizeSttLanguage(form.get("language"));
    const configuredLanguage = normalizeSttLanguage(process.env.STT_LANGUAGE);
    const language = requestedLanguage || configuredLanguage || "fr";
    if (!(file instanceof File)) {
      return NextResponse.json({ error: "Field 'file' is required." }, { status: 400 });
    }

    const forward = new FormData();
    forward.append("file", file, file.name || "recording.webm");
    forward.append("language", language);

    const controller = new AbortController();
    timeoutId = setTimeout(() => controller.abort(), sttProxyTimeoutMs());
    const res = await fetch(`${backendBaseUrl()}/tech/stt`, {
      method: "POST",
      body: forward,
      signal: controller.signal,
    });
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    if ((error as Error).name === "AbortError") {
      return NextResponse.json(
        { error: "The transcription service timed out quickly. Browser transcription will be used when available." },
        { status: 504 }
      );
    }
    return NextResponse.json({ error: (error as Error).message }, { status: 500 });
  }
}


