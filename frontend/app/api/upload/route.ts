import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const backendForm = new FormData();

  for (const [key, value] of form.entries()) {
    if (value instanceof File) {
      backendForm.append(key, value, value.name);
    }
  }

  const res = await fetch(`${BACKEND}/upload`, {
    method: "POST",
    body: backendForm,
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
