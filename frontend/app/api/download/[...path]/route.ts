import { NextRequest } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET(
  req: NextRequest,
  { params }: { params: { path: string[] } },
) {
  const segments = params.path;
  if (segments.length < 2) {
    return new Response("Invalid download path", { status: 400 });
  }
  const job_id = segments[0];
  const artifact = segments.slice(1).join("/");

  // Validate job_id is a hex UUID (with or without hyphens)
  if (!/^[0-9a-f]{32}$/i.test(job_id) && !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(job_id)) {
    return new Response("Invalid job ID", { status: 400 });
  }
  // Reject path traversal in artifact
  if (artifact.includes("..") || artifact.startsWith("/") || artifact.includes("\\")) {
    return new Response("Invalid artifact path", { status: 400 });
  }

  const url = `${BACKEND}/download/${job_id}/${artifact}`;

  const res = await fetch(url);
  if (!res.ok) {
    return new Response(await res.text(), { status: res.status });
  }

  const headers = new Headers(res.headers);
  return new Response(res.body, { headers });
}
