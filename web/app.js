const API = "";

const STAGE_PROGRESS = {
  planning: 15,
  researching: 45,
  writing: 75,
  evaluating: 60,
  publishing: 90,
  awaiting_approval: 85,
  completed: 100,
  failed: 100,
};

const PROCESS_STATE_PROGRESS = {
  running: 70,
  waiting: 30,
  completed: 100,
  failed: 100,
  terminated: 100,
  created: 10,
  starting: 20,
  idle: 5,
};

let activeSpaceId = null;
let selectedGoalId = null;
let showArchived = false;
let activeTab = "goals";
let eventSource = null;
let systemPollTimer = null;
let policyPollTimer = null;
let goalPollTimer = null;
let liveLines = [];

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

function $(id) {
  return document.getElementById(id);
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function healthClass(health) {
  return `health-${health || "idle"}`;
}

function formatAge(seconds) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function formatBytes(n) {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  return `${(n / 1024).toFixed(1)} KB`;
}

function formatTime(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return iso;
  }
}

function progressForStage(stage) {
  if (!stage) return 5;
  const key = String(stage).toLowerCase();
  return STAGE_PROGRESS[key] ?? 25;
}

function progressForProcess(state) {
  return PROCESS_STATE_PROGRESS[String(state).toLowerCase()] ?? 15;
}

function miniBar(pct) {
  const filled = Math.round((pct / 100) * 12);
  return "█".repeat(filled) + "░".repeat(12 - filled);
}

function showTab(name) {
  activeTab = name;
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === name);
  });
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("hidden", panel.id !== `panel-${name}`);
  });
  $("goal-bar").classList.toggle("hidden", !selectedGoalId || name === "goals");

  if (name === "system") {
    loadSystem();
    startSystemPoll();
  } else if (name === "policy") {
    stopSystemPoll();
    renderPolicy();
    startPolicyPoll();
  } else {
    stopSystemPoll();
    stopPolicyPoll();
  }

  if (name === "live" && selectedGoalId) {
    connectStream(selectedGoalId);
  }

  if (selectedGoalId && ["knowledge", "timeline", "live"].includes(name)) {
    refreshGoalPanels();
  }
}

function startSystemPoll() {
  stopSystemPoll();
  systemPollTimer = setInterval(loadSystem, 2500);
}

function stopSystemPoll() {
  if (systemPollTimer) {
    clearInterval(systemPollTimer);
    systemPollTimer = null;
  }
}

function startPolicyPoll() {
  stopPolicyPoll();
  policyPollTimer = setInterval(renderPolicy, 2500);
}

function stopPolicyPoll() {
  if (policyPollTimer) {
    clearInterval(policyPollTimer);
    policyPollTimer = null;
  }
}

function startGoalPoll() {
  stopGoalPoll();
  goalPollTimer = setInterval(async () => {
    if (selectedGoalId) {
      await refreshGoalBar();
      if (activeTab === "live" || activeTab === "knowledge" || activeTab === "timeline") {
        await refreshGoalPanels();
      }
      if (activeTab === "policy") {
        await renderPolicy();
      }
    }
    await loadGoals();
    await loadApprovals();
  }, 4000);
}

function stopGoalPoll() {
  if (goalPollTimer) {
    clearInterval(goalPollTimer);
    goalPollTimer = null;
  }
}

function connectStream(goalId) {
  disconnectStream();
  liveLines = [];
  renderLiveFeed();

  const url = `/goals/${encodeURIComponent(goalId)}/stream`;
  eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.type === "connected") return;
      appendLiveLine(payload);
      if (payload.narrative) {
        refreshLiveResults();
      }
    } catch {
      /* ignore malformed */
    }
  };

  eventSource.onerror = () => {
    appendLiveLine({
      timestamp: new Date().toISOString(),
      narrative: "(stream disconnected — reconnecting on next tab visit)",
    });
  };
}

function disconnectStream() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

function appendLiveLine(payload) {
  liveLines.push(payload);
  if (liveLines.length > 200) liveLines.shift();
  renderLiveFeed();
}

