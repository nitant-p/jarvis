# Jarvis — Local Voice Scheduler

> A private personal planner that turns phone voice notes into calendar entries, makes room for long-term goals, and adapts plans using feedback about what actually happened.

**Status:** Product planning; no implementation yet.  
**Updated:** 20 October 2026  
**Initial user:** One person  
**Host plan:** Develop on the available Mac now. Hosting is deferred; the previously discussed DigitalOcean 8 GB CPU instance is the assumed portability target. MacBook Pro is not the permanent always-on host.

This document records the product discussion. **Confirmed** requirements reflect the user's decisions. **Proposed** criteria and technical directions are starting points for discussion. **Open** items still need a decision; this is not a finalized architecture.

**Cloud trial research:** See [specifications, provider costs, and validation plan](cloud-hosting-research.md). A trial on rented hardware changes the original privacy boundary; the proposed first test uses synthetic goals and non-sensitive recordings. This research does not provision services or change the long-term requirement to keep private goals on owned hardware.

**Current implementation scope:** [Version 1 architecture — voice to calendar tools](architecture-v1.md) selects a starting model, transcription runtime, pipeline, MCP tools, calendar CRUD, and provider boundaries. Schedule optimization and long-term goal planning are deferred. The broader requirements below remain the product roadmap.

## Contents

