"use client";

import { useEffect, useMemo, useState } from "react";
import {
  artifactUrl,
  confirmMapping,
  createSession,
  detectTables,
  getJob,
  listRuns,
  startAnalysis,
  uploadFiles
} from "../lib/api";
import { RunHistory } from "../components/RunHistory";
import type { CandidateTable, ConfirmedMapping, DetectResponse, JobState } from "../lib/types";

function emptyMapping(): ConfirmedMapping {
  return {
    system_access_table_id: "",
    system_access_id_column: "",
    hr_active_table_id: "",
    hr_active_id_column: "",
    hr_departure_table_id: "",
    hr_departure_id_column: ""
  };
}

export default function HomePage() {
  const [sessionId, setSessionId] = useState<string>("");
  const [files, setFiles] = useState<File[]>([]);
  const [candidates, setCandidates] = useState<CandidateTable[]>([]);
  const [detectResult, setDetectResult] = useState<DetectResponse | null>(null);
  const [mapping, setMapping] = useState<ConfirmedMapping>(emptyMapping());
  const [duplicatePolicy, setDuplicatePolicy] = useState<"exact" | "normalized" | "substring">("normalized");
  const [job, setJob] = useState<JobState | null>(null);
  const [runs, setRuns] = useState<string[]>([]);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  const tableOptions = useMemo(() => candidates.map((c) => c.table_id), [candidates]);
  const tableColumns = useMemo(() => {
    const index = new Map<string, string[]>();
    candidates.forEach((candidate) => index.set(candidate.table_id, candidate.columns));
    return index;
  }, [candidates]);

  useEffect(() => {
    if (!job || (job.status !== "pending" && job.status !== "running") || !sessionId) return;
    const timer = setInterval(async () => {
      try {
        const latest = await getJob(sessionId, job.job_id);
        setJob(latest);
      } catch (e) {
        setError((e as Error).message);
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [job, sessionId]);

  async function refreshRuns() {
    if (!sessionId) return;
    const allRuns = await listRuns(sessionId);
    setRuns(allRuns);
  }

  async function handleCreateSession() {
    setError("");
    setBusy(true);
    try {
      const id = await createSession();
      setSessionId(id);
      setCandidates([]);
      setDetectResult(null);
      setMapping(emptyMapping());
      setJob(null);
      setRuns([]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload() {
    if (!sessionId || files.length === 0) return;
    setError("");
    setBusy(true);
    try {
      const uploaded = await uploadFiles(sessionId, files);
      setCandidates(uploaded);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleDetect() {
    if (!sessionId || candidates.length === 0) return;
    setError("");
    setBusy(true);
    try {
      const data = await detectTables(sessionId);
      setDetectResult(data);
      if (data.suggested_mapping) setMapping(data.suggested_mapping);
      await refreshRuns();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    if (!sessionId) return;
    setError("");
    setBusy(true);
    try {
      await confirmMapping(sessionId, mapping);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleAnalyze() {
    if (!sessionId) return;
    setError("");
    setBusy(true);
    try {
      const started = await startAnalysis(sessionId, mapping, duplicatePolicy);
      const initialJob = await getJob(sessionId, started.job_id);
      setJob(initialJob);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function updateMapping<K extends keyof ConfirmedMapping>(key: K, value: ConfirmedMapping[K]) {
    setMapping((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <main>
      <h1>LA Review Agent</h1>
      <p>Workflow: create session → upload files → detect tables → confirm mapping → analyze.</p>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button onClick={handleCreateSession} disabled={busy}>
          Create Session
        </button>
        <button onClick={refreshRuns} disabled={!sessionId || busy}>
          Refresh Runs
        </button>
      </div>
      <p>Session ID: {sessionId || "(not created)"}</p>
      <section style={{ marginBottom: 16 }}>
        <h2>1) Upload Files</h2>
        <input
          type="file"
          multiple
          accept=".csv,.xlsx"
          onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
        />
        <button onClick={handleUpload} disabled={!sessionId || files.length === 0 || busy} style={{ marginLeft: 8 }}>
          Upload
        </button>
        {candidates.length > 0 ? (
          <ul>
            {candidates.map((candidate) => (
              <li key={candidate.table_id}>
                {candidate.table_id} ({candidate.row_count} rows) — columns: {candidate.columns.join(", ")}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section style={{ marginBottom: 16 }}>
        <h2>2) Detect Tables</h2>
        <button onClick={handleDetect} disabled={!sessionId || candidates.length === 0 || busy}>
          Run Detection
        </button>
        {detectResult ? (
          <>
            <p>Status: {detectResult.status}</p>
            <ul>
              {detectResult.classifications.map((item) => (
                <li key={item.table_id}>
                  {item.table_id} → {item.table_type} ({item.confidence_level} / {item.confidence.toFixed(2)})
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </section>

      <section style={{ marginBottom: 16 }}>
        <h2>3) Confirm Mapping</h2>
        <div style={{ display: "grid", gap: 8, maxWidth: 720 }}>
          <label>
            System access table
            <select
              value={mapping.system_access_table_id}
              onChange={(e) => updateMapping("system_access_table_id", e.target.value)}
            >
              <option value="">Select table</option>
              {tableOptions.map((tableId) => (
                <option key={tableId} value={tableId}>
                  {tableId}
                </option>
              ))}
            </select>
          </label>
          <label>
            System access ID column
            <select
              value={mapping.system_access_id_column}
              onChange={(e) => updateMapping("system_access_id_column", e.target.value)}
            >
              <option value="">Select column</option>
              {(tableColumns.get(mapping.system_access_table_id) ?? []).map((column) => (
                <option key={column} value={column}>
                  {column}
                </option>
              ))}
            </select>
          </label>
          <label>
            Active HR table
            <select value={mapping.hr_active_table_id} onChange={(e) => updateMapping("hr_active_table_id", e.target.value)}>
              <option value="">Select table</option>
              {tableOptions.map((tableId) => (
                <option key={tableId} value={tableId}>
                  {tableId}
                </option>
              ))}
            </select>
          </label>
          <label>
            Active HR ID column
            <select value={mapping.hr_active_id_column} onChange={(e) => updateMapping("hr_active_id_column", e.target.value)}>
              <option value="">Select column</option>
              {(tableColumns.get(mapping.hr_active_table_id) ?? []).map((column) => (
                <option key={column} value={column}>
                  {column}
                </option>
              ))}
            </select>
          </label>
          <label>
            Departure HR table
            <select
              value={mapping.hr_departure_table_id}
              onChange={(e) => updateMapping("hr_departure_table_id", e.target.value)}
            >
              <option value="">Select table</option>
              {tableOptions.map((tableId) => (
                <option key={tableId} value={tableId}>
                  {tableId}
                </option>
              ))}
            </select>
          </label>
          <label>
            Departure HR ID column
            <select
              value={mapping.hr_departure_id_column}
              onChange={(e) => updateMapping("hr_departure_id_column", e.target.value)}
            >
              <option value="">Select column</option>
              {(tableColumns.get(mapping.hr_departure_table_id) ?? []).map((column) => (
                <option key={column} value={column}>
                  {column}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button onClick={handleConfirm} disabled={!sessionId || busy} style={{ marginTop: 8 }}>
          Confirm Mapping
        </button>
      </section>

      <section style={{ marginBottom: 16 }}>
        <h2>4) Analyze</h2>
        <label>
          Duplicate policy{" "}
          <select value={duplicatePolicy} onChange={(e) => setDuplicatePolicy(e.target.value as typeof duplicatePolicy)}>
            <option value="exact">exact</option>
            <option value="normalized">normalized</option>
            <option value="substring">substring</option>
          </select>
        </label>
        <button onClick={handleAnalyze} disabled={!sessionId || busy} style={{ marginLeft: 8 }}>
          Start Analysis
        </button>
        {job ? (
          <div>
            <p>
              Job {job.job_id}: {job.status} ({job.detail})
            </p>
            {job.result ? (
              <>
                <p>
                  Missing in HR: {job.result.missing_in_hr_count}, Found in departure: {job.result.found_in_departure_count},
                  Duplicate groups: {job.result.duplicate_group_count}
                </p>
                <p>
                  <a href={artifactUrl(sessionId, job.job_id, "missing_in_hr")} target="_blank" rel="noreferrer">
                    Download missing_in_hr.csv
                  </a>{" "}
                  |{" "}
                  <a href={artifactUrl(sessionId, job.job_id, "found_in_departure")} target="_blank" rel="noreferrer">
                    Download found_in_departure.csv
                  </a>
                </p>
                <details>
                  <summary>Preview data</summary>
                  <pre>{JSON.stringify(job.result, null, 2)}</pre>
                </details>
              </>
            ) : null}
          </div>
        ) : null}
      </section>

      <RunHistory runs={runs} />
      {error ? <p style={{ color: "red" }}>{error}</p> : null}
    </main>
  );
}