function renderLiveFeed() {
  const feed = $("live-feed");
  const empty = $("live-empty");
  if (!selectedGoalId) {
    feed.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");
  feed.innerHTML = liveLines
    .map((line) => {
      const ts = formatTime(line.timestamp);
      const msg = escapeHtml(line.narrative || line.event_type || "");
      return `<div class="feed-line"><span class="ts">${ts}</span><span class="msg">${msg}</span></div>`;
    })
    .join("");
  feed.scrollTop = feed.scrollHeight;
}

async function loadSpaces() {
  const data = await api("/spaces");
  const select = $("space-select");
  select.innerHTML = "";
  data.spaces.forEach((space) => {
    const opt = document.createElement("option");
    opt.value = space.space_id;
    opt.textContent = space.name + (space.is_default ? " (default)" : "");
    select.appendChild(opt);
    if (space.is_default && !activeSpaceId) {
      activeSpaceId = space.space_id;
    }
  });
  if (activeSpaceId) {
    select.value = activeSpaceId;
  }
}

async function loadGoals() {
  const params = new URLSearchParams();
  if (activeSpaceId) params.set("space_id", activeSpaceId);
  if (showArchived) params.set("include_archived", "true");
  const query = params.toString() ? `?${params}` : "";
  const data = await api(`/goals${query}`);
  const goals = data.goals || [];
  const list = $("goal-list");
  const empty = $("goals-empty");

  list.innerHTML = goals
    .map((goal) => {
      const pct = progressForStage(goal.pipeline_stage);
      const stage = goal.pipeline_stage || "starting";
      const policyLabel = goal.policy
        ? `${goal.policy.spend_preset} · ${goal.policy.autonomy_preset}`
        : "";
      const archived = goal.archived ? " archived" : "";
      const selected = goal.goal_id === selectedGoalId ? " selected" : "";
      return `
        <div class="goal-row${selected}${archived}" data-goal-id="${escapeHtml(goal.goal_id)}">
          <span class="goal-row-desc">${escapeHtml(goal.description)}</span>
          <span class="health-tag ${healthClass(goal.health)}">${goal.health}</span>
          <span class="goal-row-meta">${escapeHtml(stage)} · ${pct}%${policyLabel ? " · " + escapeHtml(policyLabel) : ""}</span>
        </div>`;
    })
    .join("");

  empty.classList.toggle("hidden", goals.length > 0);

  list.querySelectorAll(".goal-row").forEach((row) => {
    row.onclick = () => selectGoal(row.dataset.goalId);
  });
}

async function selectGoal(goalId) {
  selectedGoalId = goalId;
  $("inspector-panel").classList.add("hidden");
  await loadGoals();
  await refreshGoalBar();
  await refreshGoalPanels();
  if (activeTab === "live") {
    connectStream(goalId);
  }
}

async function refreshGoalBar() {
  if (!selectedGoalId) {
    $("goal-bar").classList.add("hidden");
    return;
  }

  const [goal, processes] = await Promise.all([
    api(`/goals/${selectedGoalId}`),
    api(`/goals/${selectedGoalId}/processes`),
  ]);

  const pct = progressForStage(goal.pipeline_stage);
  $("goal-bar").classList.remove("hidden");
  $("goal-bar-title").textContent = goal.description;
  const healthEl = $("goal-bar-health");
  healthEl.textContent = goal.health;
  healthEl.className = `health-tag ${healthClass(goal.health)}`;
  $("goal-bar-pct").textContent = `${pct}% · ${goal.pipeline_stage || "starting"}`;
  $("goal-bar-fill").style.width = `${pct}%`;

  const procList = processes.processes || [];
  $("goal-bar-pipeline").innerHTML = procList.length
    ? procList
        .map((p) => {
          const pp = progressForProcess(p.state);
          const cls = p.state === "failed" ? "failed" : p.state === "running" ? "running" : "";
          return `
            <div class="pipeline-item ${cls}">
              <span>${escapeHtml(p.name)}</span>
              <span>${escapeHtml(p.state)}</span>
              <span>${miniBar(pp)}</span>
            </div>`;
        })
        .join("")
    : `<span class="goal-row-meta">No active processes</span>`;
}

async function refreshGoalPanels() {
  if (!selectedGoalId) return;

  if (activeTab === "knowledge" || activeTab === "live") {
    await renderKnowledge();
  }
  if (activeTab === "timeline") {
    await renderTimeline();
  }
  if (activeTab === "live") {
    await refreshLiveResults();
  }
}

async function renderKnowledge() {
  const empty = $("knowledge-empty");
  const table = $("knowledge-table");
  const body = $("knowledge-body");
  const preview = $("knowledge-preview");

  if (!selectedGoalId) {
    empty.classList.remove("hidden");
    table.classList.add("hidden");
    preview.classList.add("hidden");
    return;
  }

  const data = await api(`/goals/${selectedGoalId}/results`);
  const artifacts = data.artifacts || [];

  if (!artifacts.length) {
    empty.textContent = "No knowledge artifacts yet.";
    empty.classList.remove("hidden");
    table.classList.add("hidden");
    preview.classList.add("hidden");
    return;
  }

  empty.classList.add("hidden");
  table.classList.remove("hidden");

  body.innerHTML = artifacts
    .map((a, i) => `
      <tr class="clickable" data-idx="${i}">
        <td>${escapeHtml(a.artifact_type)}</td>
        <td>${escapeHtml(a.key)}</td>
        <td>${formatBytes(a.size_bytes)}</td>
        <td>→</td>
      </tr>`)
    .join("");

  body.querySelectorAll("tr").forEach((row) => {
    row.onclick = () => {
      body.querySelectorAll("tr").forEach((r) => r.classList.remove("selected"));
      row.classList.add("selected");
      const artifact = artifacts[Number(row.dataset.idx)];
      preview.classList.remove("hidden");
      preview.textContent = artifact.content || "(empty)";
    };
  });
}

async function refreshLiveResults() {
  if (!selectedGoalId) return;
  const data = await api(`/goals/${selectedGoalId}/results`);
  const panel = $("live-results");
  const body = $("live-results-body");

  const report = data.report?.content;
  const findings = (data.findings || []).map((f) => f.content).filter(Boolean);

  if (report) {
    panel.classList.remove("hidden");
    body.textContent = report;
    return;
  }

  if (findings.length) {
    panel.classList.remove("hidden");
    body.textContent = findings.join("\n\n---\n\n");
    return;
  }

  panel.classList.add("hidden");
  body.textContent = "";
}

async function renderTimeline() {
  const empty = $("timeline-empty");
  const list = $("timeline-list");

  if (!selectedGoalId) {
    empty.classList.remove("hidden");
    list.innerHTML = "";
    return;
  }

  const timeline = await api(`/goals/${selectedGoalId}/timeline`);
  const groups = timeline.groups || [];

  if (!groups.length && !(timeline.scheduled || []).length) {
    empty.textContent = "No timeline events yet.";
    empty.classList.remove("hidden");
    list.innerHTML = "";
    return;
  }

  empty.classList.add("hidden");
  let html = "";

  groups.forEach((group) => {
    html += `<div class="timeline-day">${escapeHtml(group.day)}</div>`;
    group.entries.forEach((entry) => {
      html += `<div class="timeline-entry" data-event-id="${escapeHtml(entry.event_id)}">${escapeHtml(entry.narrative)}</div>`;
    });
  });

  (timeline.scheduled || []).forEach((entry) => {
    html += `<div class="timeline-entry scheduled">⏱ ${escapeHtml(entry.narrative)}</div>`;
  });

  list.innerHTML = html;
  list.querySelectorAll(".timeline-entry[data-event-id]").forEach((row) => {
    row.onclick = () => inspectEvent(row.dataset.eventId);
  });
}

async function inspectEvent(eventId) {
  const data = await api(`/events/${eventId}/inspect`);
  const panel = $("inspector-panel");
  const fields = $("inspector-fields");
  const raw = $("inspector-raw");

  const rows = [
    ["When", formatTime(data.timestamp) + " " + (data.timestamp || "").slice(0, 10)],
    ["Type", data.event_type],
    ["Why", data.why || data.narrative],
    ["Process", data.source_process],
    ["Plugin", data.plugin],
    ["Duration", data.duration_ms != null ? `${data.duration_ms} ms` : "—"],
    ["Capabilities", (data.capabilities || []).join(", ") || "—"],
    ["Correlation", data.correlation_id || "—"],
    ["Goal", data.goal_id || "—"],
  ];

  fields.innerHTML = rows
    .map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value || "—")}</dd>`)
    .join("");

  raw.textContent = JSON.stringify(data, null, 2);
  panel.classList.remove("hidden");
}

async function renderPolicy() {
  const empty = $("policy-empty");
  const content = $("policy-content");
  if (!selectedGoalId) {
    empty.classList.remove("hidden");
    content.classList.add("hidden");
    return;
  }

  const data = await api(`/goals/${selectedGoalId}/policy`);
  if (!data.limits) {
    empty.textContent = data.message || "No policy configured for this goal.";
    empty.classList.remove("hidden");
    content.classList.add("hidden");
    return;
  }

  empty.classList.add("hidden");
  content.classList.remove("hidden");

  const usage = data.usage || {};
  const limits = data.limits || {};
  const util = data.utilization || {};

  $("policy-summary").innerHTML = `
    <span>Workload <strong>${escapeHtml(data.workload || "—")}</strong></span>
    <span>Spend <strong>${escapeHtml(data.spend_preset || "—")}</strong></span>
    <span>Autonomy <strong>${escapeHtml(data.autonomy_preset || "—")}</strong></span>
    <span>Auto-approve <strong>${data.auto_approve ? "yes" : "no"}</strong></span>
  `;

  const rows = [
    ["Tokens", usage.tokens ?? 0, limits.max_tokens, util.tokens_pct],
    ["Tool calls", usage.tool_invocations ?? 0, limits.max_tool_invocations, util.tools_pct],
    ["Cost (USD)", (usage.cost_usd ?? 0).toFixed(3), limits.max_cost_usd, util.cost_pct],
    ["Exec time (s)", (usage.execution_seconds ?? 0).toFixed(1), limits.max_execution_time_seconds, null],
  ];

  $("policy-limits").innerHTML = rows
    .map(([label, used, limit, pct]) => {
      const bar = pct != null ? ` ${miniBar(pct)} ${pct}%` : "";
      return `
        <tr>
          <td>${escapeHtml(label)}</td>
          <td>${used}</td>
          <td>${limit}</td>
          <td class="goal-row-meta">${bar}</td>
        </tr>`;
    })
    .join("");

  $("policy-config").textContent = JSON.stringify(
    { budget: limits, config: data.config || {} },
    null,
    2,
  );

  const goal = await api(`/goals/${selectedGoalId}`);
  $("edit-description").value = goal.description || "";
  if (data.spend_preset) $("edit-spend").value = data.spend_preset;
  if (data.autonomy_preset) $("edit-autonomy").value = data.autonomy_preset;
}

async function goalAction(path, { confirmText } = {}) {
  if (!selectedGoalId) return;
  if (confirmText && !window.confirm(confirmText)) return;
  await api(path, { method: "POST" });
  await loadGoals();
  await refreshGoalBar();
  if (activeTab === "policy") await renderPolicy();
}

async function deleteSelectedGoal() {
  if (!selectedGoalId) return;
  if (!window.confirm("Delete this goal? Running processes will be cancelled.")) return;
  await api(`/goals/${selectedGoalId}`, { method: "DELETE" });
  selectedGoalId = null;
  disconnectStream();
  $("goal-bar").classList.add("hidden");
  await loadGoals();
  showTab("goals");
}

async function loadSystem() {
  const snapshot = await api("/system/snapshot");
  const metrics = snapshot.metrics || {};
  const budgets = snapshot.budgets || [];
  const budgetByPid = Object.fromEntries(budgets.map((b) => [b.process_id, b]));

  const counts = metrics.process_count_by_state || {};
  const running = counts.running || 0;
  const waiting = counts.waiting || metrics.waiting_count || 0;
  const failed = counts.failed || 0;

  $("system-summary").innerHTML = `
    <span>Processes <strong>${(snapshot.processes || []).length}</strong></span>
    <span>Running <strong>${running}</strong></span>
    <span>Waiting <strong>${waiting}</strong></span>
    <span>Failed <strong>${failed}</strong></span>
    <span>Queue <strong>${snapshot.scheduler_depth ?? metrics.scheduler_depth ?? 0}</strong></span>
    <span>Events <strong>${metrics.event_throughput ?? 0}</strong></span>
    <span>Tokens <strong>${metrics.token_consumption ?? 0}</strong></span>
  `;

  $("system-processes").innerHTML = (snapshot.processes || [])
    .map((p) => {
      const b = budgetByPid[p.process_id] || {};
      return `
        <tr>
          <td>${escapeHtml(p.name)}</td>
          <td>${escapeHtml(p.state)}</td>
          <td>${formatAge(p.age_seconds)}</td>
          <td>${b.tokens ?? 0}</td>
          <td>${b.tool_invocations ?? 0}</td>
          <td>${b.execution_seconds != null ? b.execution_seconds.toFixed(1) + "s" : "—"}</td>
          <td>${p.mailbox_pending ?? 0}</td>
        </tr>`;
    })
    .join("") || `<tr><td colspan="7" class="goal-row-meta">No processes</td></tr>`;

  const queue = snapshot.queued_process_ids || [];
  $("system-queue").textContent = queue.length
    ? queue.map((id, i) => `${i + 1}. ${id}`).join("\n")
    : "(empty)";
}

async function loadApprovals() {
  const snapshot = await api("/system/snapshot");
  const pending = snapshot.pending_approvals || [];
  const bar = $("approvals-bar");
  const list = $("approval-list");

  if (!pending.length) {
    bar.classList.add("hidden");
    return;
  }

  bar.classList.remove("hidden");
  list.innerHTML = pending
    .map(
      (item) => `
      <div class="approval-item">
        <p>${escapeHtml(item.message)}</p>
        <button type="button" data-approval="${escapeHtml(item.request_id)}">Approve</button>
      </div>`
    )
    .join("");

  list.querySelectorAll("button[data-approval]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/approvals/${btn.dataset.approval}`, { method: "POST" });
      await loadApprovals();
      if (selectedGoalId) {
        await refreshGoalBar();
        await refreshGoalPanels();
      }
    };
  });
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.onclick = () => showTab(tab.dataset.tab);
});

