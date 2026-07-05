const API = "";

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || response.statusText);
  }
  return data;
}

const views = {
  empty: document.getElementById("empty-state"),
  list: document.getElementById("goal-list-view"),
  detail: document.getElementById("goal-detail-view"),
  monitor: document.getElementById("monitor-view"),
};

let activeSpaceId = null;
let selectedGoalId = null;
let pollTimer = null;

function showView(name) {
  Object.entries(views).forEach(([key, el]) => {
    el.classList.toggle("hidden", key !== name);
  });
}

function healthClass(health) {
  return `health-${health || "idle"}`;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderMarkdown(text) {
  const escaped = escapeHtml(text || "");
  return escaped
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/^- (.+)$/gm, "• $1");
}

async function loadSpaces() {
  const data = await api("/spaces");
  const list = document.getElementById("space-list");
  list.innerHTML = "";
  data.spaces.forEach((space) => {
    const li = document.createElement("li");
    li.textContent = space.name + (space.is_default ? " (default)" : "");
    li.dataset.spaceId = space.space_id;
    if (space.space_id === activeSpaceId || (!activeSpaceId && space.is_default)) {
      li.classList.add("active");
      activeSpaceId = space.space_id;
    }
    li.onclick = async () => {
      await api(`/spaces/${space.space_id}/switch`, { method: "POST" });
      activeSpaceId = space.space_id;
      await loadSpaces();
      await loadGoals();
    };
    list.appendChild(li);
  });
}

async function loadGoals() {
  const query = activeSpaceId ? `?space_id=${encodeURIComponent(activeSpaceId)}` : "";
  const data = await api(`/goals${query}`);
  const goals = data.goals || [];
  const container = document.getElementById("goal-cards");
  container.innerHTML = "";
  document.getElementById("goal-count").textContent = `${goals.length} goals`;

  if (!goals.length && !selectedGoalId) {
    showView("empty");
    return;
  }

  showView(selectedGoalId ? "detail" : "list");

  goals.forEach((goal) => {
    const card = document.createElement("article");
    card.className = "goal-card";
    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center">
        <strong>${escapeHtml(goal.description)}</strong>
        <span class="health-pill ${healthClass(goal.health)}">${goal.health}</span>
      </div>
      <p style="color:var(--muted);font-size:0.85rem;margin:0.5rem 0 0">
        ${escapeHtml(goal.knowledge?.display || "No knowledge yet")}
      </p>`;
    card.onclick = () => openGoal(goal.goal_id);
    container.appendChild(card);
  });

  await loadApprovals();
}

function renderResults(results) {
  const resultsEl = document.getElementById("detail-results");
  const report = results.report;

  if (!report?.content) {
    const running = results.artifacts?.length === 0;
    resultsEl.innerHTML = running
      ? '<p class="muted">Research in progress… results will appear here when complete.</p>'
      : '<p class="muted">No final report yet. Check Knowledge below for partial findings.</p>';
    return;
  }

  resultsEl.innerHTML = renderMarkdown(report.content);
}

function renderKnowledge(artifacts) {
  const knowEl = document.getElementById("detail-knowledge");
  if (!artifacts.length) {
    knowEl.innerHTML = "<p class='muted'>No artifacts yet</p>";
    return;
  }

  knowEl.innerHTML = "";
  artifacts.forEach((artifact) => {
    const item = document.createElement("div");
    item.className = "artifact-item";
    item.innerHTML = `
      <strong>${artifact.artifact_type}</strong>: ${escapeHtml(artifact.key)}
      <span class="muted"> (${artifact.size_bytes} B)</span>`;

    const preview = document.createElement("div");
    preview.className = "artifact-preview hidden";
    if (artifact.content) {
      preview.innerHTML = renderMarkdown(
        artifact.content.length > 1200
          ? artifact.content.slice(0, 1200) + "\n\n…"
          : artifact.content
      );
    } else {
      preview.textContent = "(empty)";
    }

    item.onclick = () => {
      preview.classList.toggle("hidden");
    };

    knowEl.appendChild(item);
    knowEl.appendChild(preview);
  });
}

async function openGoal(goalId) {
  selectedGoalId = goalId;
  showView("detail");

  const [goal, timeline, results, processes] = await Promise.all([
    api(`/goals/${goalId}`),
    api(`/goals/${goalId}/timeline`),
    api(`/goals/${goalId}/results`),
    api(`/goals/${goalId}/processes`),
  ]);

  document.getElementById("detail-title").textContent = goal.description;
  const health = document.getElementById("detail-health");
  health.textContent = goal.health;
  health.className = `health-pill ${healthClass(goal.health)}`;

  const stage = goal.pipeline_stage ? ` · ${goal.pipeline_stage}` : "";
  document.getElementById("detail-overview").textContent =
    `${goal.kind} goal · ${goal.process_ids?.length || 0} processes${stage}`;
  document.getElementById("detail-stats").textContent =
    goal.knowledge?.display || "No knowledge yet";

  const procEl = document.getElementById("detail-processes");
  procEl.innerHTML = (processes.processes || [])
    .map((p) => `<div class="process-row"><span>${escapeHtml(p.name)}</span><span>${p.state}</span></div>`)
    .join("") || "<p class='muted'>No active processes</p>";

  renderResults(results);
  renderKnowledge(results.artifacts || []);

  const timelineEl = document.getElementById("detail-timeline");
  timelineEl.innerHTML = "";
  (timeline.groups || []).forEach((group) => {
    const block = document.createElement("div");
    block.className = "timeline-group";
    block.innerHTML = `<div class="timeline-day">${escapeHtml(group.day)}</div>`;
    group.entries.forEach((entry) => {
      const row = document.createElement("div");
      row.className = "timeline-entry";
      row.textContent = entry.narrative;
      row.onclick = () => inspectEvent(entry.event_id);
      block.appendChild(row);
    });
    timelineEl.appendChild(block);
  });

  (timeline.scheduled || []).forEach((entry) => {
    const row = document.createElement("div");
    row.className = "timeline-entry";
    row.textContent = `⏱ ${entry.narrative}`;
    timelineEl.appendChild(row);
  });
}

async function inspectEvent(eventId) {
  const data = await api(`/events/${eventId}/inspect`);
  document.getElementById("inspector-card").classList.remove("hidden");
  document.getElementById("inspector-output").textContent = JSON.stringify(data, null, 2);
}

async function loadApprovals() {
  const snapshot = await api("/system/snapshot");
  const pending = snapshot.pending_approvals || [];
  const bar = document.getElementById("approvals-bar");
  const container = document.getElementById("approval-cards");
  if (!pending.length) {
    bar.classList.add("hidden");
    return;
  }
  bar.classList.remove("hidden");
  container.innerHTML = pending.map((item) => `
    <div style="margin-bottom:0.75rem">
      <p style="margin:0 0 0.5rem">${escapeHtml(item.message)}</p>
      <button data-approval="${item.request_id}">Approve</button>
    </div>`).join("");
  container.querySelectorAll("button[data-approval]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/approvals/${btn.dataset.approval}`, { method: "POST" });
      await loadGoals();
      if (selectedGoalId) await openGoal(selectedGoalId);
    };
  });
}

