const state = {
  timezone: "America/New_York",
  backgroundIndex: 0,
  notes: [],
  selectedNoteId: null,
  noteColor: "#fff2a8",
  noteZ: 10,
  notesVersion: 0,
  notesSaveTimer: null,
  notesInteracting: false,
  newsHeadlines: [],
  newsIndex: 0,
  newsTimer: null,
};

const backgrounds = [
  "/static/backgrounds/morning-pond.png",
  "/static/backgrounds/kitchen-garden.png",
  "/static/backgrounds/evening-patio.png",
];

function formatDateTime(value, options) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: state.timezone,
    ...options,
  }).format(new Date(value));
}

function sameDay(a, b) {
  return formatDateTime(a, { dateStyle: "short" }) === formatDateTime(b, { dateStyle: "short" });
}

function updateClock() {
  const now = new Date();
  document.getElementById("clock").textContent = new Intl.DateTimeFormat("en-US", {
    timeZone: state.timezone,
    hour: "numeric",
    minute: "2-digit",
  }).format(now);
  document.getElementById("date").textContent = new Intl.DateTimeFormat("en-US", {
    timeZone: state.timezone,
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(now);
}

function renderEvents(events) {
  const container = document.getElementById("events");
  const count = document.getElementById("event-count");
  count.textContent = `${events.length} event${events.length === 1 ? "" : "s"}`;

  if (!events.length) {
    container.innerHTML = '<div class="empty">No upcoming calendar events.</div>';
    return;
  }

  container.innerHTML = events
    .slice(0, 6)
    .map((event) => {
      const start = new Date(event.start);
      const end = new Date(event.end);
      const when = event.allDay
        ? formatDateTime(start, { weekday: "short", month: "short", day: "numeric" })
        : `${formatDateTime(start, { weekday: "short", hour: "numeric", minute: "2-digit" })} - ${formatDateTime(end, { hour: "numeric", minute: "2-digit" })}`;
      const today = sameDay(start, new Date()) ? "Today" : formatDateTime(start, { month: "short", day: "numeric" });
      const leaveBy = event.leaveBy
        ? `<p class="leave">Leave by ${escapeHtml(event.leaveBy)}${event.travelMinutes ? ` &middot; ${escapeHtml(event.travelMinutes)} min drive` : ""}</p>`
        : "";

      return `
        <article class="event">
          <div class="event-rail" style="background:${event.color}"></div>
          <div class="event-date">${today}</div>
          <div class="event-main">
            <h3>${escapeHtml(event.title)}</h3>
            <p>${escapeHtml(when)} &middot; ${escapeHtml(event.calendar)}</p>
            ${leaveBy}
          </div>
        </article>
      `;
    })
    .join("");
}

function renderTasks(tasks) {
  document.getElementById("task-count").textContent = `${tasks.length} active`;
  const container = document.getElementById("tasks");
  renderTaskList(container, tasks, "No active tasks.", 5);
}

function renderHomework(homework) {
  document.getElementById("homework-count").textContent = `${homework.length} due`;
  const container = document.getElementById("homework");
  renderTaskList(container, homework, "No homework due.", 4);
}

function renderTaskList(container, items, emptyMessage, limit) {
  if (!items.length) {
    container.innerHTML = `<div class="empty">${escapeHtml(emptyMessage)}</div>`;
    return;
  }

  container.innerHTML = items
    .slice(0, limit)
    .map((item) => {
      const priority = item.priority === "high" ? " high" : "";
      const statusClass = statusToClass(item.status, item.done);
      return `
        <article class="task${priority} ${statusClass}">
          <div class="check"></div>
          <div>
            <div class="task-title-row">
              <h3>${escapeHtml(item.title)}</h3>
              <span class="task-status">${escapeHtml(item.status || (item.done ? "Completed" : "Not Started"))}</span>
            </div>
            <p>${escapeHtml([item.due, item.owner].filter(Boolean).join(" - "))}</p>
          </div>
        </article>
      `;
    })
    .join("");
}

function statusToClass(status, done) {
  const value = String(status || "").toLowerCase();
  if (done || ["done", "complete", "completed", "finished", "closed", "true", "yes"].includes(value)) {
    return "status-completed";
  }
  if (value === "in progress" || value === "in-progress" || value.startsWith("in progres") || value === "started") {
    return "status-progress";
  }
  return "status-open";
}

function renderWeather(weather) {
  const container = document.getElementById("weather");
  const hours = Array.isArray(weather) ? weather : weather?.hourly || [];
  const days = Array.isArray(weather?.daily) ? weather.daily : [];
  if (!hours.length) {
    container.innerHTML = '<div class="empty">Weather unavailable.</div>';
    return;
  }

  const hourly = hours
    .map((hour, index) => {
      const label = index === 0 ? "Now" : formatDateTime(hour.time, { hour: "numeric" });
      const condition = hour.condition || "Cloudy / Overcast";
      return `
        <article class="weather-hour condition-${escapeClass(hour.conditionKey || "cloudy")}">
          <p class="weather-time">${escapeHtml(label)}</p>
          <div class="weather-main">
            <span class="weather-icon" title="${escapeHtml(condition)}" aria-label="${escapeHtml(condition)}">
              ${weatherIcon(hour.icon || "cloud")}
            </span>
            <h3>${escapeHtml(hour.temperature)}&deg;</h3>
          </div>
          <p class="rain">${escapeHtml(hour.rainChance)}% rain</p>
        </article>
      `;
    })
    .join("");

  const daily = days
    .map((day, index) => {
      const label = index === 0 ? "Today" : formatDateTime(day.date, { weekday: "short" });
      const condition = day.condition || "Cloudy / Overcast";
      const high = day.high ?? "--";
      const low = day.low ?? "--";
      return `
        <article class="weather-day condition-${escapeClass(day.conditionKey || "cloudy")}">
          <p class="weather-time">${escapeHtml(label)}</p>
          <div class="weather-main">
            <span class="weather-icon" title="${escapeHtml(condition)}" aria-label="${escapeHtml(condition)}">
              ${weatherIcon(day.icon || "cloud")}
            </span>
            <h3>${escapeHtml(high)}&deg;<span>/${escapeHtml(low)}&deg;</span></h3>
          </div>
          <p class="rain">${escapeHtml(day.rainChance ?? 0)}% rain</p>
        </article>
      `;
    })
    .join("");

  container.innerHTML = `
    <div class="weather-group">
      <p class="weather-section-label">Hourly</p>
      <div class="weather-hourly">${hourly}</div>
    </div>
    <div class="weather-vsep"></div>
    <div class="weather-group">
      <p class="weather-section-label">Next 7 Days</p>
      <div class="weather-daily">${daily}</div>
    </div>
  `;
}

function weatherIcon(name) {
  const icons = {
    sun: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1"></path></svg>`,
    "mostly-sunny": `<svg viewBox="0 0 24 24"><circle cx="8" cy="8" r="3.2"></circle><path d="M8 2.5v2M8 11.5v2M2.5 8h2M11.5 8h2M4.1 4.1l1.4 1.4M10.5 10.5l1.4 1.4M4.1 11.9l1.4-1.4M10.5 5.5l1.4-1.4M9 18h8.5a3.5 3.5 0 0 0 .4-7 5.5 5.5 0 0 0-10.5 2"></path></svg>`,
    "partly-cloudy": `<svg viewBox="0 0 24 24"><circle cx="8" cy="8" r="3"></circle><path d="M8 2.5v2M2.5 8h2M4 4l1.4 1.4M12 12.5A5 5 0 0 1 21.5 15a3.5 3.5 0 0 1-3.5 3.5H8.5a4 4 0 1 1 1-7.9"></path></svg>`,
    cloud: `<svg viewBox="0 0 24 24"><path d="M6.5 18h11a4 4 0 0 0 .5-8 6 6 0 0 0-11.3 2A3 3 0 0 0 6.5 18Z"></path></svg>`,
    rain: `<svg viewBox="0 0 24 24"><path d="M6.5 14.5h11a4 4 0 0 0 .5-8 6 6 0 0 0-11.3 2A3 3 0 0 0 6.5 14.5Z"></path><path d="M8 18l-1 2M12 18l-1 2M16 18l-1 2"></path></svg>`,
    drizzle: `<svg viewBox="0 0 24 24"><path d="M6.5 14.5h11a4 4 0 0 0 .5-8 6 6 0 0 0-11.3 2A3 3 0 0 0 6.5 14.5Z"></path><path d="M9 18v1.5M13 18v1.5M17 18v1.5"></path></svg>`,
    "heavy-rain": `<svg viewBox="0 0 24 24"><path d="M6.5 13.5h11a4 4 0 0 0 .5-8 6 6 0 0 0-11.3 2A3 3 0 0 0 6.5 13.5Z"></path><path d="M7 17l-1.4 3M11 17l-1.4 3M15 17l-1.4 3M19 17l-1.4 3"></path></svg>`,
    storm: `<svg viewBox="0 0 24 24"><path d="M6.5 13.5h11a4 4 0 0 0 .5-8 6 6 0 0 0-11.3 2A3 3 0 0 0 6.5 13.5Z"></path><path d="M13 14l-3 5h3l-1 4 4-6h-3l2-3"></path></svg>`,
    hail: `<svg viewBox="0 0 24 24"><path d="M6.5 13.5h11a4 4 0 0 0 .5-8 6 6 0 0 0-11.3 2A3 3 0 0 0 6.5 13.5Z"></path><circle cx="8" cy="18" r="1"></circle><circle cx="13" cy="20" r="1"></circle><circle cx="18" cy="18" r="1"></circle></svg>`,
    snow: `<svg viewBox="0 0 24 24"><path d="M6.5 13.5h11a4 4 0 0 0 .5-8 6 6 0 0 0-11.3 2A3 3 0 0 0 6.5 13.5Z"></path><path d="M12 16v6M9.5 17.5l5 3M14.5 17.5l-5 3"></path></svg>`,
    "light-snow": `<svg viewBox="0 0 24 24"><path d="M6.5 14h11a4 4 0 0 0 .5-8 6 6 0 0 0-11.3 2A3 3 0 0 0 6.5 14Z"></path><path d="M10 18v3M14 18v3"></path></svg>`,
    "heavy-snow": `<svg viewBox="0 0 24 24"><path d="M6.5 13h11a4 4 0 0 0 .5-8 6 6 0 0 0-11.3 2A3 3 0 0 0 6.5 13Z"></path><path d="M8 16v5M12 16v5M16 16v5M6.5 18.5h11"></path></svg>`,
    sleet: `<svg viewBox="0 0 24 24"><path d="M6.5 13.5h11a4 4 0 0 0 .5-8 6 6 0 0 0-11.3 2A3 3 0 0 0 6.5 13.5Z"></path><path d="M8 17l-1 2M12 17v2.5M16 17l-1 2"></path><circle cx="19" cy="19" r=".9"></circle></svg>`,
    "freezing-rain": `<svg viewBox="0 0 24 24"><path d="M6.5 13.5h11a4 4 0 0 0 .5-8 6 6 0 0 0-11.3 2A3 3 0 0 0 6.5 13.5Z"></path><path d="M8 17l-1 2M12 16.5v4M10.5 18.5h3M16 17l-1 2"></path></svg>`,
    fog: `<svg viewBox="0 0 24 24"><path d="M6.5 11h11a4 4 0 0 0 .5-8 6 6 0 0 0-11.3 2A3 3 0 0 0 6.5 11Z"></path><path d="M3 15h18M5 18h14M3 21h18"></path></svg>`,
    wind: `<svg viewBox="0 0 24 24"><path d="M3 8h12a3 3 0 1 0-3-3"></path><path d="M3 13h17"></path><path d="M3 18h11a3 3 0 1 1-3 3"></path></svg>`,
    hot: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"></circle><path d="M12 1.5v3M12 19.5v3M4.6 4.6 6.8 6.8M17.2 17.2l2.2 2.2M1.5 12h3M19.5 12h3M4.6 19.4l2.2-2.2M17.2 6.8l2.2-2.2"></path><path d="M17.5 3.5c1.8 1.7 2.8 3.8 3 6.2"></path></svg>`,
    cold: `<svg viewBox="0 0 24 24"><path d="M12 2v20M5 5l14 14M19 5 5 19M3 12h18"></path></svg>`,
    moon: `<svg viewBox="0 0 24 24"><path d="M18.5 15.5A8 8 0 0 1 8.5 5.5 8 8 0 1 0 18.5 15.5Z"></path></svg>`,
    "cloudy-night": `<svg viewBox="0 0 24 24"><path d="M14 5a6 6 0 0 0 4.5 8.8A6.5 6.5 0 1 1 14 5Z"></path><path d="M7 19h10a3.5 3.5 0 0 0 .4-7 5 5 0 0 0-9.5 1.5A2.8 2.8 0 0 0 7 19Z"></path></svg>`,
    sunrise: `<svg viewBox="0 0 24 24"><path d="M3 19h18M5 15a7 7 0 0 1 14 0M12 3v8M8.5 6.5 12 3l3.5 3.5"></path></svg>`,
    sunset: `<svg viewBox="0 0 24 24"><path d="M3 19h18M5 15a7 7 0 0 1 14 0M12 3v8M8.5 7.5 12 11l3.5-3.5"></path></svg>`,
  };
  return icons[name] || icons.cloud;
}

function renderNews(headlines) {
  state.newsHeadlines = headlines;
  state.newsIndex = 0;
  showTickerHeadline();
}

function showTickerHeadline() {
  const container = document.getElementById("news-ticker");
  clearTimeout(state.newsTimer);

  if (!state.newsHeadlines.length) {
    container.innerHTML = '<span class="ticker-item ticker-single">No headlines published yet today.</span>';
    return;
  }

  const headline = state.newsHeadlines[state.newsIndex % state.newsHeadlines.length];
  container.innerHTML = `<span class="ticker-item ticker-single">${escapeHtml(headline.title)}</span>`;
  state.newsIndex += 1;
  state.newsTimer = setTimeout(showTickerHeadline, 22000);
}

async function loadNotes(force = false) {
  if (!force && shouldHoldLocalNotes()) return;

  try {
    const response = await fetch("/api/notes", { cache: "no-store" });
    const payload = await response.json();
    if (!force && payload.version === state.notesVersion) return;

    state.notes = Array.isArray(payload.notes) ? payload.notes : [];
    state.notesVersion = payload.version || 0;
    state.noteZ = state.notes.reduce((max, note) => Math.max(max, note.z || 10), 10);
    renderNotes();
  } catch (error) {
    console.warn("Unable to sync sticky notes", error);
  }
}

function createNoteData(overrides = {}) {
  return {
    id: overrides.id || `note-${Date.now()}-${Math.round(Math.random() * 10000)}`,
    x: overrides.x ?? 48,
    y: overrides.y ?? 48,
    width: overrides.width ?? 250,
    height: overrides.height ?? 170,
    color: overrides.color || state.noteColor,
    text: overrides.text || "",
    z: overrides.z || ++state.noteZ,
  };
}

function saveNotes(delay = 250) {
  clearTimeout(state.notesSaveTimer);
  state.notesSaveTimer = setTimeout(flushNotes, delay);
}

async function flushNotes() {
  clearTimeout(state.notesSaveTimer);
  state.notesSaveTimer = null;

  try {
    const response = await fetch("/api/notes", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes: state.notes }),
    });
    const payload = await response.json();
    if (Array.isArray(payload.notes)) {
      state.notes = payload.notes;
    }
    state.notesVersion = payload.version || state.notesVersion;
    state.noteZ = state.notes.reduce((max, note) => Math.max(max, note.z || 10), state.noteZ);
  } catch (error) {
    console.warn("Unable to save sticky notes", error);
  }
}

