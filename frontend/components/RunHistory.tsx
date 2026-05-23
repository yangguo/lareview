"use client";

export function RunHistory({ runs }: { runs: string[] }) {
  return (
    <section>
      <h3>Run History</h3>
      {runs.length === 0 ? <p>No runs yet.</p> : <ul>{runs.map((run) => <li key={run}>{run}</li>)}</ul>}
    </section>
  );
}
