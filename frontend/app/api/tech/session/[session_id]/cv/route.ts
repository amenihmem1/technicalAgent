import { backendBaseUrl } from "@/lib/techBackend";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(
  request: Request,
  { params }: { params: { session_id: string } }
) {
  try {
    const form = await request.formData();
    const file = form.get("file");
    if (!(file instanceof File)) {
      return NextResponse.json({ error: "Field 'file' is required." }, { status: 400 });
    }

    const forward = new FormData();
    forward.append("file", file, file.name);

    const backendUrl = `${backendBaseUrl()}/tech/sessions/${encodeURIComponent(params.session_id)}/cv`;
    console.log("[api/tech/session/[id]/cv] Uploading to:", backendUrl);

    const res = await fetch(backendUrl, {
      method: "POST",
      body: forward,
    });

    console.log("[api/tech/session/[id]/cv] Backend status:", res.status);

    if (!res.ok) {
      const errorText = await res.text();
      console.error("[api/tech/session/[id]/cv] Backend error response:", errorText);
      return NextResponse.json(
        { error: `Backend returned ${res.status}: ${errorText}` },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data, { status: 200 });
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    console.error("[api/tech/session/[id]/cv] Exception:", errorMsg, error);
    return NextResponse.json({ error: errorMsg }, { status: 500 });
  }
}
