"use client";

import { useState } from "react";
import { createSession, detectTables } from "../lib/api";
import { RunHistory } from "../components/RunHistory";

export default function HomePage() {
  const [sessionId, setSessionId] = useState<string>("");
  const [detectResult, setDetectResult] = useState<any>(null);
  const [error, setError] = useState<string>("");

  async function handleCreateSession() {
    setError("");
    try {
      const id = await createSession();
      setSessionId(id);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleDetect() {
    if (!sessionId) return;
    setError("");
    try {
      const data = await detectTables(sessionId);
      setDetectResult(data);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <main>
      <h1>LA Review Agent</h1>
      <p>Workflow: create session → upload files via API → detect tables → confirm mapping → analyze.</p>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button onClick={handleCreateSession}>Create Session</button>
        <button onClick={handleDetect} disabled={!sessionId}>Run Detection</button>
      </div>
      <p>Session ID: {sessionId || "(not created)"}</p>
      {error ? <p style={{ color: "red" }}>{error}</p> : null}
      {detectResult ? (
        <section>
          <h2>Detection Result</h2>
          <pre>{JSON.stringify(detectResult, null, 2)}</pre>
          <RunHistory runs={detectResult?.run_id ? [detectResult.run_id] : []} />
        </section>
      ) : null}
    </main>
  );
}
