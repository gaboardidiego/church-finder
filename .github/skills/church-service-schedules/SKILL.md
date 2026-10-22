---
name: church-service-schedules
description: "Use when given a JSON file of churches and asked to find upcoming services, mass times, liturgies, or worship schedules, browse the listed websites with Playwright, and save per-church schedules."
argument-hint: "path/to/churches.json [number of days]"
user-invocable: true
---

# Church Service Schedules

Find upcoming church services for records in a JSON input file, using each record's website as the starting point. Save one schedule per church and reusable website-navigation and language notes.

## Input and output

1. Use the JSON path supplied by the user or in the skill arguments. If no input file is specified, ask for its path before proceeding.
2. Accept either a JSON array of church records or an object with a `results` array.
3. Each church record should have a stable `uuid`, `name`, and `website`. Do not invent missing identifiers or websites; report invalid records in `errors.log`.
4. Church-list JSON files live in `data/churches/`. Use `data/services/<input-stem>/` as the output root, regardless of the current working directory. For example, `data/churches/small.json` produces `data/services/small/`.
5. Use the requested schedule horizon when provided. Otherwise, use the next 30 days in `Europe/Vienna`, starting now and excluding service times that have already passed today.

Create this structure without deleting unrelated files:

```text
data/services/<input-stem>/
├── errors.log                 # only when errors or unverified schedules exist
└── <church-uuid>/
    ├── services.json
    └── parsing.md
```

`services.json` is a JSON array containing only service objects. Each object has exactly these fields:

```json
[
  {
    "language": "German",
    "start_time": "10:00",
    "date": "2026-10-25"
  }
]
```

Use an ISO `date` (`YYYY-MM-DD`) and local 24-hour `start_time` (`HH:MM`). Do not include church metadata, service names, or other fields. Before setting `language`, check the church's website and linked official sources for an explicit statement of the service language. Use the stated language; if none is specified, infer it from the language used on the schedule page or, if needed, the church's website. For multilingual sites, use the language associated with the relevant service or schedule; if that is unclear, use the site's predominant language and document the basis for the inference. Never assume German by default. Document the language information found, or that none was published and how the language was inferred, in `<uuid>/parsing.md`. If no dated services can be verified, write an empty array and explain why in the root `errors.log`.

## Procedure

1. Read and validate the input JSON. Identify the output root and each UUID folder.
2. Before browsing a church's website, read its existing `<uuid>/parsing.md`, if present. Use its navigation path to go directly to the known schedule page or document, but verify that the route still works and the information is current.
3. Open the record's `website` in Playwright. Follow the site's own navigation and links to its service timetable, dated calendar, announcements, or linked schedule documents. Prefer the church's own sources or its official diocese. Do not treat search snippets or third-party directories as confirmed schedules.
4. Check the church website and linked official sources for the language used for services before assigning `language`. Record the stated language and its source location in `parsing.md`. If no language is stated, infer it from the language used on the schedule page or the site's predominant language, and record that this is an inference and what it is based on. For multilingual sites, prefer the language associated with the relevant service or schedule. Never default to German.
5. Extract only dates and start times supported by the source. Expand a recurring timetable into dates within the requested horizon only when both its recurrence and start time are explicit and there is no evidence it has expired. Do not guess times, dates, or cancellations.
6. Write `<uuid>/services.json` as a JSON array with one object per service, each containing exactly `language`, `start_time`, and `date`. Do not include service names or church metadata.
7. Write or update `<uuid>/parsing.md` with reusable instructions for finding the schedule starting from the listed website. Include the start URL, navigation labels or links to follow, the authoritative schedule page/document, any useful fallback route, and the website's service-language information with its source location. Do not put discovered dates, times, or run summaries in this file. Avoid overwriting useful existing route notes unless the route has changed.
8. If a schedule cannot be verified for a church (including when a site is unavailable, no dated services are published, or the available page has no usable start times), create or append to root `errors.log`. Include the church UUID, checked source, and specific reason. An empty `services.json` is not a substitute for recording the reason.
9. Validate that every church has a UUID folder and that `services.json` is a parseable JSON array. Check each service object has exactly the keys `language`, `start_time`, and `date`; validate ISO dates and `HH:MM` times, and ensure dates are within the requested horizon. Confirm `parsing.md` exists and that `errors.log` exists whenever errors or unverified schedules are present.

## Parallel processing

When there are multiple valid church records and the current agent environment supports delegation, process independent churches in parallel. Use at most three workers, assigning each church to exactly one worker. Give each worker the input records, schedule horizon, output root, and the instruction to read any existing parsing note before browsing. Workers may browse and report findings, but must not write output files. Have them return, per UUID, the verified services, reusable navigation and language notes, and any error with its checked source and reason. The coordinating agent writes all files and the shared `errors.log`, then performs the full validation in step 9. If delegation is unavailable or there is only one church, process the records directly.

## Parsing-note example

```markdown
# Finding the service schedule

- Start at `https://church.example/`.
- Open **Services** > **Schedule**.
- Use the linked calendar for dated services; use the PDF link named **Current timetable** for start times.
- The church's **About** page states that services are in German; use that language for the service entries.
- If the calendar is empty, check the official diocese schedule at `https://diocese.example/parish`.
```
