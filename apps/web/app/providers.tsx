"use client";
import { ReactNode, useMemo } from "react";
import { CopilotKit } from "@copilotkit/react-core";
import { HttpAgent } from "@ag-ui/client";

const AGENT = process.env.NEXT_PUBLIC_AGENT_NAME ?? "infra_orchestrator";
// The browser talks to the Python AG-UI endpoint directly (CORS is enabled on the backend).
const AGENT_HTTP_URL = process.env.NEXT_PUBLIC_AGENT_HTTP_URL ?? "http://localhost:8000/agent";

export function Providers({ children }: { children: ReactNode }) {
  // Register the AG-UI agent client-side so useCoAgent / useLangGraphInterrupt resolve it.
  // (Server-side remoteEndpoints/agents discovery did not surface the agent to the runtime /info.)
  const agents = useMemo(() => ({ [AGENT]: new HttpAgent({ url: AGENT_HTTP_URL }) }), []);

  return (
    <CopilotKit
      runtimeUrl="/api/copilotkit"
      agent={AGENT}
      agents__unsafe_dev_only={agents}
      showDevConsole={false}
    >
      {children}
    </CopilotKit>
  );
}
