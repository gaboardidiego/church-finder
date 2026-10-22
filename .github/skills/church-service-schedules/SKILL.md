---
name: church-service-schedules
description: "Use when given a JSON file of churches and asked to find upcoming services, mass times, liturgies, or worship schedules, browse the listed websites with Playwright, and save per-church schedules. Not for one-off questions about a single church; answer those directly."
argument-hint: "path/to/churches.json [number of days] [timezone]"
user-invocable: true
---

# Church Service Schedules

Find upcoming church services for records in a JSON input file, using each record's website as the starting point. Save one schedule per church and reusable website-navigation and language notes.

Supporting files in this folder: [reference.md](./reference.md) (examples, language evidence, Playwright guidance, source precedence, log and worker formats) and [validate.py](./validate.py) (final validation).

## Input and output

1. Use the JSON path supplied by the user or in the skill arguments. If no input file is specified, ask for its path before proceeding.
2. Accept either a JSON array of church records or an object with a `results` array.
3. Each church record should have a stable `uuid`, `name`, and `website`. Do not invent missing identifiers or websites. An invalid record gets **no folder**; it is only reported in `errors.log` and is skipped everywhere else (including validation).
4. Church-list JSON files live in `data/churches/`. Use `data/services/<input-stem>/` as the output root, regardless of the current working directory. For example, `data/churches/small.json` produces `data/services/small/`.
5. Record every upcoming service the sources show, with no upper date limit, starting now and excluding service times that have already passed today. Apply a fixed horizon (both end dates included) only when the user requests one. Expansion of recurring timetables has its own limit; see step 5 of the procedure. Determine the IANA timezone once from the user, the records' location (coordinates, address) or the input file; if records span several timezones, evaluate each church in its own timezone. Determine "now" once at the start and use the same timestamp for every church and worker.

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

Use an ISO `date` (`YYYY-MM-DD`) and local 24-hour `start_time` (`HH:MM`). Do not include church metadata, service names, or other fields. If no dated services can be verified, write an empty array and explain why in the root `errors.log`.

### Language

Set `language` from the first applicable source:

1. An explicit statement of the service language on the church's website or linked official sources (see the evidence list in [reference.md](./reference.md)).
2. Otherwise, infer it from the language of the schedule page or, if needed, the church's website. For multilingual sites, use the language associated with the relevant service or schedule; if that is unclear, use the site's predominant language.

Never assume a language from the country or region alone; the language must come from evidence. In `<uuid>/parsing.md`, record the language and where it was found. For an inference, prefix it with `Inferred:` and state what it is based on.

### errors.log

One line per entry: `<uuid> | <checked source URL> | <reason>` (formats for invalid records and missing sources are in [reference.md](./reference.md)). Create the file only when needed. On a re-run, replace the existing entries for a church rather than adding duplicates.

## Procedure

0. **Back up the previous state.** If the output root already exists, copy it before changing anything: `cp -a data/services/<input-stem> data/services/_backups/<input-stem>-<YYYYMMDD-HHMMSS>` (local time; create `_backups/` if needed). Never modify or delete existing backups. Skip this step if the output root does not exist yet, and tell the user the backup path when one was made.
1. Read and validate the input JSON. Log invalid records. Identify the output root and each UUID folder for valid records.
2. Before browsing a church's website, read its existing `<uuid>/parsing.md`, if present. Use its navigation path to go directly to the known schedule page or document, but verify that the route still works and the information is current.
3. Open the record's `website` in Playwright (see the Playwright guidance in [reference.md](./reference.md)). Follow the site's own navigation and links to its service timetable, dated calendar, announcements, or linked schedule documents. Prefer the church's own sources or its official diocese. Do not treat search snippets or third-party directories as confirmed schedules. If sources disagree, apply the source precedence in [reference.md](./reference.md).
4. Determine the service language as described in the Language section.
5. Extract only dates and start times supported by the source. Include every explicitly dated service shown, however far ahead. Expand a recurring timetable into dates only when both its recurrence and start time are explicit and there is no evidence it has expired; expand it up to the end of its stated validity (season, month, "until" date) or, if none is stated, for 30 days from now. With a user-requested horizon, drop everything beyond it. Do not guess times, dates, or cancellations. Services at the same date and time in different languages are separate entries; remove exact duplicates.
6. Write `<uuid>/services.json` (replacing any previous file) as specified above.
7. Write or update `<uuid>/parsing.md` with reusable instructions for finding the schedule starting from the listed website: the start URL, navigation labels or links to follow, the authoritative schedule page/document, any useful fallback route, and the language information. Do not put discovered dates, times, or run summaries in this file. Avoid overwriting useful existing route notes unless the route has changed. See the example in [reference.md](./reference.md).
8. If a schedule cannot be verified for a church (including when a site is unavailable, no dated services are published, or the available page has no usable start times), add an entry to root `errors.log`. An empty `services.json` is not a substitute for recording the reason.
9. Validate by running `python3 .github/skills/church-service-schedules/validate.py data/churches/<input-stem>.json [--days N] [--timezone <IANA name>]`. Fix any reported problems and re-run until it passes, or report what remains. The script skips invalid records and checks folders, `parsing.md`, the `services.json` format and dates (not in the past, and within the horizon if one was requested), and `errors.log`.

## Progress reporting

Tell the user how far along you are, without waiting for the end:

- At the start: the number of valid records, the number of invalid ones, the horizon (or "all published services"), and the backup path (if any).
- After every 10 churches processed (and after the last one), send a short message: `Processed X/Y churches — N with services, M unverified (logged)`. For a list of fewer than 10 churches, report only at the end.
- If a church takes unusually long or a worker fails, mention it in the next update.
- At the end: totals, the location of `errors.log`, and the validation result.

When processing in parallel, the coordinating agent counts a church as processed once its results are written.

## Parallel processing

When there are multiple valid church records and the current agent environment supports delegation, process independent churches in parallel. Use at most five workers, assigning each church to exactly one worker. Give each worker the input records, requested horizon (if any) and the shared "now" timestamp, output root, and the instruction to read any existing parsing note before browsing. Workers may browse and report findings, but must not write output files. Each worker returns, per UUID, the JSON block and notes described in [reference.md](./reference.md). If a worker fails, retry its churches once with a new worker; if it fails again, log an error for each of those churches. The coordinating agent writes all files and the shared `errors.log`, then runs the validation in step 9. If delegation is unavailable or there is only one church, process the records directly.
