import { backendBaseUrl } from "@/lib/techBackend";
export const runtime = "nodejs";

type RouteParams = {
  params: Promise<{ session_id: string }>;
};

export async function POST(request: Request, { params }: RouteParams) {
  const { session_id } = await params;

  try {
    const body = await request.formData();
    const res = await fetch(`${backendBaseUrl()}/tech/sessions/${encodeURIComponent(session_id)}/vision`, {
      method: "POST",
      body,
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
