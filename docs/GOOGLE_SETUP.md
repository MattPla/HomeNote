# Google Setup

This guide explains how to connect your own Google Calendar and Google Sheets.

## Google Calendar

1. Open Google Calendar.
2. Click the gear icon, then **Settings**.
3. In the left sidebar, choose the calendar you want to show.
4. Scroll to **Integrate calendar**.
5. Copy one of these:
   - **Secret address in iCal format** for private calendars.
   - **Public address in iCal format** for public calendars.
6. Paste it into `config.json`:

```json
"calendars": [
  {
    "name": "Family",
    "url": "PASTE_ICAL_URL_HERE",
    "color": "#4c91d9"
  }
]
```

Do not commit a private iCal URL to a public repository.

## Google Sheets

HomeNote reads Google Sheets through CSV export URLs. No Google API key is needed if the sheet is shared publicly as view-only.

1. Open the Google Sheet.
2. Click **Share**.
3. Under **General access**, choose **Anyone with the link**.
4. Set the role to **Viewer**.
5. Copy the sheet URL.

The spreadsheet ID is the part between `/d/` and `/edit`:

```text
https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
```

Put it into `config.json`:

```json
"task_sheet": {
  "sheet_id": "SPREADSHEET_ID",
  "gid": "0"
}
```

## Finding A Tab GID

Each tab in a Google Sheet has a `gid`.

1. Click the tab you want.
2. Look at the URL.
3. Copy the value after `gid=`.

Example:

```text
https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit#gid=1669138132
```

Use it like this:

```json
"homework_sheet": {
  "sheet_id": "SPREADSHEET_ID",
  "gid": "1669138132"
}
```

## Task Sheet Template

Create a tab with these headers in row 1:

```text
Task, Owner, Start Date, Due Date, Priority, Status
```

Example:

```text
Task,Owner,Start Date,Due Date,Priority,Status
Laundry,Dad,06/06/2026,06/06/2026,Normal,Not Started
Dishes,Dad,06/06/2026,06/06/2026,Normal,Completed
```

## Homework Sheet Template

Create a second tab with these headers in row 1:

```text
Homework, Child, Due Date, Status
```

Example:

```text
Homework,Child,Due Date,Status
Worksheet pages 1-4,Elijah,06/06/2026,In Progress
Read chapter 3,Avery,06/07/2026,Not Started
```

## Status Colors

- `Completed`, `Complete`, `Done`, `Finished`, `Closed`, `Yes`, or `True`: green solid circle.
- `In Progress`, `In-Progress`, `Started`, or `In Progres`: yellow solid circle.
- Anything else: open circle.

