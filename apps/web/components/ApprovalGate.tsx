"use client";
import { useLangGraphInterrupt } from "@copilotkit/react-core";

// The graph-enforced human gate. Pairs with the Python LangGraph interrupt() call.
// v2 migration: import { useInterrupt } from "@copilotkit/react-core/v2" -> same render({event, resolve}).
// NOTE: useHumanInTheLoop is tool-based and will NOT receive a graph interrupt -- do not use it here.
export function ApprovalGate() {
  useLangGraphInterrupt({
    render: ({ event, resolve }) => {
      const node = event?.value?.node ?? "this step";
      const plan = event?.value?.plan ?? {};
      return (
        <div className="approval">
          <div className="approval__title">⚠️ Destructive step needs approval</div>
          <div className="approval__body">
            <b>{plan.label ?? node}</b> will modify production. Approve?
          </div>
          <div className="approval__actions">
            <button className="btn btn--approve" onClick={() => resolve({ approved: true })}>Approve</button>
            <button className="btn btn--reject" onClick={() => resolve({ approved: false })}>Reject</button>
          </div>
        </div>
      );
    },
  });
  return null;
}
