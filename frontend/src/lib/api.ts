export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return String(body.detail[0].msg);
  } catch {}
  return `Request failed (${res.status})`;
}

/** All calls go to /api/* (proxied to the backend). The custom header is the CSRF guard. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Requested-With", "fetch");
  if (typeof init.body === "string" && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const res = await fetch(`/api${path}`, { ...init, headers, credentials: "same-origin" });
  if (!res.ok) throw new ApiError(res.status, await readError(res));
  return res.json() as Promise<T>;
}

/** fetch() cannot report upload progress, so uploads use XMLHttpRequest. */
export function uploadSubmission(
  title: string,
  file: File,
  onProgress: (pct: number) => void,
): Promise<{ id: string }> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("title", title);
    form.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/submissions");
    xhr.setRequestHeader("X-Requested-With", "fetch");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => {
      let body: any = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {}
      if (xhr.status >= 200 && xhr.status < 300) return resolve(body);
      const detail = typeof body?.detail === "string" ? body.detail : body?.detail?.[0]?.msg;
      reject(new ApiError(xhr.status, detail || `Upload failed (${xhr.status})`));
    };
    xhr.onerror = () => reject(new ApiError(0, "Network error. Check your connection and try again."));
    xhr.send(form);
  });
}
