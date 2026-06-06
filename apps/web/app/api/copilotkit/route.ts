import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { HttpAgent } from "@ag-ui/client";
import { NextRequest } from "next/server";

// The Python LangGraph agent (infra_orchestrator) is served as a raw AG-UI endpoint at /agent
// and registered directly here via @ag-ui/client HttpAgent. This is the reliable agent
// registration path -- the copilotkit remote-endpoint discovery left the agent unroutable
// ("No default agent provided"). The agent does all the work, so ExperimentalEmptyAdapter
// means NO OpenAI key is required.
const AGENT_NAME = process.env.NEXT_PUBLIC_AGENT_NAME ?? "infra_orchestrator";
const AGENT_URL = process.env.AGENT_URL ?? "http://localhost:8000/agent";

const serviceAdapter = new ExperimentalEmptyAdapter();

const runtime = new CopilotRuntime({
  agents: {
    [AGENT_NAME]: new HttpAgent({ url: AGENT_URL }),
  },
});

export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter,
    endpoint: "/api/copilotkit",
  });
  return handleRequest(req);
};
