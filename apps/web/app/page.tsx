"use client";
import { CopilotSidebar } from "@copilotkit/react-ui";
import { Cockpit } from "../components/Cockpit";

export default function Home() {
  return (
    <>
      <Cockpit />
      {/* CopilotKit operator console — the AG-UI agent is also wired here (see app/providers.tsx). */}
      <CopilotSidebar
        defaultOpen={false}
        clickOutsideToClose
        labels={{ title: "Operator console", initial: "Ask me to make an infra change, or use the buttons above." }}
        instructions="You are the orchestrator for an infra-change cockpit that decomposes requests into a blast-radius DAG and executes under a circuit breaker."
      />
    </>
  );
}
