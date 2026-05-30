import { backendBaseUrl } from "@/lib/techBackend";
export const runtime = "nodejs";

export async function GET(
  request: Request,
  { params }: { params: { session_id: string } }
) {
  const requestUrl = new URL(request.url);
  const language = requestUrl.searchParams.get("language");
  const querySuffix = language ? `?language=${encodeURIComponent(language)}` : "";
  const res = await fetch(`${backendBaseUrl()}/tech/sessions/${encodeURIComponent(params.session_id)}/insights-report.pdf${querySuffix}`, {
    method: "GET",
  });
  if (!res.ok) {
    const body = await res.text();
    return new Response(body || "PDF unavailable", { status: res.status });
  }
  const buf = await res.arrayBuffer();
  return new Response(buf, {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="${params.session_id}-insights-visuels-vocaux.pdf"`,
    },
  });
}
