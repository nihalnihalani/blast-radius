"use client";
export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <main className="cockpit">
      <div className="error-banner" style={{ margin: 20, borderRadius: 8 }}>
        ⚠️ Something broke: {error.message}
        <button className="btn" style={{ marginLeft: 12 }} onClick={reset}>Retry</button>
      </div>
    </main>
  );
}
