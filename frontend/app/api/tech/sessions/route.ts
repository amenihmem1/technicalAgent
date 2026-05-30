import { backendBaseUrl } from "@/lib/techBackend";
export const runtime = "nodejs";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const limit = searchParams.get("limit") || "60";

  try {
    const backendUrl = `${backendBaseUrl()}/tech/sessions?limit=${encodeURIComponent(limit)}`;
    console.log("[api/tech/sessions] Fetching from:", backendUrl);

    const res = await fetch(backendUrl, {
      method: "GET",
      cache: "no-store",
    });

    console.log("[api/tech/sessions] Backend status:", res.status);
    console.log("[api/tech/sessions] Backend headers:", Object.fromEntries(res.headers.entries()));

    if (!res.ok) {
      const errorText = await res.text();
      console.error("[api/tech/sessions] Backend error response:", errorText);
      return Response.json(
        { error: `Backend returned ${res.status}: ${errorText}` },
        { status: res.status }
      );
    }

    const raw = await res.text();
    console.log("[api/tech/sessions] Response length:", raw.length);

    // Validate JSON
    try {
      JSON.parse(raw);
    } catch (jsonError) {
      console.error("[api/tech/sessions] Invalid JSON from backend:", jsonError);
      return Response.json(
        { error: "Invalid JSON from backend" },
        { status: 502 }
      );
    }

    return new Response(raw, {
      status: 200,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    console.error("[api/tech/sessions] Exception:", errorMsg, error);
    return Response.json({ error: errorMsg }, { status: 500 });
  }
}
