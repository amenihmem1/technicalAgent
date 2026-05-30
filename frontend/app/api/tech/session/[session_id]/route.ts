import { backendBaseUrl } from "@/lib/techBackend";
export const runtime = "nodejs";

type RouteParams = {
  params: Promise<{ session_id: string }>;
};

export async function GET(_request: Request, { params }: RouteParams) {
  const { session_id } = await params;
  const requestUrl = new URL(_request.url);
  const includeInsights = requestUrl.searchParams.get("include_insights");
  const language = requestUrl.searchParams.get("language");
  const queryParams = new URLSearchParams();
  if (includeInsights) queryParams.set("include_insights", includeInsights);
  if (language) queryParams.set("language", language);
  const querySuffix = queryParams.toString() ? `?${queryParams.toString()}` : "";

  try {
    const res = await fetch(`${backendBaseUrl()}/tech/sessions/${encodeURIComponent(session_id)}${querySuffix}`, {
      method: "GET",
      cache: "no-store",
    });
    const raw = await res.text();
    return new Response(raw, {
      status: res.status,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return Response.json({ error: (error as Error).message }, { status: 500 });
  }
}

export async function PATCH(request: Request, { params }: RouteParams) {
  const { session_id } = await params;

  try {
    const payload = await request.json();
    const res = await fetch(`${backendBaseUrl()}/tech/sessions/${encodeURIComponent(session_id)}/meta`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const raw = await res.text();
    return new Response(raw, {
      status: res.status,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return Response.json({ error: (error as Error).message }, { status: 500 });
  }
}

export async function DELETE(_request: Request, { params }: RouteParams) {
  const { session_id } = await params;

  try {
    const res = await fetch(`${backendBaseUrl()}/tech/sessions/${encodeURIComponent(session_id)}`, {
      method: "DELETE",
    });
    const raw = await res.text();
    return new Response(raw, {
      status: res.status,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return Response.json({ error: (error as Error).message }, { status: 500 });
  }
}
