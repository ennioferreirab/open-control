import { NextRequest, NextResponse } from "next/server";
import { createHash } from "crypto";

const TOKEN_COOKIE_NAME = "mc_session";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 7; // 7 days

function hashToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

export async function POST(request: NextRequest) {
  const { token } = await request.json();
  const expectedToken = process.env.MC_ACCESS_TOKEN;

  if (!expectedToken) {
    return NextResponse.json({ error: "Auth not configured" }, { status: 500 });
  }

  if (token !== expectedToken) {
    return NextResponse.json({ error: "Invalid access token" }, { status: 401 });
  }

  const sessionValue = hashToken(expectedToken);
  const response = NextResponse.json({ success: true });
  response.cookies.set(TOKEN_COOKIE_NAME, sessionValue, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: COOKIE_MAX_AGE,
  });

  return response;
}
