import type { NextRequest } from "next/server";
import {
  CopilotRuntime,
  createCopilotRuntimeHandler,
} from "@copilotkit/runtime/v2";
import { HttpAgent } from "@ag-ui/client";

const agentUrl = process.env.ADK_AGENT_URL || "http://localhost:8000";

const runtime = new CopilotRuntime({
  agents: {
    expense_approval_agent: new HttpAgent({
      url: agentUrl,
    }),
  },
  // Reenvía únicamente el header Authorization hacia el servidor FastAPI AG-UI.
  forwardHeaders: {
    allow: ["authorization"],
  },
});

const handler = createCopilotRuntimeHandler({
  runtime,
  basePath: "/api/copilotkit",
  hooks: {
    // Valida que exista un Bearer token antes de tocar el agente ADK.
    // Cuando conectes Clerk / Auth0 / Firebase / Auth.js, verifica aquí el JWT real.
    onRequest: ({ request }) => {
      const authHeader = request.headers.get("authorization");
      if (!authHeader?.startsWith("Bearer ") || !authHeader.slice(7).trim()) {
        throw new Response(
          JSON.stringify({
            error: "unauthorized",
            message: "Falta el header Authorization: Bearer <token>.",
          }),
          {
            status: 401,
            headers: { "content-type": "application/json" },
          },
        );
      }
    },
  },
});

export const GET = (req: NextRequest) => handler(req);
export const POST = (req: NextRequest) => handler(req);
export const PATCH = (req: NextRequest) => handler(req);
export const DELETE = (req: NextRequest) => handler(req);
