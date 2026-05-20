import { NextResponse } from "next/server";
import { getAgentState, startAgent } from "../../../../lib/agentProcess";

export const runtime = "nodejs";

export async function POST() {
  try {
    const result = startAgent();
    return NextResponse.json({
      ok: true,
      ...result,
      state: getAgentState()
    });
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: (error as Error).message },
      { status: 500 }
    );
  }
}
