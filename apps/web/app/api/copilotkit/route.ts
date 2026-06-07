import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotKitEndpoint,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { NextRequest } from "next/server";

// Official self-hosted setup: the Python LangGraph agent is exposed via copilotkit's
// CopilotKitRemoteEndpoint at /copilotkit; the Next runtime discovers + proxies it.
// The agent does all the work -> ExperimentalEmptyAdapter (no OpenAI key needed).
const runtime = new CopilotRuntime({
  remoteEndpoints: [
    copilotKitEndpoint({ url: process.env.REMOTE_ENDPOINT_URL ?? "http://localhost:8000/copilotkit" }),
  ],
});

export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter: new ExperimentalEmptyAdapter(),
    endpoint: "/api/copilotkit",
  });
  return handleRequest(req);
};
