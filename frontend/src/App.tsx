import { useCallback, useEffect, useRef, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import luxonPlugin from "@fullcalendar/luxon3";
import { DateTime } from "luxon";
import {
  request,
  type Calendar,
  type CalendarEvent,
  type Job,
  type Proposal,
} from "./api";

type Chat = { role: "you" | "jarvis"; text: string };
type Draft = {
  supersedes?: string;
  id?: string;
  version?: number;
  title: string;
  calendar_id: string;
  start: string;
  duration: number;
  location: string;
  estimate: boolean;
};
const blank = (calendar_id = "personal"): Draft => ({
  title: "",
  calendar_id,
  start: "",
  duration: 60,
  location: "",
  estimate: false,
});

export default function App() {
  const [token, setToken] = useState(
    sessionStorage.getItem("jarvis-token") || "",
  );
  const [inputToken, setInputToken] = useState("");
  const [connected, setConnected] = useState(false);
  const [timezone, setTimezone] = useState("Asia/Singapore");
  const [calendars, setCalendars] = useState<Calendar[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [range, setRange] = useState({
    start: DateTime.now().startOf("week").toISO()!,
    end: DateTime.now().endOf("week").toISO()!,
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [chat, setChat] = useState<Chat[]>([]);
  const [text, setText] = useState("");
  const [conversation, setConversation] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [recording, setRecording] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [calendarForm, setCalendarForm] = useState(false);
  const [calendarName, setCalendarName] = useState("");
  const [editingCalendar, setEditingCalendar] = useState<Calendar | null>(null);
  const [googleConnected, setGoogleConnected] = useState(false);
  const [overlap, setOverlap] = useState<Record<string, boolean>>({});
  const recorder = useRef<MediaRecorder | null>(null);
  const recordTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const api = useCallback(
    <T,>(path: string, method = "GET", data?: unknown) =>
      request<T>(token, path, method, data),
    [token],
  );
  const refresh = useCallback(async () => {
    const [cs, es, ps] = await Promise.all([
      api<Calendar[]>("/calendars"),
      api<CalendarEvent[]>(
        `/events?start=${encodeURIComponent(range.start)}&end=${encodeURIComponent(range.end)}`,
      ),
      api<Proposal[]>("/proposals"),
    ]);
    setCalendars(cs);
    setEvents(es);
    setProposals(ps);
  }, [api, range]);

  useEffect(() => {
    if (!token) return;
    api<{ timezone: string; google_connected: boolean }>("/settings")
      .then((s) => {
        setTimezone(s.timezone);
        setGoogleConnected(s.google_connected);
        setConnected(true);
      })
      .catch((e) => {
        setError(e.message);
        setConnected(false);
      });
  }, [api, token]);

  useEffect(() => {
    if (!connected) return;
    refresh().catch((e) => setError(e.message));
    const timer = setInterval(
      () => refresh().catch((e) => setError(e.message)),
      3000,
    );
    return () => clearInterval(timer);
  }, [connected, refresh]);

  useEffect(() => {
    if (!job || ["completed", "failed"].includes(job.status)) return;
    let cancelled = false;
    const timer = setInterval(async () => {
      try {
        const updated = await api<Job>(`/jobs/${job.id}`);
        if (cancelled) return;
        setJob(updated);
        if (updated.status === "completed") {
          if (updated.result?.text)
            setChat((c) => [
              ...c,
              { role: "jarvis", text: updated.result!.text! },
            ]);
          if (updated.result?.conversation_id)
            setConversation(updated.result.conversation_id);
          await refresh();
        } else if (updated.status === "failed")
          setError(updated.error || "Processing failed");
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    }, 1000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [job?.id, job?.status, api, refresh]); // eslint-disable-line

  useEffect(
    () => () => {
      if (recordTimer.current) clearTimeout(recordTimer.current);
      if (recorder.current?.state === "recording") recorder.current.stop();
      recorder.current?.stream.getTracks().forEach((t) => t.stop());
    },
    [],
  );

  async function action(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function send() {
    if (!text.trim()) return;
    const message = text;
    setText("");
    setChat((c) => [...c, { role: "you", text: message }]);
    await action(async () =>
      setJob(
        await api<Job>("/messages", "POST", {
          text: message,
          conversation_id: conversation,
          request_id: crypto.randomUUID(),
          timezone,
          captured_at: new Date().toISOString(),
        }),
      ),
    );
  }

  async function record() {
    if (recording) {
      recorder.current?.stop();
      return;
    }
    try {
      if (!navigator.mediaDevices?.getUserMedia)
        throw new Error(
          "Recording needs HTTPS or localhost. You can type below.",
        );
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const media = new MediaRecorder(stream);
      recorder.current = media;
      const chunks: Blob[] = [];
      const captured = new Date().toISOString();
      media.ondataavailable = (e) => {
        if (e.data.size) chunks.push(e.data);
      };
      media.onstop = () => {
        if (recordTimer.current) clearTimeout(recordTimer.current);
        stream.getTracks().forEach((t) => t.stop());
        setRecording(false);
        const form = new FormData();
        form.append(
          "audio",
          new Blob(chunks, { type: media.mimeType }),
          "recording",
        );
        form.append("request_id", crypto.randomUUID());
        form.append("captured_at", captured);
        form.append("timezone", timezone);
        if (conversation) form.append("conversation_id", conversation);
        setChat((c) => [
          ...c,
          { role: "you", text: "Voice note · transcribing…" },
        ]);
        void action(async () =>
          setJob(await api<Job>("/recordings", "POST", form)),
        );
      };
      media.start();
      setRecording(true);
      recordTimer.current = setTimeout(() => {
        if (media.state === "recording") media.stop();
      }, 119000);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function saveDraft() {
    if (!draft) return;
    const start = DateTime.fromISO(draft.start, { zone: timezone });
    if (!start.isValid) {
      setError("Choose a valid start time");
      return;
    }
    const fields = {
      calendar_id: draft.calendar_id,
      title: draft.title,
      start: start.toISO(),
      duration_minutes: Number(draft.duration),
      timezone,
      location: draft.location,
      duration_is_estimate: draft.estimate,
    };
    await action(async () => {
      await api("/proposals", "POST", {
        operation: draft.id ? "event_update" : "event_create",
        payload: draft.id
          ? {
              event_id: draft.id,
              expected_version: draft.version,
              event: fields,
            }
          : fields,
      });
      if (draft.supersedes)
        await api(`/proposals/${draft.supersedes}/reject`, "POST");
      setDraft(null);
    });
  }

  const working =
    busy || !!(job && !["completed", "failed"].includes(job.status));
  const pending = proposals.filter((p) => p.status !== "rejected");

  if (!connected)
    return (
      <main className="login">
        <div className="brand">
          j<span>arvis</span>
          <i>✳</i>
        </div>
        <h1>
          A little room
          <br />
          for life.
        </h1>
        <p>
          Your calendar, with a listening ear.
          <br />
          Connect to your private workspace.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sessionStorage.setItem("jarvis-token", inputToken);
            setToken(inputToken);
          }}
        >
          <label htmlFor="token">Workspace access token</label>
          <input
            id="token"
            type="password"
            value={inputToken}
            onChange={(e) => setInputToken(e.target.value)}
            required
            autoComplete="off"
          />
          <button type="submit">
            Open my workspace <span>↗</span>
          </button>
        </form>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <small>Runs on your host. Your plans stay with you.</small>
      </main>
    );

  return (
    <div className="shell">
      <header>
        <div className="brand">
          j<span>arvis</span>
          <i>✳</i>
        </div>
        <span className="header-note">A LITTLE ROOM FOR LIFE</span>
        <button
          className="quiet"
          onClick={() => {
            sessionStorage.removeItem("jarvis-token");
            setToken("");
            setConnected(false);
          }}
        >
          Lock workspace ↗
        </button>
      </header>
      <main className="workspace">
        <div className="page-heading">
          <div>
            <div className="eyebrow">YOUR DAYS, THOUGHTFULLY ARRANGED</div>
            <h1>Make space for what matters.</h1>
            <p>Say what’s on your mind. We’ll put it on your calendar.</p>
          </div>
          <div className="zone">
            <span className="dot" />
            {timezone.replace("_", " ")}
          </div>
        </div>
        {error && (
          <div role="alert" className="error banner">
            {error}
            <button className="quiet" onClick={() => setError("")}>
              Dismiss
            </button>
          </div>
        )}
        <div className="columns">
          <aside>
            <section className="capture card">
              <div className="eyebrow">01 / CAPTURE</div>
              <h2>What’s the plan?</h2>
              <p>
                A dinner, a meeting, a little time for yourself. Start with a
                voice note.
              </p>
              <button
                className={`record ${recording ? "recording" : ""}`}
                disabled={working && !recording}
                onClick={() => void record()}
                aria-label={recording ? "Stop recording" : "Record voice note"}
              >
                {recording ? "■" : "●"}
              </button>
              <strong>
                {recording ? "Listening… tap to finish" : "Tap to record"}
              </strong>
              <small>Up to 2 minutes · English</small>
              <div className="divider">or type a note</div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void send();
                }}
              >
                <label className="sr-only" htmlFor="message">
                  Message to Jarvis
                </label>
                <textarea
                  id="message"
                  placeholder="Dinner with Sam tomorrow at 7…"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  maxLength={4000}
                  disabled={working}
                />
                <button className="send" disabled={working || !text.trim()}>
                  {" "}
                  {working ? "Working…" : "Send note"} <span>↗</span>
                </button>
              </form>
            </section>
            <section className="conversation card">
              <div className="section-head">
                <div className="eyebrow">THE CONVERSATION</div>
                <button
                  className="quiet"
                  disabled={working}
                  onClick={() => {
                    setConversation(null);
                    setChat([]);
                    setJob(null);
                  }}
                >
                  New
                </button>
              </div>
              {chat.length ? (
                chat.map((m, i) => (
                  <div className={`message ${m.role}`} key={i}>
                    <span>{m.role === "you" ? "YOU" : "JARVIS"}</span>
                    <p>{m.text}</p>
                  </div>
                ))
              ) : (
                <p className="empty">
                  Your notes and follow-up questions will appear here.
                </p>
              )}
              {job?.result?.transcript && (
                <details>
                  <summary>Review transcript</summary>
                  <p>{job.result.transcript}</p>
                  <button
                    className="quiet"
                    onClick={() =>
                      setText(
                        `Correction to my voice note: ${job.result!.transcript}`,
                      )
                    }
                  >
                    Correct in next message ↗
                  </button>
                </details>
              )}
              {job?.status === "failed" && (
                <button
                  className="quiet"
                  onClick={() =>
                    void action(async () =>
                      setJob(await api<Job>(`/jobs/${job.id}/retry`, "POST")),
                    )
                  }
                >
                  Retry processing ↗
                </button>
              )}
            </section>
            <section className="calendars card">
              <div className="section-head">
                <div className="eyebrow">YOUR CALENDARS</div>
                <button
                  className="quiet"
                  onClick={() => {
                    setCalendarForm(true);
                    setEditingCalendar(null);
                    setCalendarName("");
                  }}
                >
                  + Add
                </button>
              </div>
              {calendars.map((c) => (
                <div className="calendar-row" key={c.id}>
                  <span className="dot" />
                  <span>
                    {c.name}
                    <small>
                      {c.provider}
                      {!c.writable ? " · read only" : ""}
                    </small>
                  </span>
                  {c.provider === "local" && (
                    <button
                      className="quiet"
                      aria-label={`Edit calendar ${c.name}`}
                      onClick={() => {
                        setEditingCalendar(c);
                        setCalendarName(c.name);
                        setCalendarForm(true);
                      }}
                    >
                      ···
                    </button>
                  )}
                </div>
              ))}
              {googleConnected && (
                <button
                  className="quiet"
                  disabled={working}
                  onClick={() =>
                    void action(async () =>
                      setJob(
                        await api<Job>("/integrations/google/sync", "POST"),
                      ),
                    )
                  }
                >
                  Sync Google Calendar ↗
                </button>
              )}
            </section>
          </aside>
          <div className="schedule-column">
            <section className="schedule card">
              <div className="section-head">
                <div>
                  <div className="eyebrow">02 / YOUR SCHEDULE</div>
                  <h2>The week ahead</h2>
                </div>
                <button disabled={busy} onClick={() => setDraft(blank())}>
                  + Add event
                </button>
              </div>
              <FullCalendar
                plugins={[
                  dayGridPlugin,
                  timeGridPlugin,
                  interactionPlugin,
                  luxonPlugin,
                ]}
                initialView={
                  window.matchMedia("(max-width: 750px)").matches
                    ? "timeGridDay"
                    : "timeGridWeek"
                }
                timeZone={timezone}
                height="auto"
                nowIndicator
                allDaySlot
                headerToolbar={{
                  left: "prev,next today",
                  center: "title",
                  right: "timeGridWeek,timeGridDay",
                }}
                slotMinTime="00:00:00"
                slotMaxTime="24:00:00"
                scrollTime="08:00:00"
                selectable
                editable
                datesSet={(d) => setRange({ start: d.startStr, end: d.endStr })}
                events={events.map((e) => ({
                  id: e.id,
                  title: e.title,
                  start: e.start,
                  end: e.end,
                  allDay: e.all_day,
                  editable:
                    !e.recurring &&
                    !e.all_day &&
                    !!calendars.find((c) => c.id === e.calendar_id)?.writable,
                  backgroundColor: "#52715e",
                  borderColor: "#52715e",
                }))}
                select={(selection) =>
                  setDraft({
                    ...blank(),
                    start: DateTime.fromJSDate(selection.start, {
                      zone: timezone,
                    }).toFormat("yyyy-MM-dd'T'HH:mm"),
                    duration: Math.max(
                      15,
                      (selection.end.getTime() - selection.start.getTime()) /
                        60000,
                    ),
                  })
                }
                eventClick={({ event }) => {
                  const e = events.find((e) => e.id === event.id)!;
                  if (e.all_day || e.recurring) {
                    setError(
                      "Recurring and all-day events are view-only in V1",
                    );
                    return;
                  }
                  setDraft({
                    id: e.id,
                    version: e.version,
                    title: e.title,
                    calendar_id: e.calendar_id,
                    start: DateTime.fromISO(e.start)
                      .setZone(timezone)
                      .toFormat("yyyy-MM-dd'T'HH:mm"),
                    duration: Math.round(
                      (Date.parse(e.end) - Date.parse(e.start)) / 60000,
                    ),
                    location: e.location,
                    estimate: e.duration_is_estimate,
                  });
                }}
                eventDrop={(info) => {
                  const e = events.find((e) => e.id === info.event.id)!;
                  const moved = info.event.start!;
                  info.revert();
                  setDraft({
                    id: e.id,
                    version: e.version,
                    title: e.title,
                    calendar_id: e.calendar_id,
                    start: DateTime.fromJSDate(moved, {
                      zone: timezone,
                    }).toFormat("yyyy-MM-dd'T'HH:mm"),
                    duration: Math.round(
                      (Date.parse(e.end) - Date.parse(e.start)) / 60000,
                    ),
                    location: e.location,
                    estimate: e.duration_is_estimate,
                  });
                }}
                eventDurationEditable={false}
              />
            </section>
            <section className="review card">
              <div className="section-head">
                <div>
                  <div className="eyebrow">03 / REVIEW</div>
                  <h2>A moment before it’s on the calendar.</h2>
                </div>
                <span className="badge">
                  {proposals.filter((p) => p.status === "pending").length} to
                  review
                </span>
              </div>
              {!pending.length && (
                <p className="empty">
                  Proposed changes appear here. You always get the final say.
                </p>
              )}
              {pending.slice(0, 10).map((p) => (
                <article className="proposal" key={p.id}>
                  <div className="proposal-top">
                    <strong>{p.operation.replaceAll("_", " ")}</strong>
                    <span className={`status ${p.status}`}>{p.status}</span>
                  </div>
                  <p>
                    {String(
                      p.payload.title ||
                        p.payload.name ||
                        (p.before as CalendarEvent)?.title ||
                        (p.before as Calendar)?.name ||
                        "Calendar change",
                    )}
                  </p>
                  {p.payload.start ? (
                    <small>
                      {DateTime.fromISO(String(p.payload.start))
                        .setZone(timezone)
                        .toLocaleString(DateTime.DATETIME_MED)}{" "}
                      →{" "}
                      {DateTime.fromISO(String(p.payload.end))
                        .setZone(timezone)
                        .toLocaleString(DateTime.TIME_SIMPLE)}
                    </small>
                  ) : null}
                  {p.operation === "calendar_delete" && (
                    <p>
                      Includes{" "}
                      {((p.payload.affected_events as unknown[]) || []).length}{" "}
                      events.
                    </p>
                  )}
                  {p.before && p.operation === "event_update" && (
                    <small className="previous">
                      Previously:{" "}
                      {DateTime.fromISO((p.before as CalendarEvent).start)
                        .setZone(timezone)
                        .toLocaleString(DateTime.DATETIME_MED)}
                    </small>
                  )}
                  {p.result?.conflicts?.length ? (
                    <div className="conflict">
                      Overlaps:{" "}
                      {p.result.conflicts.map((e) => e.title).join(", ")}
                      {p.status === "pending" && (
                        <label className="check">
                          <input
                            type="checkbox"
                            checked={!!overlap[p.id]}
                            onChange={(e) =>
                              setOverlap((o) => ({
                                ...o,
                                [p.id]: e.target.checked,
                              }))
                            }
                          />
                          Allow this overlap
                        </label>
                      )}
                    </div>
                  ) : null}
                  {p.error && <p className="error">{p.error}</p>}
                  {p.status === "pending" && (
                    <div className="proposal-actions">
                      <button
                        disabled={busy}
                        onClick={() =>
                          void action(async () => {
                            await api(`/proposals/${p.id}/approve`, "POST", {
                              allow_overlap: !!overlap[p.id],
                            });
                          })
                        }
                      >
                        Accept change
                      </button>
                      {["event_create", "event_update"].includes(
                        p.operation,
                      ) && (
                        <button
                          className="quiet"
                          disabled={busy}
                          onClick={() =>
                            setDraft({
                              supersedes: p.id,
                              id:
                                p.operation === "event_update"
                                  ? String(p.payload.event_id)
                                  : undefined,
                              version:
                                p.operation === "event_update"
                                  ? Number(p.payload.expected_version)
                                  : undefined,
                              title: String(p.payload.title),
                              calendar_id: String(p.payload.calendar_id),
                              start: DateTime.fromISO(String(p.payload.start))
                                .setZone(timezone)
                                .toFormat("yyyy-MM-dd'T'HH:mm"),
                              duration: Math.round(
                                (Date.parse(String(p.payload.end)) -
                                  Date.parse(String(p.payload.start))) /
                                  60000,
                              ),
                              location: String(p.payload.location || ""),
                              estimate: Boolean(p.payload.duration_is_estimate),
                            })
                          }
                        >
                          Edit
                        </button>
                      )}
                      <button
                        className="quiet"
                        disabled={busy}
                        onClick={() =>
                          void action(async () => {
                            await api(`/proposals/${p.id}/reject`, "POST");
                          })
                        }
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                  {p.status === "uncertain" && (
                    <button
                      className="quiet"
                      disabled={busy}
                      onClick={() =>
                        void action(async () => {
                          await api(`/proposals/${p.id}/retry`, "POST");
                        })
                      }
                    >
                      Reconcile original operation ↗
                    </button>
                  )}
                </article>
              ))}
            </section>
          </div>
        </div>
        <footer>
          Made for your rhythm.{" "}
          <span>VOICE → UNDERSTAND → REVIEW → CALENDAR</span>
        </footer>
      </main>
      {draft && (
        <div className="modal-backdrop">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="event-title"
          >
            <div className="section-head">
              <h2 id="event-title">{draft.id ? "Edit event" : "A new plan"}</h2>
              <button className="quiet" onClick={() => setDraft(null)}>
                Close ×
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void saveDraft();
              }}
            >
              <label>
                Title
                <input
                  required
                  value={draft.title}
                  onChange={(e) =>
                    setDraft({ ...draft, title: e.target.value })
                  }
                />
              </label>
              <label>
                Calendar
                <select
                  value={draft.calendar_id}
                  disabled={!!draft.id}
                  onChange={(e) =>
                    setDraft({ ...draft, calendar_id: e.target.value })
                  }
                >
                  {calendars
                    .filter((c) => c.writable)
                    .map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Starts · {timezone}
                <input
                  type="datetime-local"
                  required
                  value={draft.start}
                  onChange={(e) =>
                    setDraft({ ...draft, start: e.target.value })
                  }
                />
              </label>
              <label>
                Duration in minutes
                <input
                  type="number"
                  required
                  min="1"
                  max="10080"
                  value={draft.duration}
                  onChange={(e) =>
                    setDraft({ ...draft, duration: Number(e.target.value) })
                  }
                />
              </label>
              <label>
                Location
                <input
                  value={draft.location}
                  onChange={(e) =>
                    setDraft({ ...draft, location: e.target.value })
                  }
                />
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={draft.estimate}
                  onChange={(e) =>
                    setDraft({ ...draft, estimate: e.target.checked })
                  }
                />
                Duration is approximate
              </label>
              <button disabled={busy}>Preview change</button>
              {draft.id && (
                <button
                  type="button"
                  className="danger quiet"
                  disabled={busy}
                  onClick={() =>
                    void action(async () => {
                      await api("/proposals", "POST", {
                        operation: "event_delete",
                        payload: {
                          event_id: draft.id,
                          expected_version: draft.version,
                        },
                      });
                      setDraft(null);
                    })
                  }
                >
                  Propose deletion
                </button>
              )}
            </form>
          </section>
        </div>
      )}
      {calendarForm && (
        <div className="modal-backdrop">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="calendar-title"
          >
            <div className="section-head">
              <h2 id="calendar-title">
                {editingCalendar ? "Edit calendar" : "New calendar"}
              </h2>
              <button className="quiet" onClick={() => setCalendarForm(false)}>
                Close ×
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void action(async () => {
                  await api("/proposals", "POST", {
                    operation: editingCalendar
                      ? "calendar_update"
                      : "calendar_create",
                    payload: editingCalendar
                      ? {
                          calendar_id: editingCalendar.id,
                          expected_version: editingCalendar.version,
                          calendar: { name: calendarName, timezone },
                        }
                      : { name: calendarName, timezone },
                  });
                  setCalendarForm(false);
                });
              }}
            >
              <label>
                Name
                <input
                  required
                  value={calendarName}
                  onChange={(e) => setCalendarName(e.target.value)}
                />
              </label>
              <button disabled={busy}>Preview calendar</button>
              {editingCalendar && editingCalendar.id !== "personal" && (
                <button
                  type="button"
                  className="danger quiet"
                  onClick={() =>
                    void action(async () => {
                      await api("/proposals", "POST", {
                        operation: "calendar_delete",
                        payload: {
                          calendar_id: editingCalendar.id,
                          expected_version: editingCalendar.version,
                        },
                      });
                      setCalendarForm(false);
                    })
                  }
                >
                  Propose calendar deletion
                </button>
              )}
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
