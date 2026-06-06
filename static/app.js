const state = {
  timezone: "America/New_York",
  backgroundIndex: 0,
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

function renderWeather(hours) {
  const container = document.getElementById("weather");
  if (!hours.length) {
    container.innerHTML = '<div class="empty">Weather unavailable.</div>';
    return;
  }

  container.innerHTML = hours
    .map((hour, index) => {
      const label = index === 0 ? "Now" : formatDateTime(hour.time, { hour: "numeric" });
      return `
        <article class="weather-hour">
          <p class="weather-time">${escapeHtml(label)}</p>
          <h3>${escapeHtml(hour.temperature)}&deg;</h3>
          <p class="rain">${escapeHtml(hour.rainChance)}% rain</p>
        </article>
      `;
    })
    .join("");
}

function renderNews(headlines) {
  const container = document.getElementById("news-ticker");
  if (!headlines.length) {
    container.innerHTML = '<span class="ticker-item">No headlines published yet today.</span>';
    return;
  }

  const items = headlines
    .map((headline) => `<span class="ticker-item">${escapeHtml(headline.title)}</span>`)
    .join("");
  container.innerHTML = `${items}${items}`;
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
updateClock();
refresh();
setInterval(updateClock, 1000);
setInterval(refresh, 5 * 60 * 1000);
setInterval(rotateBackground, 60 * 1000);
