from __future__ import annotations

import csv
from email.utils import parsedate_to_datetime
from html import unescape
import io
import json
import os
import re
import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse
from typing import Any

import recurring_ical_events
import requests
from flask import Flask, jsonify, render_template, request
from google.auth.transport.requests import AuthorizedSession
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from icalendar import Calendar
from zoneinfo import ZoneInfo


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.environ.get("HOMENOTE_CONFIG", APP_DIR / "config.json"))
NOTES_PATH = Path(os.environ.get("HOMENOTE_NOTES", APP_DIR / "notes.json"))
GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

app = Flask(__name__)
notes_lock = threading.Lock()
config_lock = threading.Lock()

DEFAULT_CONFIG = {
    "timezone": "America/New_York",
    "title": "HomeNote",
    "days_ahead": 7,
    "calendars": [],
    "tasks": [],
    "task_sheet": {},
    "homework_sheet": {},
    "weather": {
        "latitude": 28.176856,
        "longitude": -82.67127,
        "label": "Home",
    },
}


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return dict(DEFAULT_CONFIG)

    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_config(config: dict[str, Any]) -> None:
    with config_lock:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp_path = CONFIG_PATH.with_suffix(".tmp")
        temp_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        temp_path.replace(CONFIG_PATH)


def load_notes() -> tuple[list[dict[str, Any]], float]:
    with notes_lock:
        if not NOTES_PATH.exists():
            return [], 0

        with NOTES_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        notes = payload.get("notes", []) if isinstance(payload, dict) else payload
        if not isinstance(notes, list):
            notes = []
        return notes, NOTES_PATH.stat().st_mtime


def save_notes(notes: list[dict[str, Any]]) -> float:
    sanitized = [sanitize_note(note) for note in notes if isinstance(note, dict)]
    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "notes": sanitized[:80],
    }

    with notes_lock:
        NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp_path = NOTES_PATH.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(NOTES_PATH)
        return NOTES_PATH.stat().st_mtime


def sanitize_note(note: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(note.get("id") or f"note-{datetime.now(timezone.utc).timestamp()}"),
        "x": clamp_number(note.get("x"), 0, 10000, 48),
        "y": clamp_number(note.get("y"), 0, 10000, 48),
        "width": clamp_number(note.get("width"), 120, 1200, 250),
        "height": clamp_number(note.get("height"), 90, 900, 170),
        "color": str(note.get("color") or "#fff2a8")[:24],
        "text": str(note.get("text") or "")[:3000],
        "z": clamp_number(note.get("z"), 1, 1000000, 10),
    }


def clamp_number(value: Any, minimum: int, maximum: int, fallback: int) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, number))


def coerce_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def public_settings(config: dict[str, Any]) -> dict[str, Any]:
    calendars = config.get("calendars", [])
    calendar = calendars[0] if calendars and isinstance(calendars[0], dict) else {}
    return {
        "title": config.get("title", "HomeNote"),
        "timezone": config.get("timezone", "America/New_York"),
        "daysAhead": config.get("days_ahead", 7),
        "travelBufferMinutes": config.get("travel_buffer_minutes", 10),
        "calendar": {
            "name": calendar.get("name", "Calendar"),
            "provider": calendar.get("provider", "google_api"),
            "id": calendar.get("id", ""),
            "url": calendar.get("url", ""),
            "color": calendar.get("color", "#4c91d9"),
        },
        "taskSheet": config.get("task_sheet", {}),
        "homeworkSheet": config.get("homework_sheet", {}),
        "weather": config.get("weather", DEFAULT_CONFIG["weather"]),
    }


