import type { ReactNode } from "react";
import { CopilotKit } from "@copilotkit/react-core";
import "@copilotkit/react-ui/styles.css";
import "./globals.css";

export const metadata = { title: "BLAST-RADIUS", description: "Multi-agent infra-change cockpit" };

const AGENT = process.env.NEXT_PUBLIC_AGENT_NAME ?? "infra_orchestrator";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        {/* agent= binds the chat + shared state to our LangGraph agent.
            enableInspector/showDevConsole help debug the AG-UI event stream live. */}
        <CopilotKit runtimeUrl="/api/copilotkit" agent={AGENT} showDevConsole>
          {children}
        </CopilotKit>
      </body>
    </html>
  );
}
