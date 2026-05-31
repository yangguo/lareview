import { NextRequest } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(
  _req: NextRequest,
  { params }: { params: { task_id: string } },
) {
  const task_id = params.task_id;
  if (!/^[0-9a-f]{32}$/i.test(task_id)) {
    return new Response(JSON.stringify({ status: "error", error: "Invalid task ID" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const res = await fetch(`${BACKEND}/v1/chat/completions/result/${task_id}`, {
    cache: "no-store",
  });
  const data = await res.json();
  return new Response(JSON.stringify(data), {
    status: res.status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    },
  });
}
