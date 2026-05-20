import { NextResponse } from "next/server";

export const runtime = "nodejs";

function backendBaseUrl() {
  return process.env.TECH_API_BASE_URL || "http://127.0.0.1:8001";
}

export async function POST(
  request: Request,
  { params }: { params: { session_id: string } }
) {
  try {
    const payload = await request.json();
    const res = await fetch(`${backendBaseUrl()}/tech/sessions/${encodeURIComponent(params.session_id)}/audio`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    const raw = await res.text();
    let data: unknown = {};
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      data = { detail: raw || "Backend returned a non-JSON error." };
    }
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    return NextResponse.json({ error: (error as Error).message }, { status: 500 });
  }
}


