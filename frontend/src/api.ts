let csrfToken = "";
let pendingCsrf: Promise<string> | null = null;
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function csrf(): Promise<string> {
  if (csrfToken) return csrfToken;
  if (!pendingCsrf)
    pendingCsrf = fetch("/api/auth/csrf", { credentials: "same-origin" })
      .then(async (r) => {
        if (!r.ok) throw new Error("Сервис временно недоступен");
        csrfToken = (await r.json()).csrf_token;
        return csrfToken;
      })
      .finally(() => {
        pendingCsrf = null;
      });
  return pendingCsrf;
}
export function errorText(data: unknown): string {
  const d = (data as { detail?: unknown })?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d))
    return "Проверьте заполненные поля. Возможно, текст слишком длинный или адрес email неверен.";
  return "Не удалось выполнить действие. Попробуйте ещё раз.";
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (options.method && !["GET", "HEAD"].includes(options.method))
    headers.set("X-CSRF-Token", await csrf());
  let response: Response;
  try {
    response = await fetch("/api" + path, {
      ...options,
      headers,
      credentials: "same-origin",
    });
  } catch {
    throw new Error("Нет связи с сервером. Проверьте подключение.");
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    if (response.status === 403) csrfToken = "";
    throw new ApiError(response.status, errorText(data));
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
export const send = <T>(path: string, method: string, data?: unknown) =>
  api<T>(path, {
    method,
    ...(data !== undefined ? { body: JSON.stringify(data) } : {}),
  });
export async function uploadFile(
  id: string,
  file: File,
  progress: (n: number) => void,
  signal: AbortSignal,
) {
  const token = await csrf();
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", `/api/videos/${id}/file`);
    xhr.setRequestHeader("X-CSRF-Token", token);
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) progress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      cleanup();
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else {
        let message = "Не удалось загрузить файл";
        try {
          message = errorText(JSON.parse(xhr.responseText));
        } catch {}
        reject(new Error(message));
      }
    };
    xhr.onerror = () => {
      cleanup();
      reject(new Error("Загрузка прервана. Проверьте подключение."));
    };
    xhr.onabort = () => {
      cleanup();
      reject(new Error("Загрузка отменена"));
    };
    const abort = () => xhr.abort();
    const cleanup = () => signal.removeEventListener("abort", abort);
    signal.addEventListener("abort", abort, { once: true });
    if (signal.aborted) {
      reject(new Error("Загрузка отменена"));
      return;
    }
    xhr.send(file);
  });
}
