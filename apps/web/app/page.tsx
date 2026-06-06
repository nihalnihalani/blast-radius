"use client";
import { CopilotSidebar } from "@copilotkit/react-ui";
import { useCopilotChatSuggestions } from "@copilotkit/react-core";
import { BlastRadiusDAG } from "../components/BlastRadiusDAG";
import { ApprovalGate } from "../components/ApprovalGate";
import { Controls } from "../components/Controls";

export default function Home() {
  // One-click demo prompts so we never type on stage.
  useCopilotChatSuggestions({
    instructions: "Suggest: 'Scale the payments service' and 'Rotate the DB credentials'.",
  });

  return (
    <main className="cockpit">
      <header className="cockpit__header">
        <h1>💥 BLAST-RADIUS</h1>
        <span className="cockpit__sub">multi-agent infra-change cockpit</span>
        <Controls />
      </header>

      <BlastRadiusDAG />

      {/* Registers the graph-interrupt approval modal + chat surface. */}
      <ApprovalGate />
      <CopilotSidebar
        defaultOpen
        labels={{ title: "Operator console", initial: "Ask me to make an infra change." }}
        instructions="You are the orchestrator for an infra-change cockpit. Decompose requests into a blast-radius DAG and execute under a circuit breaker."
      />
    </main>
  );
}