def apply_public_settings(config: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    updated = dict(config)
    updated["title"] = str(settings.get("title") or config.get("title") or "HomeNote")[:80]
    updated["timezone"] = str(settings.get("timezone") or config.get("timezone") or "America/New_York")[:80]
    updated["days_ahead"] = clamp_number(settings.get("daysAhead"), 1, 30, int(config.get("days_ahead", 7)))
    updated["travel_buffer_minutes"] = clamp_number(
        settings.get("travelBufferMinutes"),
        0,
        120,
        int(config.get("travel_buffer_minutes", 10)),
    )

    existing_calendar = {}
    if config.get("calendars") and isinstance(config["calendars"][0], dict):
        existing_calendar = dict(config["calendars"][0])
    incoming_calendar = settings.get("calendar", {}) if isinstance(settings.get("calendar"), dict) else {}
    calendar_id = str(incoming_calendar.get("id") or "").strip()
    calendar_url = str(incoming_calendar.get("url") or "").strip()
    calendar = {
        **existing_calendar,
        "name": str(incoming_calendar.get("name") or existing_calendar.get("name") or "Calendar")[:80],
        "provider": str(incoming_calendar.get("provider") or existing_calendar.get("provider") or "google_api")[:40],
        "color": str(incoming_calendar.get("color") or existing_calendar.get("color") or "#4c91d9")[:24],
    }
    if calendar_id:
        calendar["id"] = calendar_id
    else:
        calendar.pop("id", None)
    if calendar_url:
        calendar["url"] = calendar_url
    elif "url" in incoming_calendar:
        calendar.pop("url", None)
    updated["calendars"] = [calendar] if (calendar_id or calendar_url or existing_calendar) else []

    task_sheet = settings.get("taskSheet", {}) if isinstance(settings.get("taskSheet"), dict) else {}
    updated["task_sheet"] = {
        "sheet_id": str(task_sheet.get("sheet_id") or task_sheet.get("sheetId") or "")[:160],
        "gid": str(task_sheet.get("gid") or "0")[:40],
    }

    homework_sheet = settings.get("homeworkSheet", {}) if isinstance(settings.get("homeworkSheet"), dict) else {}
    updated["homework_sheet"] = {
        "sheet_id": str(homework_sheet.get("sheet_id") or homework_sheet.get("sheetId") or "")[:160],
        "gid": str(homework_sheet.get("gid") or "0")[:40],
    }

    weather = settings.get("weather", {}) if isinstance(settings.get("weather"), dict) else {}
    existing_weather = config.get("weather", DEFAULT_CONFIG["weather"])
    updated["weather"] = {
        "label": str(weather.get("label") or existing_weather.get("label") or "Home")[:80],
        "latitude": coerce_float(weather.get("latitude"), float(existing_weather.get("latitude", 28.176856))),
        "longitude": coerce_float(weather.get("longitude"), float(existing_weather.get("longitude", -82.67127))),
    }
    return updated


def coerce_datetime(value: Any, tz: ZoneInfo) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.combine(value, datetime.min.time())

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def fetch_calendar_events(config: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    tz = ZoneInfo(config.get("timezone", "America/New_York"))
    now = datetime.now(tz)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    horizon = day_start + timedelta(days=int(config.get("days_ahead", 1)))
    events: list[dict[str, Any]] = []
    errors: list[str] = []

    for event_config in config.get("events", []):
        start_value = event_config.get("start")
        if not start_value:
            continue

        start = datetime.fromisoformat(start_value).astimezone(tz)
        end_value = event_config.get("end", start_value)
        end = datetime.fromisoformat(end_value).astimezone(tz)
        if not event_overlaps_range(start, end, day_start, horizon):
            continue

        events.append(
            {
                "title": event_config.get("title", "Untitled event"),
                "calendar": event_config.get("calendar", "Calendar"),
                "color": event_config.get("color", "#2f7d6d"),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "allDay": bool(event_config.get("allDay", False)),
                "location": event_config.get("location", ""),
                "leaveBy": event_config.get("leaveBy", ""),
                "travelMinutes": event_config.get("travelMinutes"),
            }
        )

    for calendar_config in config.get("calendars", []):
        if calendar_config.get("provider") == "google_api":
            try:
                weather_cfg = config.get("weather", {})
                events.extend(fetch_google_calendar_events(
                    calendar_config, tz, day_start, horizon,
                    home_lat=weather_cfg.get("latitude"),
                    home_lon=weather_cfg.get("longitude"),
                    travel_buffer=int(config.get("travel_buffer_minutes", 10)),
                ))
            except Exception as exc:
                name = calendar_config.get("name", "Google Calendar")
                errors.append(f"{name}: {exc}")
            continue

        url = normalize_calendar_url(calendar_config)
        if not url or "YOUR_PRIVATE_ICAL_URL" in url:
            continue

        color = calendar_config.get("color", "#2f7d6d")
        name = calendar_config.get("name", "Calendar")
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            calendar = Calendar.from_ical(response.text)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                errors.append(f"{name}: calendar feed is not public or the iCal URL is not valid")
            else:
                errors.append(f"{name}: {exc}")
            continue
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            continue

        for component in recurring_ical_events.of(calendar).between(day_start, horizon):
            if component.name != "VEVENT":
                continue

            raw_start = component.decoded("DTSTART")
            start = coerce_datetime(raw_start, tz)
            end = coerce_datetime(component.decoded("DTEND", raw_start), tz)
            if not event_overlaps_range(start, end, day_start, horizon):
                continue

            events.append(
                {
                    "title": str(component.get("SUMMARY", "Untitled event")),
                    "calendar": name,
                    "color": color,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "allDay": not isinstance(raw_start, datetime),
                }
            )

    return sorted(events, key=lambda event: event["start"])[:60], "; ".join(errors) or None


def fetch_google_calendar_events(
    calendar_config: dict[str, Any],
    tz: ZoneInfo,
    day_start: datetime,
    horizon: datetime,
    home_lat: float | None = None,
    home_lon: float | None = None,
    travel_buffer: int = 10,
) -> list[dict[str, Any]]:
    token_path = Path(calendar_config.get("token_path", APP_DIR / "google-token.json"))
    credentials_path = Path(calendar_config.get("credentials_path", APP_DIR / "google-credentials.json"))
    calendar_id = calendar_config.get("id") or calendar_config.get("calendar_id") or "primary"
    name = calendar_config.get("name", "Google Calendar")
    color = calendar_config.get("color", "#2f7d6d")

    if not token_path.exists():
        raise FileNotFoundError(f"missing OAuth token file: {token_path}")

    creds = Credentials.from_authorized_user_file(str(token_path), GOOGLE_CALENDAR_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        token_path.write_text(creds.to_json(), encoding="utf-8")
    if not creds.valid:
        raise RuntimeError("OAuth token is invalid; rerun the Google Calendar auth helper")

    if not credentials_path.exists() and not creds.refresh_token:
        raise FileNotFoundError(f"missing OAuth client credentials file: {credentials_path}")

    session = AuthorizedSession(creds)
    response = session.get(
        f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events",
        params={
            "timeMin": day_start.isoformat(),
            "timeMax": horizon.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 60,
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()

    events = []
    for item in payload.get("items", []):
        raw_start = item.get("start", {})
        raw_end = item.get("end", raw_start)
        start = parse_google_event_time(raw_start, tz)
        end = parse_google_event_time(raw_end, tz)
        if not event_overlaps_range(start, end, day_start, horizon):
            continue

        location = item.get("location", "")
        leave_by = ""
        travel_minutes = None
        all_day = "date" in raw_start

        if location and not all_day and home_lat is not None and home_lon is not None:
            coords = geocode_address(location)
            if coords:
                mins = fetch_driving_minutes(home_lat, home_lon, coords[0], coords[1])
                if mins is not None:
                    travel_minutes = mins
                    leave_dt = start - timedelta(minutes=mins + travel_buffer)
                    leave_by = leave_dt.strftime("%I:%M %p").lstrip("0")

        events.append(
            {
                "title": item.get("summary", "Untitled event"),
                "calendar": name,
                "color": color,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "allDay": all_day,
                "location": location,
                "leaveBy": leave_by,
                "travelMinutes": travel_minutes,
            }
        )

    return events


def geocode_address(address: str) -> tuple[float, float] | None:
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "HomeNote/1.0"},
            timeout=5,
        )
        results = resp.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception:
        pass
    return None


def fetch_driving_minutes(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> int | None:
    try:
        resp = requests.get(
            f"http://router.project-osrm.org/route/v1/driving/{from_lon},{from_lat};{to_lon},{to_lat}",
            params={"overview": "false"},
            timeout=5,
        )
        data = resp.json()
        if data.get("code") == "Ok" and data.get("routes"):
            return max(1, round(data["routes"][0]["duration"] / 60))
    except Exception:
        pass
    return None


def parse_google_event_time(value: dict[str, str], tz: ZoneInfo) -> datetime:
    if value.get("dateTime"):
        dt = datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00"))
        return dt.astimezone(tz)
    if value.get("date"):
        return datetime.fromisoformat(value["date"]).replace(tzinfo=tz)
    return datetime.now(tz)


def event_overlaps_range(start: datetime, end: datetime, range_start: datetime, range_end: datetime) -> bool:
    return start < range_end and end > range_start


def normalize_calendar_url(calendar_config: dict[str, Any]) -> str:
    url = calendar_config.get("url", "").strip()
    calendar_id = calendar_config.get("id", "").strip()
    if calendar_id:
        return f"https://calendar.google.com/calendar/ical/{quote(calendar_id, safe='')}/public/basic.ics"

    parsed = urlparse(url)
    if "calendar.google.com" in parsed.netloc and parsed.path.endswith("/calendar/embed"):
        src = parse_qs(parsed.query).get("src", [""])[0]
        if src:
            return f"https://calendar.google.com/calendar/ical/{quote(src, safe='')}/public/basic.ics"

    return url


DONE_STATUSES = {"done", "complete", "completed", "finished", "closed", "true", "yes"}
DEFAULT_NEWS_RSS_URL = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"


def parse_sheet_date(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def build_sheet_csv_url(sheet_config: dict[str, Any]) -> str:
    url = sheet_config.get("csv_url")
    if url:
        return url
    if not sheet_config.get("sheet_id"):
        return ""

    sheet_id = sheet_config["sheet_id"]
    gid = sheet_config.get("gid", "0")
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def fetch_sheet_items(config: dict[str, Any], sheet_config: dict[str, Any], id_prefix: str) -> list[dict[str, Any]]:
    tz = ZoneInfo(config.get("timezone", "America/New_York"))
    today = datetime.now(tz).date()
    url = build_sheet_csv_url(sheet_config)
    if not url:
        return []

    response = requests.get(url, timeout=15)
    response.raise_for_status()
    rows = csv.DictReader(io.StringIO(response.text))
    items = []

    for index, row in enumerate(rows):
        normalized = {key.strip().lower(): (value or "").strip() for key, value in row.items() if key}
        title = normalized.get("task") or normalized.get("homework") or normalized.get("title") or normalized.get("name")
        if not title:
            continue

        status = normalized.get("status", "")

        start = normalized.get("start date") or normalized.get("start")
        due = normalized.get("due date") or normalized.get("due") or normalized.get("date")
        start_date = parse_sheet_date(start)
        due_date = parse_sheet_date(due)
        if start_date and today < start_date.date():
            continue
        if due_date and today > due_date.date():
            continue

        priority = (normalized.get("priority") or "normal").lower()
        items.append(
            {
                "id": f"{id_prefix}-{index}",
                "title": title,
                "due": due,
                "owner": normalized.get("owner") or normalized.get("child") or normalized.get("assigned to") or "",
                "done": status.lower() in DONE_STATUSES,
                "status": status or "Not Started",
                "priority": "high" if priority in {"high", "urgent"} else "normal",
                "sortDate": due_date.isoformat() if due_date else "",
            }
        )

    return sorted(items, key=lambda item: (item["sortDate"] or "9999-12-31", item["title"].lower()))


def fetch_sheet_tasks(config: dict[str, Any]) -> list[dict[str, Any]]:
    return fetch_sheet_items(config, config.get("task_sheet", {}), "sheet")


def normalize_tasks(config: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = []
    for index, task in enumerate(config.get("tasks", [])):
        if isinstance(task, str):
            task = {"title": task}
        if not task.get("title"):
            continue
        tasks.append(
            {
                "id": task.get("id", index),
                "title": task["title"],
                "due": task.get("due"),
                "owner": task.get("owner", ""),
                "done": bool(task.get("done", False)),
                "status": task.get("status", "Done" if task.get("done") else "Not Started"),
                "priority": task.get("priority", "normal"),
            }
        )
    return tasks + fetch_sheet_tasks(config)


def fetch_homework(config: dict[str, Any]) -> list[dict[str, Any]]:
    return fetch_sheet_items(config, config.get("homework_sheet", {}), "homework")


def fetch_weather(config: dict[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], str | None]:
    weather_config = config.get("weather", {})
    latitude = weather_config.get("latitude", 28.176856)
    longitude = weather_config.get("longitude", -82.67127)
    tz_name = config.get("timezone", "America/New_York")
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz).replace(minute=0, second=0, microsecond=0)
    end = now + timedelta(hours=12)

    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "temperature_2m,precipitation_probability,weather_code,is_day,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "timezone": tz_name,
            "forecast_days": 7,
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    temperatures = hourly.get("temperature_2m", [])
    rain_chances = hourly.get("precipitation_probability", [])
    weather_codes = hourly.get("weather_code", [])
    is_day_values = hourly.get("is_day", [])
    wind_speeds = hourly.get("wind_speed_10m", [])
    daily = payload.get("daily", {})
    sunrise_hours = {
        datetime.fromisoformat(value).replace(tzinfo=tz).replace(minute=0, second=0, microsecond=0)
        for value in daily.get("sunrise", [])
        if value
    }
    sunset_hours = {
        datetime.fromisoformat(value).replace(tzinfo=tz).replace(minute=0, second=0, microsecond=0)
        for value in daily.get("sunset", [])
        if value
    }
    hourly_forecast = []

    for index, time_value in enumerate(times):
        hour = datetime.fromisoformat(time_value).replace(tzinfo=tz)
        if hour < now or hour >= end:
            continue

        temperature = round(float(temperatures[index]))
        rain_chance = int(rain_chances[index] if rain_chances[index] is not None else 0)
        weather_code = int(weather_codes[index] if index < len(weather_codes) and weather_codes[index] is not None else 0)
        is_day = bool(is_day_values[index] if index < len(is_day_values) else True)
        wind_speed = float(wind_speeds[index] if index < len(wind_speeds) and wind_speeds[index] is not None else 0)
        condition = classify_weather_condition(
            weather_code=weather_code,
            temperature=temperature,
            wind_speed=wind_speed,
            is_day=is_day,
            is_sunrise=hour in sunrise_hours,
            is_sunset=hour in sunset_hours,
        )

        hourly_forecast.append(
            {
                "time": hour.isoformat(),
                "temperature": temperature,
                "rainChance": rain_chance,
                "weatherCode": weather_code,
                "windSpeed": round(wind_speed),
                "condition": condition["label"],
                "conditionKey": condition["key"],
                "icon": condition["icon"],
            }
        )
        if len(hourly_forecast) >= 12:
            break

    daily_forecast = []
    daily_times = daily.get("time", [])
    daily_codes = daily.get("weather_code", [])
    daily_highs = daily.get("temperature_2m_max", [])
    daily_lows = daily.get("temperature_2m_min", [])
    daily_rain = daily.get("precipitation_probability_max", [])

    for index, date_value in enumerate(daily_times[:7]):
        high = round(float(daily_highs[index])) if index < len(daily_highs) and daily_highs[index] is not None else None
        low = round(float(daily_lows[index])) if index < len(daily_lows) and daily_lows[index] is not None else None
        weather_code = int(daily_codes[index] if index < len(daily_codes) and daily_codes[index] is not None else 0)
        rain_chance = int(daily_rain[index] if index < len(daily_rain) and daily_rain[index] is not None else 0)
        condition = classify_weather_condition(
            weather_code=weather_code,
            temperature=high or 70,
            wind_speed=0,
            is_day=True,
            is_sunrise=False,
            is_sunset=False,
        )
        daily_forecast.append(
            {
                "date": datetime.fromisoformat(date_value).replace(tzinfo=tz).isoformat(),
                "high": high,
                "low": low,
                "rainChance": rain_chance,
                "weatherCode": weather_code,
                "condition": condition["label"],
                "conditionKey": condition["key"],
                "icon": condition["icon"],
            }
        )

    return {"hourly": hourly_forecast, "daily": daily_forecast}, None


def classify_weather_condition(
    weather_code: int,
    temperature: int,
    wind_speed: float,
    is_day: bool,
    is_sunrise: bool,
    is_sunset: bool,
) -> dict[str, str]:
    if is_sunrise:
        return {"key": "sunrise", "label": "Sunrise", "icon": "sunrise"}
    if is_sunset:
        return {"key": "sunset", "label": "Sunset", "icon": "sunset"}

    if weather_code in {95}:
        return {"key": "thunderstorm", "label": "Thunderstorm", "icon": "storm"}
    if weather_code in {96, 99}:
        return {"key": "hail", "label": "Hail", "icon": "hail"}
    if weather_code in {80, 81}:
        return {"key": "showers" if is_day else "rainy-night", "label": "Showers" if is_day else "Rainy Night", "icon": "rain"}
    if weather_code == 82:
        return {"key": "heavy-rain", "label": "Heavy Rain", "icon": "heavy-rain"}
    if weather_code in {61, 63}:
        return {"key": "rain" if is_day else "rainy-night", "label": "Rain" if is_day else "Rainy Night", "icon": "rain"}
    if weather_code == 65:
        return {"key": "heavy-rain", "label": "Heavy Rain", "icon": "heavy-rain"}
    if weather_code in {51, 53, 55}:
        return {"key": "light-rain", "label": "Light Rain / Drizzle", "icon": "drizzle"}
    if weather_code in {56, 57, 66, 67}:
        return {"key": "freezing-rain", "label": "Freezing Rain", "icon": "freezing-rain"}
    if weather_code in {85, 86}:
        return {"key": "snowy-night" if not is_day else "snow", "label": "Snowy Night" if not is_day else "Snow", "icon": "snow"}
    if weather_code == 71:
        return {"key": "light-snow", "label": "Light Snow", "icon": "light-snow"}
    if weather_code == 73:
        return {"key": "snowy-night" if not is_day else "snow", "label": "Snowy Night" if not is_day else "Snow", "icon": "snow"}
    if weather_code == 75:
        return {"key": "heavy-snow", "label": "Heavy Snow", "icon": "heavy-snow"}
    if weather_code == 77:
        return {"key": "sleet", "label": "Sleet", "icon": "sleet"}
    if weather_code in {45, 48}:
        return {"key": "fog", "label": "Fog", "icon": "fog"}

    if temperature >= 95:
        return {"key": "hot", "label": "Hot / Heat", "icon": "hot"}
    if temperature <= 32:
        return {"key": "cold", "label": "Cold / Freeze", "icon": "cold"}
    if wind_speed >= 25:
        return {"key": "windy", "label": "Windy", "icon": "wind"}

    if weather_code == 0:
        return {"key": "sunny" if is_day else "clear-night", "label": "Sunny / Clear" if is_day else "Moon / Clear Night", "icon": "sun" if is_day else "moon"}
    if weather_code == 1:
        return {"key": "mostly-sunny" if is_day else "clear-night", "label": "Mostly Sunny" if is_day else "Moon / Clear Night", "icon": "mostly-sunny" if is_day else "moon"}
    if weather_code == 2:
        return {"key": "partly-cloudy" if is_day else "cloudy-night", "label": "Partly Cloudy" if is_day else "Cloudy Night", "icon": "partly-cloudy" if is_day else "cloudy-night"}
    if weather_code == 3:
        return {"key": "cloudy" if is_day else "cloudy-night", "label": "Cloudy / Overcast" if is_day else "Cloudy Night", "icon": "cloud" if is_day else "cloudy-night"}

    return {"key": "cloudy", "label": "Cloudy / Overcast", "icon": "cloud"}


def fetch_news(config: dict[str, Any]) -> list[dict[str, str]]:
    news_config = config.get("news", {})
    rss_url = news_config.get("rss_url", DEFAULT_NEWS_RSS_URL)
    limit = int(news_config.get("limit", 12))
    tz = ZoneInfo(config.get("timezone", "America/New_York"))
    today = datetime.now(tz).date()

    response = requests.get(
        rss_url,
        timeout=15,
        headers={"User-Agent": "HomeNote/1.0"},
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)
    headlines = []

    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        published_text = (item.findtext("pubDate") or "").strip()
        if not title or not published_text:
            continue

        try:
            published = parsedate_to_datetime(published_text).astimezone(tz)
        except (TypeError, ValueError):
            continue

        if published.date() != today:
            continue

        headlines.append(
            {
                "title": title,
                "link": link,
                "published": published.isoformat(),
                "source": (item.findtext("source") or "News").strip(),
                "topic": (item.findtext("category") or item.findtext("source") or "Today").strip(),
                "image": extract_news_image(item),
            }
        )
        if len(headlines) >= limit:
            break

    return headlines


def extract_news_image(item: ET.Element) -> str:
    for child in item:
        tag = child.tag.rsplit("}", 1)[-1].lower()
        url = child.attrib.get("url", "")
        if tag in {"content", "thumbnail"} and url:
            return url
        if tag == "enclosure" and child.attrib.get("type", "").startswith("image/") and url:
            return url

    text = " ".join(
        value or ""
        for value in [
            item.findtext("description"),
            item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded"),
        ]
    )
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', text, flags=re.IGNORECASE)
    return unescape(match.group(1)) if match else ""


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/dashboard")
def dashboard():
    config = load_config()
    try:
        events, calendar_error = fetch_calendar_events(config)
    except Exception as exc:  # Keep the TV usable if one feed fails.
        events = []
        calendar_error = str(exc)

    try:
        tasks = normalize_tasks(config)
        task_error = None
    except Exception as exc:
        tasks = config.get("tasks", [])
        task_error = str(exc)

    try:
        homework = fetch_homework(config)
        homework_error = None
    except Exception as exc:
        homework = []
        homework_error = str(exc)

    try:
        weather, weather_error = fetch_weather(config)
    except Exception as exc:
        weather = []
        weather_error = str(exc)

    try:
        news = fetch_news(config)
        news_error = None
    except Exception as exc:
        news = []
        news_error = str(exc)

    return jsonify(
        {
            "title": config.get("title", "HomeNote"),
            "timezone": config.get("timezone", "America/New_York"),
            "now": datetime.now(timezone.utc).isoformat(),
            "events": events,
            "tasks": tasks,
            "homework": homework,
            "weather": weather,
            "news": news,
            "calendarError": calendar_error,
            "taskError": task_error,
            "homeworkError": homework_error,
            "weatherError": weather_error,
            "newsError": news_error,
        }
    )


@app.get("/api/notes")
def get_notes():
    notes, version = load_notes()
    return jsonify({"notes": notes, "version": version})


@app.put("/api/notes")
def put_notes():
    payload = request.get_json(silent=True) or {}
    notes = payload.get("notes", [])
    if not isinstance(notes, list):
        return jsonify({"error": "notes must be a list"}), 400

    version = save_notes(notes)
    return jsonify({"notes": notes, "version": version})


@app.get("/api/settings")
def get_settings():
    return jsonify(public_settings(load_config()))


@app.put("/api/settings")
def put_settings():
    payload = request.get_json(silent=True) or {}
    config = load_config()
    updated = apply_public_settings(config, payload)
    save_config(updated)
    return jsonify(public_settings(updated))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8765")))
