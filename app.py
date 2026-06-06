from __future__ import annotations

import csv
from email.utils import parsedate_to_datetime
import io
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import recurring_ical_events
import requests
from flask import Flask, jsonify, render_template
from icalendar import Calendar
from zoneinfo import ZoneInfo


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.environ.get("HOMENOTE_CONFIG", APP_DIR / "config.json"))

app = Flask(__name__)


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {
            "timezone": "America/New_York",
            "title": "HomeNote",
            "calendars": [],
            "tasks": [],
        }

    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def coerce_datetime(value: Any, tz: ZoneInfo) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.combine(value, datetime.min.time())

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def fetch_calendar_events(config: dict[str, Any]) -> list[dict[str, Any]]:
    tz = ZoneInfo(config.get("timezone", "America/New_York"))
    now = datetime.now(tz)
    horizon = now + timedelta(days=int(config.get("days_ahead", 14)))
    events: list[dict[str, Any]] = []

    for event_config in config.get("events", []):
        start_value = event_config.get("start")
        if not start_value:
            continue

        start = datetime.fromisoformat(start_value).astimezone(tz)
        end_value = event_config.get("end", start_value)
        end = datetime.fromisoformat(end_value).astimezone(tz)
        if end < now or start > horizon:
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
        url = calendar_config.get("url")
        if not url or "YOUR_PRIVATE_ICAL_URL" in url:
            continue

        response = requests.get(url, timeout=15)
        response.raise_for_status()
        calendar = Calendar.from_ical(response.text)
        color = calendar_config.get("color", "#2f7d6d")
        name = calendar_config.get("name", "Calendar")

        for component in recurring_ical_events.of(calendar).between(now, horizon):
            if component.name != "VEVENT":
                continue

            raw_start = component.decoded("DTSTART")
            start = coerce_datetime(raw_start, tz)
            end = coerce_datetime(component.decoded("DTEND", raw_start), tz)
            if end < now:
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

    return sorted(events, key=lambda event: event["start"])[:60]


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


def fetch_weather(config: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
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
            "daily": "sunrise,sunset",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "timezone": tz_name,
            "forecast_days": 2,
        },
        timeout=15,
    )
    response.raise_for_status()
    hourly = response.json().get("hourly", {})
    times = hourly.get("time", [])
    temperatures = hourly.get("temperature_2m", [])
    rain_chances = hourly.get("precipitation_probability", [])
    weather_codes = hourly.get("weather_code", [])
    is_day_values = hourly.get("is_day", [])
    wind_speeds = hourly.get("wind_speed_10m", [])
    daily = response.json().get("daily", {})
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
    forecast = []

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

        forecast.append(
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
        if len(forecast) >= 12:
            break

    return forecast, None


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
            }
        )
        if len(headlines) >= limit:
            break

    return headlines


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/dashboard")
def dashboard():
    config = load_config()
    try:
        events = fetch_calendar_events(config)
        calendar_error = None
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8765")))