function shouldHoldLocalNotes() {
  const activeNote = document.activeElement?.closest?.(".sticky-note");
  return state.notesInteracting || Boolean(activeNote);
}

function renderNotes() {
  const canvas = document.getElementById("notes-canvas");
  if (!canvas) return;
  canvas.innerHTML = state.notes.map(noteTemplate).join("");
  for (const element of canvas.querySelectorAll(".sticky-note")) {
    bindNote(element);
  }
}

function noteTemplate(note) {
  const selected = note.id === state.selectedNoteId ? " selected" : "";
  return `
    <article class="sticky-note${selected}" data-note-id="${escapeHtml(note.id)}" style="--note-color:${escapeHtml(note.color)}; left:${note.x}px; top:${note.y}px; width:${note.width}px; height:${note.height}px; z-index:${note.z || 10};">
      <div class="note-grip">
        <span></span>
        <span></span>
      </div>
      <div class="note-body" contenteditable="true" spellcheck="true">${escapeHtml(note.text)}</div>
      <div class="note-resize" title="Resize" aria-hidden="true"></div>
    </article>
  `;
}

function bindNote(element) {
  const noteId = element.dataset.noteId;
  const body = element.querySelector(".note-body");
  const grip = element.querySelector(".note-grip");
  const resize = element.querySelector(".note-resize");

  element.addEventListener("pointerdown", () => selectNote(noteId, false));
  body.addEventListener("input", () => {
    const note = findNote(noteId);
    if (!note) return;
    note.text = body.innerText;
    saveNotes();
  });
  grip.addEventListener("pointerdown", (event) => startDrag(event, noteId));
  resize.addEventListener("pointerdown", (event) => startResize(event, noteId));
}

