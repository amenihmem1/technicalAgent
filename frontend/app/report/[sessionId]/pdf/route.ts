export const runtime = "nodejs";

function backendBaseUrl() {
  return process.env.TECH_API_BASE_URL || "http://127.0.0.1:8001";
}

export async function GET(
  _request: Request,
  { params }: { params: { sessionId: string } }
) {
  const res = await fetch(`${backendBaseUrl()}/tech/sessions/${encodeURIComponent(params.sessionId)}/report.pdf`, {
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
      "Content-Disposition": `inline; filename="${params.sessionId}-technical-report.pdf"`,
      "Cache-Control": "no-store",
    },
  });
}