async function loadMonitor() {
  showView("monitor");
  const snapshot = await api("/system/snapshot");
  const el = document.getElementById("monitor-processes");
  el.innerHTML = (snapshot.processes || [])
    .map((p) => `<div class="process-row"><span>${escapeHtml(p.name)}</span><span>${p.state}</span></div>`)
    .join("");
}

document.getElementById("new-goal-form").onsubmit = async (event) => {
  event.preventDefault();
  const description = document.getElementById("goal-description").value.trim();
  const mode = document.getElementById("goal-mode").value;
  const created = await api("/goals", {
    method: "POST",
    body: JSON.stringify({ description, mode, space_id: activeSpaceId }),
  });
  document.getElementById("goal-description").value = "";
  selectedGoalId = created.goal_id;
  await loadGoals();
  await openGoal(created.goal_id);
};

document.getElementById("new-space-form").onsubmit = async (event) => {
  event.preventDefault();
  const name = document.getElementById("new-space-name").value.trim();
  await api("/spaces", { method: "POST", body: JSON.stringify({ name }) });
  document.getElementById("new-space-name").value = "";
  await loadSpaces();
};

document.getElementById("back-to-list").onclick = () => {
  selectedGoalId = null;
  document.getElementById("inspector-card").classList.add("hidden");
  loadGoals();
};

document.getElementById("view-monitor").onclick = loadMonitor;
document.getElementById("back-from-monitor").onclick = () => {
  selectedGoalId = null;
  loadGoals();
};

async function init() {
  await loadSpaces();
  await loadGoals();
  pollTimer = setInterval(async () => {
    if (selectedGoalId) {
      await openGoal(selectedGoalId);
    } else {
      await loadGoals();
    }
  }, 5000);
}

init();
