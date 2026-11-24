import { NextResponse, type NextRequest } from "next/server";

const agentUrl = process.env.ADK_AGENT_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const res = await fetch(`${agentUrl}/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { detail: "No se pudo conectar con el servidor de autenticación (puerto 8000)." },
      { status: 502 },
    );
  }
}