function findNote(noteId) {
  return state.notes.find((note) => note.id === noteId);
}

function selectNote(noteId, shouldRender = true) {
  const note = findNote(noteId);
  if (!note) return;
  state.selectedNoteId = noteId;
  note.z = ++state.noteZ;
  state.noteColor = note.color;
  syncSwatches();
  saveNotes();
  if (shouldRender) {
    renderNotes();
  } else {
    document.querySelectorAll(".sticky-note").forEach((item) => {
      item.classList.toggle("selected", item.dataset.noteId === noteId);
    });
    updateNoteElement(note);
  }
}

function addNote() {
  const canvas = document.getElementById("notes-canvas");
  if (!canvas) return;
  const offset = Math.min(state.notes.length * 18, 140);
  const note = createNoteData({
    x: Math.max(24, Math.min(74 + offset, canvas.clientWidth - 280)),
    y: Math.max(88, Math.min(118 + offset, canvas.clientHeight - 190)),
  });
  state.notes.push(note);
  state.selectedNoteId = note.id;
  saveNotes();
  renderNotes();
  focusSelectedNote();
}

function deleteSelectedNote() {
  if (!state.selectedNoteId) return;
  state.notes = state.notes.filter((note) => note.id !== state.selectedNoteId);
  state.selectedNoteId = state.notes.at(-1)?.id || null;
  saveNotes();
  renderNotes();
}

