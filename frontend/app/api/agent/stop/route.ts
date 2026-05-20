import { NextResponse } from "next/server";
import { getAgentState, stopAgent } from "../../../../lib/agentProcess";

export const runtime = "nodejs";

export async function POST() {
  try {
    const result = stopAgent();
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
