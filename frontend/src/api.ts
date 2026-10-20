export type Calendar = {
  id: string;
  name: string;
  timezone: string;
  provider: string;
  version: number;
  writable: boolean;
};
export type CalendarEvent = {
  id: string;
  calendar_id: string;
  title: string;
  start: string;
  end: string;
  timezone: string;
  location: string;
  duration_is_estimate: boolean;
  version: number;
  recurring: boolean;
  all_day: boolean;
};
export type Proposal = {
  id: string;
  operation: string;
  payload: Record<string, unknown>;
  before: CalendarEvent | Calendar | null;
  status: string;
  error?: string;
  result: { conflicts?: CalendarEvent[] } | null;
};
export type Job = {
  id: string;
  status: string;
  error: string | null;
  result: {
    text?: string;
    transcript?: string;
    conversation_id?: string;
  } | null;
};

export async function request<T>(
  token: string,
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const form = data instanceof FormData;
  const response = await fetch("/api" + path, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(!form && data !== undefined
        ? { "Content-Type": "application/json" }
        : {}),
    },
    body: data === undefined ? undefined : form ? data : JSON.stringify(data),
  });
  const body = await response.json();
  if (!response.ok) {
    const detail =
      body.message ||
      (Array.isArray(body.detail)
        ? body.detail.map((d: { msg: string }) => d.msg).join("; ")
        : body.detail);
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return body;
}
