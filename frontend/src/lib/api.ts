/** Minimal typed fetch wrapper for the app's API (same origin; via the Vite proxy locally). */
import { APP_NAME } from "./brand";

/** Fired when the server says the sign-in is missing or expired (the app then shows the login screen). */
export const UNAUTHORIZED_EVENT = "uc:unauthorized";

function notifyUnauthorized(path: string) {
  if (!path.startsWith("/api/auth/")) window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function extractMessage(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length) {
      return detail
        .map((d: { loc?: (string | number)[]; msg?: string }) => {
          const field = d.loc?.filter((p) => p !== "body").join(".");
          return field ? `${field}: ${d.msg}` : d.msg;
        })
        .join("; ");
    }
  }
  if (status === 0) return `Can't reach the ${APP_NAME} server. Check your connection.`;
  if (status >= 500) return "The server had a problem. Please try again.";
  return `Request failed (${status})`;
}

async function request<T>(method: string, path: string, body?: unknown, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      ...init,
    });
  } catch {
    throw new ApiError(extractMessage(null, 0), 0);
  }
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    if (res.status === 401) notifyUnauthorized(path);
    if (res.status === 502 || res.status === 503 || res.status === 504) {
      throw new ApiError(`Can't reach the ${APP_NAME} server right now. Please try again in a moment.`, res.status);
    }
    throw new ApiError(extractMessage(data, res.status), res.status);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body ?? {}),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body ?? {}),
  del: <T>(path: string) => request<T>("DELETE", path),
};

/** Upload a file as the raw request body, reporting progress (0..1). */
export function uploadFile<T>(
  path: string,
  file: Blob,
  onProgress?: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", path);
    xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      let data: unknown = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        data = null;
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data as T);
      else {
        if (xhr.status === 401) notifyUnauthorized(path);
        reject(new ApiError(extractMessage(data, xhr.status), xhr.status));
      }
    };
    xhr.onerror = () => reject(new ApiError("Upload failed: the server could not be reached.", 0));
    xhr.onabort = () => reject(new ApiError("Upload cancelled.", 0));
    if (signal) signal.addEventListener("abort", () => xhr.abort());
    xhr.send(file);
  });
}

export function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}