$("space-select").onchange = async (event) => {
  const spaceId = event.target.value;
  await api(`/spaces/${spaceId}/switch`, { method: "POST" });
  activeSpaceId = spaceId;
  selectedGoalId = null;
  disconnectStream();
  $("goal-bar").classList.add("hidden");
  await loadGoals();
};

$("new-space-btn").onclick = async () => {
  const name = window.prompt("Space name");
  if (!name?.trim()) return;
  await api("/spaces", { method: "POST", body: JSON.stringify({ name: name.trim() }) });
  await loadSpaces();
};

$("show-archived").onchange = async (event) => {
  showArchived = event.target.checked;
  await loadGoals();
};

$("action-edit").onclick = () => showTab("policy");
$("action-rerun").onclick = () =>
  goalAction(`/goals/${selectedGoalId}/rerun`, {
    confirmText: "Rerun this goal? Current processes will be cancelled and work restarted.",
  }).then(() => showTab("live"));
$("action-cancel").onclick = () =>
  goalAction(`/goals/${selectedGoalId}/cancel`, {
    confirmText: "Cancel all running processes for this goal?",
  });
$("action-delete").onclick = () => deleteSelectedGoal();

$("edit-goal-form").onsubmit = async (event) => {
  event.preventDefault();
  if (!selectedGoalId) return;
  await api(`/goals/${selectedGoalId}`, {
    method: "PATCH",
    body: JSON.stringify({
      description: $("edit-description").value.trim(),
      spend_preset: $("edit-spend").value,
      autonomy_preset: $("edit-autonomy").value,
    }),
  });
  await loadGoals();
  await refreshGoalBar();
  await renderPolicy();
};

$("new-goal-form").onsubmit = async (event) => {
  event.preventDefault();
  const description = $("goal-description").value.trim();
  const mode = $("goal-mode").value;
  const spend_preset = $("goal-spend").value;
  const autonomy_preset = $("goal-autonomy").value;
  const created = await api("/goals", {
    method: "POST",
    body: JSON.stringify({
      description,
      mode,
      spend_preset,
      autonomy_preset,
      space_id: activeSpaceId,
    }),
  });
  $("goal-description").value = "";
  await loadGoals();
  await selectGoal(created.goal_id);
  showTab("live");
};

async function init() {
  await loadSpaces();
  await loadGoals();
  await loadApprovals();
  startGoalPoll();
}

init();
