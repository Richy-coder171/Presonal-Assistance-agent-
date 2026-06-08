const state = {
  dashboard: null,
  language: window.AssistantI18n.appLanguage(),
};

const priorityClass = {
  urgent: "danger",
  important: "warn",
  routine: "neutral",
  fyi: "info",
};

document.addEventListener("DOMContentLoaded", () => {
  bindActions();
  setLanguage(state.language);
  loadDashboard();
});

function bindActions() {
  document.querySelectorAll("[data-lang]").forEach((button) => {
    button.addEventListener("click", () => setLanguage(button.dataset.lang));
  });

  document.querySelector("[data-action='refresh-email']").addEventListener("click", () => runAction("/api/run/email"));
  document.querySelector("[data-action='refresh-calendar']").addEventListener("click", () => runAction("/api/run/calendar"));
  document.querySelector("[data-action='briefing']").addEventListener("click", () => runAction("/api/run/briefing"));
  document.querySelector("[data-action='send-briefing']").addEventListener("click", sendLatestBriefing);
  document.querySelector("[data-action='demo']").addEventListener("click", () => runAction("/api/demo/load"));
  document.querySelector("#task-form").addEventListener("submit", createTask);
}

function setLanguage(language) {
  state.language = language === "he" ? "he" : "en";
  localStorage.setItem("assistant.language", state.language);
  window.AssistantI18n.applyTranslations(state.language);
  document.querySelectorAll("[data-lang]").forEach((button) => {
    const isActive = button.dataset.lang === state.language;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
  if (state.dashboard) {
    render();
  }
}

async function loadDashboard() {
  setBusy(true);
  try {
    state.dashboard = await api("/api/dashboard");
    render();
    setNotice(t("systemUpdated"));
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    setBusy(false);
  }
}

async function runAction(path) {
  setBusy(true);
  try {
    const result = await api(path, { method: "POST" });
    if (result.errors && result.errors.length) {
      setNotice(result.errors.map((item) => item.error).join(" | "), true);
    } else {
      setNotice(t("completed"));
    }
    await loadDashboard();
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    setBusy(false);
  }
}

async function sendLatestBriefing() {
  if (!window.confirm(t("sendApproval"))) {
    setNotice(t("cancelled"));
    return;
  }

  setBusy(true);
  try {
    const result = await api("/api/briefing/send", {
      method: "POST",
      body: JSON.stringify({ approved: true }),
    });
    if (result.errors && result.errors.length) {
      setNotice(result.errors.map((item) => item.error).join(" | "), true);
    } else {
      setNotice(t("completed"));
    }
    await loadDashboard();
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    setBusy(false);
  }
}

async function createTask(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = {
    title: form.get("title"),
    notes: form.get("notes"),
    priority: form.get("priority"),
    due_at: form.get("due_at") ? new Date(form.get("due_at")).toISOString() : null,
  };
  setBusy(true);
  try {
    await api("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
    event.currentTarget.reset();
    setNotice(t("taskAdded"));
    await loadDashboard();
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    setBusy(false);
  }
}

async function updateTask(id, patch) {
  setBusy(true);
  try {
    await api(`/api/tasks/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
    await loadDashboard();
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    setBusy(false);
  }
}

async function deleteTask(id) {
  setBusy(true);
  try {
    await api(`/api/tasks/${encodeURIComponent(id)}`, { method: "DELETE" });
    await loadDashboard();
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    setBusy(false);
  }
}

function render() {
  const data = state.dashboard;
  renderMetrics(data.metrics);
  renderIntegrations(data.status.configured, data.status.demo_mode);
  renderEmails(data.emails);
  renderEvents(data.events, data.conflicts);
  renderTasks(data.tasks);
  renderBriefing(data.latest_briefing);
}

function renderMetrics(metrics) {
  const target = document.querySelector("#metrics");
  const items = [
    ["urgent", metrics.urgent_emails, "danger"],
    ["important", metrics.important_emails, "warn"],
    ["openTasks", metrics.open_tasks, "info"],
    ["calendarConflicts", metrics.calendar_conflicts, metrics.calendar_conflicts ? "danger" : "ok"],
  ];
  target.innerHTML = items.map(([key, value, tone]) => `
    <div class="metric ${tone}">
      <span>${escapeHtml(t(key))}</span>
      <strong>${value}</strong>
    </div>
  `).join("");
}

function renderIntegrations(configured, demoMode) {
  const target = document.querySelector("#integrations");
  const items = [
    ["Google", configured.gmail_or_google_calendar],
    ["Microsoft", configured.outlook_or_microsoft_calendar],
    [t("ai"), configured.openai],
    [t("send"), configured.messaging],
    [t("demo"), demoMode],
  ];
  target.setAttribute("aria-label", t("integrationStatus"));
  target.innerHTML = items.map(([label, active]) => `
    <span class="chip ${active ? "active" : ""}">
      <span class="dot" aria-hidden="true"></span>
      <span>${escapeHtml(label)}</span>
      <span class="sr-only">${active ? t("active") : t("inactive")}</span>
    </span>
  `).join("");
}

function renderEmails(emails) {
  const target = document.querySelector("#email-list");
  if (!emails.length) {
    target.innerHTML = empty(t("emptyInbox"));
    return;
  }
  target.innerHTML = emails.slice(0, 12).map((email) => `
    <article class="item email-item">
      <div class="item-main">
        <div class="item-row">
          <strong>${escapeHtml(email.subject || t("noSubject"))}</strong>
          ${badge(email.priority)}
        </div>
        <p>${escapeHtml(email.summary || email.snippet || "")}</p>
        ${email.draft_reply ? `<details><summary>${escapeHtml(t("draftReply"))}</summary><pre>${escapeHtml(email.draft_reply)}</pre></details>` : ""}
      </div>
      <time>${formatDate(email.received_at)}</time>
    </article>
  `).join("");
}

function renderEvents(events, conflicts) {
  const target = document.querySelector("#calendar-list");
  if (!events.length) {
    target.innerHTML = empty(t("emptyCalendar"));
    return;
  }
  const conflictIds = new Set(conflicts.flatMap((conflict) => conflict.event_ids));
  target.innerHTML = events.slice(0, 12).map((event) => `
    <article class="item ${conflictIds.has(event.id) ? "conflict" : ""}">
      <div class="item-main">
        <div class="item-row">
          <strong>${escapeHtml(event.title)}</strong>
          ${conflictIds.has(event.id) ? `<span class="badge danger">${escapeHtml(t("conflicts"))}</span>` : ""}
        </div>
        <p>${formatDate(event.start)} - ${formatTime(event.end)}${event.location ? ` · ${escapeHtml(event.location)}` : ""}</p>
      </div>
    </article>
  `).join("");
}

function renderTasks(tasks) {
  const target = document.querySelector("#task-list");
  if (!tasks.length) {
    target.innerHTML = empty(t("emptyTasks"));
    return;
  }
  target.innerHTML = tasks.slice(0, 16).map((task) => {
    const isDone = task.status === "done";
    return `
      <article class="item task-item ${isDone ? "done" : ""}">
        <button class="icon-button" title="${isDone ? t("reopenTask") : t("taskComplete")}" aria-label="${isDone ? t("reopenTask") : t("taskComplete")}" data-task="${task.id}" data-status="${isDone ? "open" : "done"}">
          <span aria-hidden="true">${isDone ? "&#8634;" : "&#10003;"}</span>
        </button>
        <div class="item-main">
          <div class="item-row">
            <strong>${escapeHtml(task.title)}</strong>
            ${badge(task.priority)}
          </div>
          <p>${escapeHtml(task.notes || "")}${task.due_at ? ` · ${formatDate(task.due_at)}` : ""}</p>
        </div>
        <button class="icon-button danger-button" title="${t("delete")}" aria-label="${t("delete")}" data-delete-task="${task.id}"><span aria-hidden="true">&#215;</span></button>
      </article>
    `;
  }).join("");

  target.querySelectorAll("[data-task]").forEach((button) => {
    button.addEventListener("click", () => updateTask(button.dataset.task, { status: button.dataset.status }));
  });
  target.querySelectorAll("[data-delete-task]").forEach((button) => {
    button.addEventListener("click", () => deleteTask(button.dataset.deleteTask));
  });
}

function renderBriefing(briefing) {
  const target = document.querySelector("#briefing-text");
  target.textContent = briefing ? briefing.text : t("loading");
}

function badge(priority) {
  const key = priority && window.AssistantI18n.translations.en[priority] ? priority : "routine";
  return `<span class="badge ${priorityClass[key] || "neutral"}">${escapeHtml(t(key))}</span>`;
}

function empty(text) {
  return `<div class="empty">${escapeHtml(text)}</div>`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || t("apiError"));
  }
  return payload;
}

function setBusy(isBusy) {
  document.body.classList.toggle("busy", isBusy);
  document.querySelectorAll("button").forEach((button) => {
    button.disabled = isBusy;
  });
}

function setNotice(text, isError = false) {
  const target = document.querySelector("#notice");
  target.textContent = text;
  target.classList.toggle("error", isError);
}

function formatDate(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat(dateLocale(), {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatTime(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat(dateLocale(), {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function dateLocale() {
  return state.language === "he" ? "he-IL" : "en-US";
}

function t(key) {
  return window.AssistantI18n.appText(key, state.language);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
