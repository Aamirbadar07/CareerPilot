"use client";

import { useCallback, useEffect, useState } from "react";

export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

/** JSON request to the backend. Throws ApiError with the server's own explanation. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isForm = init.body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(API + path, {
      ...init,
      headers: isForm || !init.body ? init.headers : { "Content-Type": "application/json", ...init.headers },
    });
  } catch {
    throw new ApiError(0, "The server is not reachable. Check that the backend is running.");
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : `Request failed (${response.status}).`;
    throw new ApiError(response.status, detail);
  }
  return body as T;
}

/** Load `path` and keep it in state. Pass null to wait (for example until an id is known). */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (path === null) return;
    let live = true;
    setLoading(true);
    api<T>(path)
      .then((d) => live && (setData(d), setError(null)))
      .catch((e: ApiError) => live && setError(e))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [path, version]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { data, error, loading, reload, setData };
}

// ---- which profile this browser is looking at --------------------------------------------

const KEY = "careerpilot.profile";
export const SAMPLE = "sample";
const listeners = new Set<() => void>();

export function setProfileId(id: string) {
  if (id === SAMPLE) localStorage.removeItem(KEY);
  else localStorage.setItem(KEY, id);
  listeners.forEach((notify) => notify());
}

/** The visitor's own profile id, or "sample". Null until the browser has been asked. */
export function useProfileId(): string | null {
  const [id, setId] = useState<string | null>(null);
  useEffect(() => {
    const read = () => setId(localStorage.getItem(KEY) ?? SAMPLE);
    read();
    listeners.add(read);
    return () => void listeners.delete(read);
  }, []);
  return id;
}
