import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const base = process.env.OCR_API_URL || "http://127.0.0.1:8000";
  const target = new URL("/api/" + path.map(encodeURIComponent).join("/") + request.nextUrl.search, base);
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  try {
    const response = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "GET" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      signal: AbortSignal.timeout(120_000),
    });
    return new NextResponse(response.body, { status: response.status, headers: { "content-type": response.headers.get("content-type") || "application/json", "cache-control": "no-store" } });
  } catch {
    return NextResponse.json({ detail: "เชื่อมต่อบริการ OCR ไม่สำเร็จ" }, { status: 502 });
  }
}

export const GET = proxy;
export const POST = proxy;