- [Purpose and principles](#purpose-and-principles)
- [Confirmed requirements](#confirmed-requirements)
- [Core workflows](#core-workflows)
- [Proposed event and task criteria](#proposed-event-and-task-criteria)
- [Proposed long-term goal framework](#proposed-long-term-goal-framework)
- [Scheduling and adaptation](#scheduling-and-adaptation)
- [Tracking and daily feedback](#tracking-and-daily-feedback)
- [Calendar options](#calendar-options)
- [Hosting and phone access](#hosting-and-phone-access)
- [Preliminary architecture boundaries](#preliminary-architecture-boundaries)
- [Release plan and acceptance criteria](#release-plan-and-acceptance-criteria)
- [Research and open decisions](#research-and-open-decisions)

## Purpose and principles

Jarvis should help answer two connected questions:

1. **What did I ask to schedule?** Capture and understand short voice notes, clarify missing details, and turn them into usable calendar entries.
2. **How should I spend the time I have?** Fit meaningful long-term goals around real commitments, recovery, hobbies, and everyday logistics.

The aim is balance as well as productivity. A useful plan makes progress achievable without treating every free minute as work. It should improve through explicit rules, observed outcomes, and user feedback rather than assuming the first scheduling policy is correct.

## Confirmed requirements

| Area | Requirement |
| --- | --- |
| Local processing | Transcription and LLM inference run on the user's own hardware. No cloud AI processing of personal inputs. |
| Private storage | Goals, detailed personal context, planning conversations, and tracking data stay on owned hardware. |
| Cloud exception | A cloud calendar is acceptable for event names, start/end times or duration, and location. |
| Audio retention | Recordings do not need permanent storage. Process them locally and remove temporary audio; exact cleanup policy remains open. |
| Capture | Record English voice notes from a phone. A private mobile website is the preferred initial direction. |
| Interfaces | Apple Calendar is a main schedule view, alongside a private website accessible from the phone. |
| Calendar compatibility | Work with Google Calendar and Apple Calendar. Whether this requires separate iCloud storage is still open. |
| Clarification | Ask for missing time and approximate duration. Ask about conflicts rather than silently deciding. |
| Goal quality | Develop vague long-term goals through questions before adding routine sessions to the schedule. |
| Authority | Propose a schedule the user can accept, reject, or edit. Broad ability to move events is acceptable during early experimentation. |
| Planning cadence | Reconsider the affected day whenever new information is added. Prepare the next day's plan at the end of the day. |
| Notifications | Routine proactive notifications should arrive at the end of the day. Event reminders are desired; their settings need clarification. |
| Completion | Support both marking an item complete in the website and reporting completion through a quick voice update. |
| Missed check-ins | Allow retrospective updates and a manageable backlog without assuming missing feedback means failure. |
| Adaptation | Suggest ways to recover missed activities using remaining time, existing plans, priorities, and recent activity history. |
| Fixed commitments | Reserve a configuration area for work, recurring commitments, and other boundaries; actual values will be discussed later. |

### Privacy boundary

The cloud calendar is a limited projection of the plan, not the store for the full personal model. Goal motivation, current skill level, progress notes, transcripts, and the reasoning behind recommendations remain local. Do not place these in calendar descriptions, attachments, or hidden provider metadata.

An event title such as “Guitar practice” still reveals an activity. The user accepts that limited disclosure; detailed goal records remain local. Generic titles can be an optional future privacy preference.

Cloud notification services, hosted gateways, analytics, and remote backups are **not yet approved exceptions**. Their data exposure must be considered separately from the accepted calendar integration.

## Core workflows

### 1. Capture a one-time event

**Example:** “Tomorrow I'm getting dinner with a friend.”

1. Open the private website on the phone and record a short note.
2. Upload it directly to the user's host for local transcription.
3. Interpret the request and show a correctable transcript and event draft.
4. Ask for the dinner time and rough duration; ask for location if needed for travel planning.
5. Resolve relative dates using the recording context and the user's timezone. Confirm genuinely ambiguous dates.
6. Check the current schedule and show any conflict for a decision.
7. Present the proposed event and any affected blocks for review.
8. After the chosen acceptance step, synchronize the event so it appears in Apple Calendar.

An estimated dinner end is not a promise. The plan should leave appropriate slack or make following activities flexible. Dinner alone and dinner with friends may use different user-approved duration estimates.

### 2. Develop a long-term goal

**Example:** “I want to learn guitar over the next six months.”

1. Save a local goal draft.
2. Ask focused follow-up questions about the desired result, current ability, available practice time, and practical constraints.
3. Make the goal specific enough to produce concrete sessions and assess progress.
4. Show the structured goal for user confirmation.
5. Only then make it eligible for routine scheduling.

A vague aspiration should not silently turn into arbitrary recurring calendar blocks.

### 3. Review tomorrow

At the end of the day, prepare tomorrow's plan and send one readiness notification. The user can review, accept, reject, or edit it from the phone. Combine the daily check-in with this review where practical to avoid separate routine notifications.

The initial horizon is tomorrow. Three-day and weekly plans are later options once the daily workflow works well.

### 4. Report progress or recover a missed activity

**Examples:** “I finished the reading session; it took about forty minutes.” / “I missed the gym.”

Interpret the update locally, identify the relevant scheduled item, and clarify if the reference is ambiguous. Record completion, partial completion, or a missed session. Reconsider the remaining day and offer alternatives when useful.

For example, after a missed 7 p.m. gym session, compare a later workout against already planned study. Explain the tradeoff using recorded priorities and recent activity, and let the user choose. The example window of 8 p.m.–midnight is not an approved bedtime or standing availability rule.

## Proposed event and task criteria

An **event** occupies time on the calendar. A **task** describes work that can be assigned to one or more time blocks. A **goal** supplies the longer-term outcome those tasks support. Keeping these distinct lets rescheduling preserve progress history.

These criteria are proposed; the LLM should ask only for missing information that matters to the current decision.

| Field | Needed when | Clarification or behavior |
| --- | --- | --- |
| Title and intent | Every item | Distinguish a new event, task, goal, progress update, or change request. |
| Date and timezone | Before placing a block | Resolve “tomorrow” against capture time; ask if date/time interpretation is ambiguous. |
| Start time or allowed window | Before placing a block | Ask for a specific appointment time, or establish flexibility for a schedulable task. |
| Estimated duration | Before placing a block | Ask for a rough estimate; optionally record a minimum/likely/maximum range. |
| Duration uncertainty | Open-ended activities | Use slack and flexible following blocks; do not treat an estimate as a firm finish. |
| Location | When travel or equipment matters | Allow home, work, online, a named place, or unknown where location is irrelevant. |
| Travel/setup time | When transitions matter | Start with user-supplied average commute and preparation times. |
| Flexibility | Before proposing a move | Distinguish fixed appointments, movable blocks, and explicitly protected time. |
| Priority and deadline | When competing for time | Ask when the choice affects a conflict or deferral; do not invent urgency. |
| Category | For balance and tracking | Examples: work, study, movement, social, hobby, recovery, meal, travel. |
| Split policy | For flexible tasks | Record whether multiple shorter sessions are useful and their minimum length. |
| Dependencies/resources | When relevant | Respect prerequisites, opening hours, equipment, and required location. |
| Goal link | For goal sessions | Link locally to an approved goal and a concrete session objective. |
| Outcome | After a session | Track done, partial, skipped, rescheduled, or unknown, plus optional actual duration. |

System-managed information should include stable local IDs, source/capture time, provider event IDs, proposal versions, and synchronization state. These support reliable updates without repeated user questions.

## Proposed long-term goal framework

“The LLM is satisfied” should mean an explicit completeness check, not an opaque feeling or confidence score. The conversation gathers the information; a validation step checks it; the user confirms it.

| Criterion | Question to resolve | Guitar example, for illustration only |
| --- | --- | --- |
| Specific outcome | What would success look like? | Play three chosen beginner songs. |
| Starting point | What can you do today? | Own a guitar; have not started practicing. |
| Horizon | By when, or when should progress be reviewed? | Six months, with an earlier review date. |
| Time commitment | What is a sustainable session length and weekly frequency? | User selects a realistic practice budget. |
| Concrete next actions | What happens in the first few sessions? | Tune the guitar, learn initial chords, follow a chosen lesson. |
| Milestones/evidence | How will progress be recognized? | Demonstrate chord changes or play a song section. |
| Practical constraints | Where, when, and with what resources? | Guitar available at home; suitable practice hours. |
| Tradeoffs | What can yield when time is scarce? | User sets relative priority and minimum useful practice. |
| Review policy | When should the plan be adjusted? | Review after initial sessions and update estimates. |

**Proposed readiness rule:** Required criteria have explicit answers, there are no unresolved contradictions, the first sessions are actionable, the time budget is feasible, and the user has confirmed the goal. Distinguish user statements from suggested or inferred details.

**Proposed lifecycle:** Draft → clarifying → ready for confirmation → active → paused/completed/archived. A goal can return to clarification when circumstances change. Full goal content stays local throughout.

## Scheduling and adaptation

### Starting policy — proposed, to be tuned

Separate **hard constraints** such as a confirmed appointment or sleep boundary from **preferences** such as studying earlier or making more time for guitar. Exact boundaries and relative weights remain undecided.

Start by producing a feasible schedule, then compare feasible alternatives using:

- Progress toward confirmed goals and user-defined priorities.
- Deadlines and commitments that the user has marked important.
- A balanced allocation of focused work, movement, hobbies, social time, and recovery.
- Commute, meal, preparation, and transition time.
- Slack for uncertainty and unscheduled life.
- Continuity: avoid repeatedly disrupting a plan without a useful benefit.

Do not equate optimization with filling every gap. If everything cannot fit, explain what remains unscheduled and ask about the material tradeoff instead of silently breaking constraints.

### Hobbies and recovery

The user's preferred alternatives to unplanned scrolling include reading a current book, watching a chosen TV show, and learning or playing guitar. Do not recommend Instagram/reels scrolling as a planned restorative break.

An activity can be both a hobby and a long-term goal. Avoid double-counting the same session. Distinguish an intentional rest period from unexplained or unreported time, and leave room for unstructured rest.

### Replanning triggers

Reconsider the affected day after a new event, a change in timing, an explicit missed/partial session, or a user progress update. Calendar edits should also be reconciled before presenting a fresh plan. Prepare tomorrow's proposal during the evening review.

Use recent **confirmed** activity to explain choices: for example, whether to recover study time or take a workout/rest opportunity. Missing tracking data must reduce certainty rather than become evidence that an activity did not happen.

### Authority and conflicts

The user permits broad rescheduling during experimentation, including moving existing events. The system can only alter calendars/events for which it has write permission. An explicit overlap still needs clarification, as requested.

**Open:** Does “accept or reject in Apple Calendar” mean a separate proposal calendar, explicit approval in the website, or actual calendar invitations? Ordinary calendar writes do not automatically create an invitation-style approval workflow. Do not assume dragging or deleting an event means rejecting its underlying goal.

**Proposed initial approach:** Review a change summary in the private website, then publish accepted changes to the calendar. An alternative is a visible proposal calendar that the user edits directly. Neither choice is finalized.

## Tracking and daily feedback

- Provide quick completion controls and local transcription of spoken updates.
- Separate planned duration from actual duration. Marking an item complete does not establish how long it took.
- Allow partial completion, skipping, rescheduling, and retrospective corrections.
- Keep unanswered check-ins in a small, dismissible review backlog. Let the user answer several together or leave them unknown.
- Use gentle follow-up during the next daily review rather than repeated prompts throughout the day.
- Track planned versus reported time by activity/goal, goal progress, repeated deferrals, and how often suggested plans are accepted or edited.
- Treat empty calendar space as **unallocated**, and absent reports as **unknown**. Neither measures actual idle time. Passive activity tracking is not currently specified.
- Tune estimates and scheduling priorities from feedback; do not silently rewrite the user's goal priorities based on a few missed sessions.

## Calendar options

Apple Calendar is a client application as well as an interface to accounts; using it does not require storing every event in iCloud. Google documents that its calendar events can be displayed in Apple Calendar on iPhone and Mac. [Google setup guide](https://support.google.com/calendar/answer/99358?hl=en).

| Option | Fit for this project | Tradeoff / unresolved detail |
| --- | --- | --- |
| **Google Calendar backend, Apple Calendar view** | Proposed simplest starting point: local service writes to a selected Google calendar; Apple Calendar displays that account. | Confirm whether any existing iCloud-only events must also be read. Avoid creating duplicate copies in both providers. |
| **Mac calendar bridge using EventKit** | Candidate for accessing calendars available to a native Mac helper, with user permission. | Requires a macOS integration and testing of account behavior; a Raspberry Pi migration would need another adapter. |
| **Direct iCloud calendar integration** | Research candidate if iCloud must be an independent backend. | Validate supported authentication, read/write synchronization, recurring events, and headless operation before selection. |

Apple's [EventKit documentation](https://developer.apple.com/documentation/eventkit) covers calendar access and change notifications. Google's [incremental synchronization guide](https://developers.google.com/workspace/calendar/api/guides/sync) describes retrieving provider changes. Apple describes third-party account access in its [authentication guidance](https://support.apple.com/en-gb/102654); this does not by itself establish a complete server-side iCloud integration.

**Proposed synchronization requirements:** Stable identity mapping, duplicate-safe retries, handling edits/deletions from the phone, detection of concurrent changes, and clear pending/failed synchronization states. Preserve local proposals when offline; do not report an event as synchronized until the provider confirms it.

## Hosting and phone access

### Hardware options — preliminary recommendations

| Option | Suggested role | Assessment |
| --- | --- | --- |
| **Existing Mac** | Build and validate the first version. | Recommended first step. Check model, memory, and available storage before selecting local models. Sleep/offline periods affect processing and evening notifications. |
| **Apple Silicon Mac mini** | Future single-box home host for the website, storage, transcription, and LLM. | Preferred candidate to benchmark. Provisionally consider 24–32 GB unified memory for headroom; actual needs depend on chosen models, quantization, context, and concurrency. |
| **Raspberry Pi 5** | Lightweight always-on web/scheduling host, or a small-model experiment. | Candidate if cost/power matters and latency is acceptable. Do not assume it matches a Mac for speech and LLM inference; benchmark representative recordings first. |
| **Pi plus existing Mac** | Pi handles availability and queues; owned Mac runs inference. | Keeps processing on owned hardware but depends on the Mac being reachable. More operational complexity than one host. |

These are engineering recommendations, not measured performance claims or purchase instructions. The [Mac mini M4/M4 Pro specifications](https://support.apple.com/en-us/121555) describe unified-memory configurations. The [Raspberry Pi 5 product brief](https://pip-assets.raspberrypi.com/categories/892-raspberry-pi-5/documents/RP-008348-DS-4-raspberry-pi-5-product-brief.pdf) lists its processor and memory options. Check current configurations, local prices, and workload measurements before buying; the Mac specification link refers specifically to the 2024 generation.

### Private mobile website — proposed direction

- Host the application and private database on owned hardware; do not use public website hosting for personal records.
- Require authenticated access and HTTPS. Browser microphone capture requires a secure context: [microphone API reference](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia).
- Decide whether access is home-network-only or available away from home through an authenticated private connection. A self-hosted VPN is one candidate, not a selected dependency.
- Avoid cloud speech APIs, hosted LLMs, third-party analytics, and remote error reports containing personal content.
- Decide how phone drafts/uploads survive temporary disconnection, and remove transient audio after the agreed processing/retry window.

**Notification boundary:** iPhone Home Screen web apps can use Web Push, but Apple's push infrastructure participates in delivery. This is an additional external dependency, not fully local delivery. If accepted, propose a generic “Tomorrow's plan is ready” message and retrieve all details privately. Otherwise, evaluate reminders through the already approved calendar route. [WebKit explanation](https://webkit.org/blog/13878/).

App-triggered clarification can appear while the website is open. Whether unresolved questions may trigger daytime push notifications remains open; routine planning notifications are end-of-day only.

## Preliminary architecture boundaries

These are responsibilities to preserve when choosing a stack, not a commitment to separate services or a particular framework:

| Responsibility | Purpose |
| --- | --- |
| Phone interface | Record/upload, correct transcripts, answer questions, review plans, report progress. |
| Local transcription | Convert temporary recordings to English text without cloud inference. |
| Local language understanding | Extract structured intent, draft follow-up questions, and explain proposed choices. |
| Validation and dialogue state | Track unanswered questions and enforce explicit event/goal readiness criteria. |
| Local planner | Apply constraints, produce candidate slots, and calculate affected schedule changes. |
| Private storage | Keep goals, tasks, preferences, tracking, proposal history, and synchronization mappings. |
| Calendar adapter | Read availability and apply approved event changes with minimal exported fields. |
| Daily job and notifications | Prepare the next-day plan and deliver the selected reminder mechanism. |

**Proposed separation:** Let the LLM interpret language and explain options; use explicit application checks for dates, completeness, overlaps, and permissions. Evaluate a rules-based planner first and a local constraint solver if needed. The model should not directly issue unchecked calendar mutations.

The [Version 1 architecture](architecture-v1.md) now recommends Python/FastAPI, React/TypeScript, SQLite, Whisper small.en via whisper.cpp, Qwen3-4B-Instruct-2507 via llama.cpp, and a thin private MCP adapter. Model/runtime compatibility and resource use must be validated during implementation. Hosting deployment remains deferred.

## Release plan and acceptance criteria

### Version 1 — Voice note to calendar

**Success:** Record something on the phone, have a local LLM understand it, and get it scheduled correctly.

- [ ] Private phone recording/upload interface connected to the Mac.
- [ ] Local English transcription and structured event extraction.
- [ ] Correctable transcript and event draft.
- [ ] Follow-up questions for missing date/time/duration and relevant location details.
- [ ] Conflict detection and an explicit resolution choice.
- [ ] A defined review/publish flow and visibility in Apple Calendar through the selected backend.
- [ ] Corrections and retries do not create duplicate events.
- [ ] Offline/sync failures remain visible and recoverable.
- [ ] Temporary audio cleanup and no cloud AI processing.

**Example acceptance scenario:** Record “Dinner with a friend tomorrow,” answer the time/duration questions, resolve any overlap, review the draft, and see one event at the agreed time on the phone. Detailed capture content stays local.

### Version 2 — Specific goals to routine sessions

**Success:** Turn a vague long-term goal into a confirmed, sufficiently detailed goal and schedule useful sessions.

- [ ] Local goal records and a persistent clarification conversation.
- [ ] Explicit readiness criteria and user confirmation before activation.
- [ ] Concrete session tasks and a feasible time budget.
- [ ] Configurable fixed commitments, commute, meals, and availability.
- [ ] Proposed routine sessions visible alongside one-time events.
- [ ] Balance preferences covering goals, hobbies, recovery, and open time.
- [ ] Website completion controls and voice progress updates.

**Example acceptance scenario:** “Learn guitar over six months” remains a draft until the outcome, baseline, time commitment, constraints, and first actions are resolved. Confirmed sessions are then proposed within available time.

### Following milestone — Feedback and adaptive replanning

The release boundary is provisional; completion tracking can be introduced earlier if useful.

- [ ] End-of-day check-in and next-day proposal, with one routine readiness notification.
- [ ] Missed-check-in backlog and retrospective updates.
- [ ] Recovery choices for missed activities using the remaining day and confirmed recent history.
- [ ] Planned-versus-reported duration views and adjustable estimates.
- [ ] Reconciliation of phone calendar edits without overwriting fresh changes.
- [ ] Longer planning horizons after the daily process proves useful.

## Research and open decisions

### Scheduling research agenda

Research is needed before claiming the system can choose a personalized “optimal” plan. Start with transparent, editable rules and compare changes against real user feedback.

| Question | Proposed investigation |
| --- | --- |
| Rules or constraint solver? | Compare a simple slot planner with a local solver on the same scenarios. [OR-Tools scheduling examples](https://developers.google.com/optimization/scheduling/employee_scheduling) demonstrate constraints and preference objectives; use the local library if selected, not a hosted optimization service. |
| What does balance mean? | Agree category targets, protected boundaries, goal priorities, and how much open time is desired. No universal weights are assumed. |
| How should durations vary? | Evaluate user estimates/ranges, buffers, and later corrections; distinguish social meals from meals alone. |
| How should missed sessions be recovered? | Compare doing it later, shortening/splitting it, deferring it, or deliberately skipping it. Test against existing priorities and recent confirmed activity. |
| How much adaptation is helpful? | Measure acceptance, edits, repeated movement, and user satisfaction. Avoid learning strong preferences from sparse or unknown data. |
| How should quality be evaluated? | Use representative scenarios: ambiguous dinner, variable commute, gym versus study, incomplete goal, unknown completion, missed check-ins, external calendar edit, offline host, and duplicate upload. |

### Decisions still needed

1. **Fixed commitments:** Workdays/hours, sleep boundaries, recurring appointments, meal patterns, average commutes, and travel buffers. Values are intentionally not filled in yet.
2. **Current hardware:** Mac model, memory, storage, and acceptable processing delay.
3. **Calendar topology:** Google-backed Apple Calendar only, or separate Google and iCloud accounts? Which calendars are readable/writable?
4. **Acceptance flow:** Website approval, a proposal calendar, or calendar invitations? How are direct phone edits interpreted?
5. **Access away from home:** Required immediately or later? Choose a private access method and offline capture behavior.
6. **Notifications:** Evening review time; event alarms versus planning notifications; whether generic Web Push through Apple infrastructure is acceptable.
7. **Goal/task criteria:** Confirm required fields, readiness rules, default priorities, splitting rules, and review cadence.
8. **Retention and recovery:** Transcript/history retention, temporary audio expiry after failure, local backup location, and change/undo history.
9. **Adaptation policy:** Protected rest, acceptable schedule density, recovery limits, and how recent activity affects recommendations.

**Next planning step:** Resolve the calendar acceptance flow, fixed commitments, current hardware, and remote access needs. Then select a minimal architecture for Version 1 and validate it with realistic voice notes before expanding the planner.
