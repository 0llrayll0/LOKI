export const BASE = (import.meta.env.VITE_API_BASE_URL as string) || "http://localhost:8100";

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init);
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    let code: string | undefined;
    try {
      const body = await res.json();
      if (body?.error?.message) message = body.error.message;
      if (body?.detail) message = String(body.detail);
      if (body?.error?.code) code = body.error.code;
    } catch {
      const text = await res.text().catch(() => "");
      if (text) message = `${res.status} ${text}`;
    }
    throw new ApiError(res.status, message, code);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}