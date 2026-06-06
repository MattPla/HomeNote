# Configuration Guide

HomeNote uses one JSON file: `config.json`.

Start by copying:

```bash
cp config.example.json config.json
```

On the installed Pi, the live file is:

```bash
~/homenote/config.json
```

Restart after editing:

```bash
sudo systemctl restart homenote.service
```

## Required Settings

```json
{
  "title": "HomeNote",
  "timezone": "America/New_York",
  "days_ahead": 7
}
```

Use an IANA timezone name, such as:

- `America/New_York`
- `America/Chicago`
- `America/Denver`
- `America/Los_Angeles`

## Calendar Feeds

```json
"calendars": [
  {
    "name": "Family",
    "url": "https://calendar.google.com/calendar/ical/YOUR_PRIVATE_OR_PUBLIC_ICAL_URL/basic.ics",
    "color": "#4c91d9"
  }
]
```

Each calendar needs:

- `name`: label shown on the dashboard.
- `url`: Google Calendar iCal URL.
- `color`: rail color for events.

## Task Sheet

```json
"task_sheet": {
  "sheet_id": "YOUR_GOOGLE_SHEET_ID",
  "gid": "0"
}
```

Expected columns:

```text
Task, Owner, Start Date, Due Date, Priority, Status
```

## Homework Sheet

```json
"homework_sheet": {
  "sheet_id": "YOUR_GOOGLE_SHEET_ID",
  "gid": "YOUR_HOMEWORK_TAB_GID"
}
```

Expected columns:

```text
Homework, Child, Due Date, Status
```

## Weather

```json
"weather": {
  "latitude": 28.176856,
  "longitude": -82.67127,
  "label": "Home"
}
```

Weather uses Open-Meteo and does not require an API key.

## News

```json
"news": {
  "rss_url": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
  "limit": 12
}
```

Any RSS feed can be used. The ticker shows headlines published today in your configured timezone.

## Manual Tasks

Manual tasks are optional and are useful as a fallback if you do not want Google Sheets.

```json
"tasks": [
  {
    "title": "Take recycling out",
    "due": "Tonight",
    "owner": "Home",
    "status": "Not Started",
    "priority": "high"
  }
]
```

## Manual Events

Manual events are optional. They can include precomputed travel information.

```json
"events": [
  {
    "title": "Sample appointment",
    "calendar": "Manual",
    "start": "2026-06-06T10:00:00-04:00",
    "end": "2026-06-06T11:00:00-04:00",
    "location": "123 Main St",
    "leaveBy": "9:35 AM",
    "travelMinutes": 25,
    "color": "#4c91d9"
  }
]
```

