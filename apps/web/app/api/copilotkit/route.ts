import {
  CopilotRuntime,
  OpenAIAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { NextRequest } from "next/server";

// The Python LangGraph agent is a remote AG-UI endpoint. CopilotKit proxies to it.
// Verify the remote-endpoint option name against your installed @copilotkit/runtime version
// (`remoteEndpoints` is current; older builds used `remoteActions`/`copilotKitEndpoint`).
const serviceAdapter = new OpenAIAdapter({ model: process.env.OPENAI_MODEL ?? "gpt-4o" });

const runtime = new CopilotRuntime({
  remoteEndpoints: [
    { url: process.env.AGENT_URL ?? "http://localhost:8000/copilotkit" },
  ],
});

export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter,
    endpoint: "/api/copilotkit",
  });
  return handleRequest(req);
};
