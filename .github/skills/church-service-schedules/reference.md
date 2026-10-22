# Reference

## Parsing-note example

```markdown
# Finding the service schedule

- Start at `https://church.example/`.
- Open **Services** > **Schedule**.
- Use the linked calendar for dated services; use the PDF link named **Current timetable** for start times.
- Language: German. Stated on the **About** page ("Gottesdienste in deutscher Sprache").
- If the calendar is empty, check the official diocese schedule at `https://diocese.example/parish`.
```

When the language is not stated, write it as an inference:

```markdown
- Language: Inferred: German. No explicit statement; the schedule page is written entirely in German.
```

## Language evidence

Look for an explicit statement first, in this order:

1. Labels on the schedule itself ("English Mass", "Hl. Messe auf Polnisch", "Misa en español").
2. An "About", "Services" or "Languages" page, or a linked official diocese entry.
3. Language-specific sections or a language switcher that points to a service-specific page.

Weak evidence (use only as an inference, and mark it `Inferred:`):

- The `lang` attribute of `<html>`.
- The language of the schedule page text.
- The site's UI language or predominant language. The UI language alone says little about the service language.

## Playwright guidance

- Dismiss cookie or consent banners (accept only what is needed to view the content), then continue.
- Wait for the page to finish loading (network idle or the schedule element appearing) before reading it. Use a timeout of about 30 s per page and move on after one retry.
- Read content inside iframes and JS-rendered calendars (use the frame's content, or open the iframe URL directly).
- PDFs and images: download the file and extract its text. If it is a scan or cannot be read reliably, treat it as unreadable and log it in `errors.log`. Do not guess its contents.
- Follow at most 6 page hops from the start URL (including fallback sources) per church. Then give up and log the reason.

## Source precedence

Prefer the church's own current page. If the church site and the diocese or another official source disagree, use the more recent and more specific source (a dated page beats an undated one, a page for that church beats a general one). Record the conflict and the choice in `parsing.md` as a route note, without dates or times, and in `errors.log` if the conflict makes the schedule unverifiable.

## errors.log format

One line per entry: `<uuid> | <checked source URL> | <reason>`

- For an invalid input record with no usable UUID, use `record#<index> | - | <reason>` (index is 0-based in the input list).
- Use `-` for the source when no source was checked.
- Keep each entry on a single line.

## Worker return format

Each worker returns, per assigned church, one JSON block followed by notes:

````markdown
```json
{
  "uuid": "…",
  "services": [{"language": "German", "start_time": "10:00", "date": "2026-10-25"}],
  "error": null
}
```
Parsing notes: start URL, navigation path, authoritative source, fallback, language evidence.
````

On failure, `services` is `[]` and `error` is `{"source": "<URL>", "reason": "<reason>"}`.