function focusSelectedNote() {
  requestAnimationFrame(() => {
    const note = document.querySelector(`[data-note-id="${CSS.escape(state.selectedNoteId)}"] .note-body`);
    note?.focus();
  });
}

function setNoteColor(color) {
  state.noteColor = color;
  const note = findNote(state.selectedNoteId);
  if (note) {
    note.color = color;
    saveNotes();
    renderNotes();
  }
  syncSwatches();
}

function syncSwatches() {
  for (const swatch of document.querySelectorAll("[data-note-color]")) {
    swatch.classList.toggle("active", swatch.dataset.noteColor === state.noteColor);
  }
}

function startDrag(event, noteId) {
  event.preventDefault();
  const note = findNote(noteId);
  const canvas = document.getElementById("notes-canvas");
  if (!note || !canvas) return;
  state.notesInteracting = true;
  selectNote(noteId, false);
  const startX = event.clientX;
  const startY = event.clientY;
  const originX = note.x;
  const originY = note.y;
  event.currentTarget.setPointerCapture(event.pointerId);

  const move = (moveEvent) => {
    note.x = clamp(originX + moveEvent.clientX - startX, 0, canvas.clientWidth - note.width);
    note.y = clamp(originY + moveEvent.clientY - startY, 0, canvas.clientHeight - note.height);
    updateNoteElement(note);
  };
  const up = () => {
    state.notesInteracting = false;
    saveNotes(0);
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

function startResize(event, noteId) {
  event.preventDefault();
  const note = findNote(noteId);
  const canvas = document.getElementById("notes-canvas");
  if (!note || !canvas) return;
  state.notesInteracting = true;
  selectNote(noteId, false);
  const startX = event.clientX;
  const startY = event.clientY;
  const originWidth = note.width;
  const originHeight = note.height;
  event.currentTarget.setPointerCapture(event.pointerId);

  const move = (moveEvent) => {
    note.width = clamp(originWidth + moveEvent.clientX - startX, 170, canvas.clientWidth - note.x);
    note.height = clamp(originHeight + moveEvent.clientY - startY, 120, canvas.clientHeight - note.y);
    updateNoteElement(note);
  };
  const up = () => {
    state.notesInteracting = false;
    saveNotes(0);
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

function updateNoteElement(note) {
  const element = document.querySelector(`[data-note-id="${CSS.escape(note.id)}"]`);
  if (!element) return;
  element.style.left = `${note.x}px`;
  element.style.top = `${note.y}px`;
  element.style.width = `${note.width}px`;
  element.style.height = `${note.height}px`;
  element.style.zIndex = note.z;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function toggleNotesMode() {
  const dashboard = document.querySelector(".dashboard");
  const toggle = document.getElementById("notes-toggle");
  const isOpen = dashboard.classList.toggle("notes-open");
  toggle.setAttribute("aria-pressed", String(isOpen));
  if (isOpen) {
    renderNotes();
  }
}

function initNotes() {
  loadNotes();
  document.getElementById("notes-toggle").addEventListener("click", toggleNotesMode);
  document.getElementById("add-note").addEventListener("click", addNote);
  document.getElementById("delete-note").addEventListener("click", deleteSelectedNote);
  for (const swatch of document.querySelectorAll("[data-note-color]")) {
    swatch.style.background = swatch.dataset.noteColor;
    swatch.addEventListener("click", () => setNoteColor(swatch.dataset.noteColor));
  }
  syncSwatches();
}

async function openSettings() {
  const modal = document.getElementById("settings-modal");
  const status = document.getElementById("settings-status");
  modal.hidden = false;
  status.textContent = "Loading...";

  try {
    const response = await fetch("/api/settings", { cache: "no-store" });
    const settings = await response.json();
    fillSettings(settings);
    status.textContent = "";
  } catch (error) {
    status.textContent = `Settings unavailable: ${error.message}`;
  }
}

function closeSettings() {
  document.getElementById("settings-modal").hidden = true;
}

function fillSettings(settings) {
  const form = document.getElementById("settings-form");
  form.elements.title.value = settings.title || "";
  form.elements.timezone.value = settings.timezone || "";
  form.elements.daysAhead.value = settings.daysAhead || 7;
  form.elements.travelBufferMinutes.value = settings.travelBufferMinutes ?? 10;
  form.elements.calendarName.value = settings.calendar?.name || "";
  form.elements.calendarId.value = settings.calendar?.id || "";
  form.elements.calendarProvider.value = settings.calendar?.provider || "google_api";
  form.elements.calendarColor.value = settings.calendar?.color || "#4c91d9";
  form.elements.calendarUrl.value = settings.calendar?.url || "";
  form.elements.taskSheetId.value = settings.taskSheet?.sheet_id || "";
  form.elements.taskGid.value = settings.taskSheet?.gid || "0";
  form.elements.homeworkSheetId.value = settings.homeworkSheet?.sheet_id || "";
  form.elements.homeworkGid.value = settings.homeworkSheet?.gid || "0";
  form.elements.weatherLabel.value = settings.weather?.label || "Home";
  form.elements.latitude.value = settings.weather?.latitude ?? "";
  form.elements.longitude.value = settings.weather?.longitude ?? "";
}

function readSettingsForm() {
  const form = document.getElementById("settings-form");
  return {
    title: form.elements.title.value.trim(),
    timezone: form.elements.timezone.value.trim(),
    daysAhead: Number(form.elements.daysAhead.value || 7),
    travelBufferMinutes: Number(form.elements.travelBufferMinutes.value || 10),
    calendar: {
      name: form.elements.calendarName.value.trim(),
      id: form.elements.calendarId.value.trim(),
      provider: form.elements.calendarProvider.value,
      color: form.elements.calendarColor.value,
      url: form.elements.calendarUrl.value.trim(),
    },
    taskSheet: {
      sheet_id: form.elements.taskSheetId.value.trim(),
      gid: form.elements.taskGid.value.trim() || "0",
    },
    homeworkSheet: {
      sheet_id: form.elements.homeworkSheetId.value.trim(),
      gid: form.elements.homeworkGid.value.trim() || "0",
    },
    weather: {
      label: form.elements.weatherLabel.value.trim(),
      latitude: Number(form.elements.latitude.value),
      longitude: Number(form.elements.longitude.value),
    },
  };
}

async function saveSettings(event) {
  event.preventDefault();
  const status = document.getElementById("settings-status");
  status.textContent = "Saving...";

  try {
    const response = await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(readSettingsForm()),
    });
    if (!response.ok) throw new Error(`Save failed (${response.status})`);
    fillSettings(await response.json());
    status.textContent = "Saved";
    await refresh();
  } catch (error) {
    status.textContent = error.message;
  }
}

function initSettings() {
  document.getElementById("settings-toggle").addEventListener("click", openSettings);
  document.getElementById("settings-close").addEventListener("click", closeSettings);
  document.getElementById("settings-form").addEventListener("submit", saveSettings);
  document.getElementById("settings-modal").addEventListener("click", (event) => {
    if (event.target.id === "settings-modal") closeSettings();
  });
}

function rotateBackground() {
  const layers = [document.getElementById("bg-a"), document.getElementById("bg-b")];
  const active = state.backgroundIndex % 2;
  const hidden = (active + 1) % 2;
  const image = backgrounds[state.backgroundIndex % backgrounds.length];

  layers[hidden].style.backgroundImage = `url("${image}")`;
  layers[hidden].classList.add("active");
  layers[active].classList.remove("active");
  state.backgroundIndex += 1;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeClass(value) {
  return String(value ?? "").toLowerCase().replace(/[^a-z0-9-]/g, "-");
}

async function refresh() {
  const status = document.getElementById("status");
  try {
    const response = await fetch("/api/dashboard", { cache: "no-store" });
    const dashboard = await response.json();
    state.timezone = dashboard.timezone;
    document.getElementById("title").textContent = dashboard.title;
    renderEvents(dashboard.events || []);
    renderTasks(dashboard.tasks || []);
    renderHomework(dashboard.homework || []);
    renderWeather(dashboard.weather || []);
    renderNews(dashboard.news || []);
    status.textContent = [
      dashboard.calendarError ? `Calendar problem: ${dashboard.calendarError}` : "",
      dashboard.taskError ? `Task problem: ${dashboard.taskError}` : "",
      dashboard.homeworkError ? `Homework problem: ${dashboard.homeworkError}` : "",
      dashboard.weatherError ? `Weather problem: ${dashboard.weatherError}` : "",
      dashboard.newsError ? `News problem: ${dashboard.newsError}` : "",
    ]
      .filter(Boolean)
      .join("  ");
    updateClock();
  } catch (error) {
    status.textContent = `Dashboard offline: ${error.message}`;
  }
}

document.getElementById("bg-a").style.backgroundImage = `url("${backgrounds[0]}")`;
document.getElementById("bg-a").classList.add("active");
state.backgroundIndex = 1;
initNotes();
initSettings();
updateClock();
refresh();
setInterval(updateClock, 1000);
setInterval(refresh, 60 * 1000);
setInterval(rotateBackground, 60 * 1000);
setInterval(loadNotes, 2000);
