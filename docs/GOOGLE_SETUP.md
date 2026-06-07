# Google Setup

This guide explains how to connect your own Google Calendar and Google Sheets.

## Google Calendar

HomeNote supports two Google Calendar paths:

- iCal feed: simplest, works when you have a secret or public iCal URL.
- Google Calendar API: best for private/shared calendars that only work when you are logged in.

## Google Calendar API For Private Or Shared Calendars

Use this when an embed URL works in your browser only because you are logged in.

### 1. Create OAuth Credentials

1. Open Google Cloud Console.
2. Create or select a project.
3. Enable **Google Calendar API**.
4. Configure the OAuth consent screen.
5. Create an OAuth client ID.
6. Choose **Desktop app** as the application type.
7. Download the JSON file.
8. Save it as `google-credentials.json`.

### 2. Authorize Once

On a computer with a browser, from the HomeNote project folder:

```bash
python -m pip install -r requirements.txt
python tools/google_calendar_auth.py --credentials google-credentials.json --token google-token.json
```

Sign in with the Google account that can see the shared calendar. The helper saves `google-token.json`.

### 3. Copy Files To The Pi

```bash
scp google-credentials.json google-token.json pi@homenote.local:/home/pi/homenote/
```

Use your actual Pi username and hostname/IP if different.

### 4. Configure HomeNote

```json
"calendars": [
  {
    "name": "Shared Calendar",
    "provider": "google_api",
    "id": "shared-calendar@example.com",
    "credentials_path": "/home/pi/homenote/google-credentials.json",
    "token_path": "/home/pi/homenote/google-token.json",
    "color": "#4c91d9"
  }
]
```

The `id` is the calendar ID. For many shared calendars this is an email address.

Restart:

```bash
sudo systemctl restart homenote.service
```

Do not commit `google-credentials.json` or `google-token.json` to GitHub.

## Google Calendar iCal

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
