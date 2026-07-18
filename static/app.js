(() => {
  const el = (id) => document.getElementById(id);

  const state = {
    sessionId: null,
    targetCategory: null,
    candidates: [],       // current screening-view queue
    files: [],
    allCandidatesCache: {}, // id -> candidate, populated by /api/all-candidates
    compareSelection: new Set(),
    charts: {},
  };

  const FEATURE_LABELS = {
    category_confidence: "Job-category match (ANN)",
    jd_similarity: "Text similarity to job description",
    skill_match_ratio: "Skill overlap",
    experience_score: "Years of experience",
    education_score: "Education level",
  };

  // ============================================================
  // VIEW ROUTER
  // ============================================================
  const views = ["dashboard", "screening", "candidates", "history", "compare", "model"];
  function switchView(name) {
    views.forEach((v) => {
      el(`view-${v}`).classList.toggle("hidden", v !== name);
    });
    document.querySelectorAll(".nav-item").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.view === name);
    });
    if (name === "dashboard") loadDashboard();
    if (name === "candidates") loadAllCandidates();
    if (name === "history") loadSessions();
    if (name === "model") loadModelInfo();
  }
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => switchView(btn.dataset.view));
  });

  // ============================================================
  // MODEL BADGE (sidebar)
  // ============================================================
  fetch("/api/model-info")
    .then((r) => r.json())
    .then((info) => {
      const badge = el("modelBadge");
      badge.classList.remove("loading");
      el("modelBadgeText").textContent =
        `ANN live · ${(info.test_accuracy * 100).toFixed(1)}% acc · ${info.n_samples} real resumes`;
    })
    .catch(() => { el("modelBadgeText").textContent = "Model status unavailable"; });

  // ============================================================
  // TOAST
  // ============================================================
  let toastTimer;
  function showToast(msg, isError = false) {
    clearTimeout(toastTimer);
    const t = el("toast");
    t.textContent = msg;
    t.classList.toggle("error", isError);
    t.classList.add("show");
    toastTimer = setTimeout(() => t.classList.remove("show"), 3200);
  }

  // ============================================================
  // GAUGE (shared svg helper)
  // ============================================================
  function gaugeSVG(pct, size = 56) {
    const r = size / 2 - 5;
    const c = 2 * Math.PI * r;
    const offset = c * (1 - pct);
    const color = pct >= 0.6 ? "#3F7D58" : pct >= 0.35 ? "#C98A3E" : "#B3452C";
    return `
      <svg class="gauge" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
        <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="#E1D8C2" stroke-width="5"/>
        <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="${color}" stroke-width="5"
          stroke-dasharray="${c}" stroke-dashoffset="${offset}" stroke-linecap="round"
          transform="rotate(-90 ${size/2} ${size/2})"/>
        <text x="50%" y="53%" text-anchor="middle" dominant-baseline="middle" font-size="14" fill="#241F17">
          ${Math.round(pct * 100)}
        </text>
      </svg>`;
  }

  // ============================================================
  // DASHBOARD
  // ============================================================
  function loadDashboard() {
    fetch("/api/dashboard").then((r) => r.json()).then(renderDashboard).catch(() => showToast("Could not load dashboard.", true));
  }
  el("refreshDashboard").addEventListener("click", loadDashboard);

  function renderDashboard(d) {
    el("statTotalCandidates").textContent = d.total_candidates;
    el("statTotalSessions").textContent = d.total_sessions;
    el("statAvgScore").textContent = d.total_candidates ? `${Math.round(d.avg_score * 100)}%` : "—";
    const decided = d.approved + d.rejected + d.edited;
    const approvalRate = decided ? Math.round((d.approved / decided) * 100) : 0;
    el("statApprovalRate").textContent = decided ? `${approvalRate}%` : "—";
    el("navCandidateCount").textContent = d.total_candidates;

    drawScoreDistChart(d.score_distribution);
    drawDecisionsChart(d);
    drawCategoriesChart(d.by_category);

    const list = el("recentActivityList");
    list.innerHTML = d.recent_activity.length
      ? d.recent_activity.map((c) => `
        <div class="activity-row">
          <div>
            <div class="activity-name">${c.candidate_name}</div>
            <div class="activity-role">${c.target_category}</div>
          </div>
          <span class="activity-score">${Math.round(c.match_probability * 100)}%</span>
          <span class="status-pill ${c.hitl_status}">${c.hitl_status}</span>
          <span class="activity-role">${new Date(c.created_at).toLocaleDateString()}</span>
        </div>
      `).join("")
      : `<p class="panel-sub">No screenings yet — run one from "New Screening".</p>`;
  }

  function destroyChart(key) { if (state.charts[key]) { state.charts[key].destroy(); } }

  function drawScoreDistChart(dist) {
    destroyChart("scoreDist");
    const ctx = el("chartScoreDist").getContext("2d");
    state.charts.scoreDist = new Chart(ctx, {
      type: "bar",
      data: {
        labels: Object.keys(dist),
        datasets: [{ data: Object.values(dist), backgroundColor: "#C98A3E", borderRadius: 4 }],
      },
      options: chartOpts({ legend: false }),
    });
  }

  function drawDecisionsChart(d) {
    destroyChart("decisions");
    const ctx = el("chartDecisions").getContext("2d");
    state.charts.decisions = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["Approved", "Rejected", "Edited", "Pending"],
        datasets: [{
          data: [d.approved, d.rejected, d.edited, d.pending],
          backgroundColor: ["#3F7D58", "#B3452C", "#C98A3E", "#3A4254"],
          borderWidth: 0,
        }],
      },
      options: { ...chartOpts({ legend: true }), cutout: "65%" },
    });
  }

  function drawCategoriesChart(byCategory) {
    destroyChart("categories");
    const ctx = el("chartCategories").getContext("2d");
    const top = byCategory.slice(0, 10);
    state.charts.categories = new Chart(ctx, {
      type: "bar",
      data: {
        labels: top.map((c) => c.target_category),
        datasets: [{ data: top.map((c) => c.n), backgroundColor: "#4A7FA6", borderRadius: 4 }],
      },
      options: { ...chartOpts({ legend: false }), indexAxis: "y" },
    });
  }

  function chartOpts({ legend }) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: legend, labels: { color: "#E7E4DA", font: { family: "Inter", size: 11 } } },
      },
      scales: {
        x: { ticks: { color: "#9AA1AE", font: { size: 10.5 } }, grid: { color: "#2B3341" } },
        y: { ticks: { color: "#9AA1AE", font: { size: 10.5 } }, grid: { color: "#2B3341" } },
      },
    };
  }

  // ============================================================
  // NEW SCREENING (intake + queue) — same behaviour as before
  // ============================================================
  const dropzone = el("dropzone");
  const resumeInput = el("resumeInput");
  const fileList = el("fileList");
  const form = el("screenForm");
  const runBtn = el("runBtn");
  const runBtnText = el("runBtnText");
  const candidateGrid = el("candidateGrid");
  const emptyState = el("emptyState");
  const queueTitle = el("queueTitle");
  const queueSub = el("queueSub");
  const downloadBtn = el("downloadReportBtn");

  dropzone.addEventListener("click", () => resumeInput.click());
  dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    addFiles(e.dataTransfer.files);
  });
  resumeInput.addEventListener("change", () => addFiles(resumeInput.files));

  function addFiles(fileListObj) {
    for (const f of fileListObj) state.files.push(f);
    renderFileList();
  }
  function renderFileList() {
    fileList.innerHTML = "";
    state.files.forEach((f, i) => {
      const li = document.createElement("li");
      li.innerHTML = `<span>${f.name}</span>`;
      const btn = document.createElement("button");
      btn.className = "remove-file";
      btn.textContent = "✕";
      btn.onclick = () => { state.files.splice(i, 1); renderFileList(); };
      li.appendChild(btn);
      fileList.appendChild(li);
    });
  }

  el("loadSampleJD").addEventListener("click", async () => {
    const text = await fetch("/api/sample/job_description").then((r) => (r.ok ? r.text() : null)).catch(() => null);
    if (text) { el("jobDescription").value = text; el("targetCategory").value = "Python Developer"; }
    else showToast("Sample JD not available in this deployment.", true);
  });

  el("loadSampleJDAI").addEventListener("click", async () => {
    const text = await fetch("/api/sample/job_description_ai_engineer").then((r) => (r.ok ? r.text() : null)).catch(() => null);
    if (text) { el("jobDescription").value = text; el("targetCategory").value = "AI Engineer"; }
    else showToast("Sample JD not available in this deployment.", true);
  });

  el("loadSampleResumes").addEventListener("click", async () => {
    try {
      const [strong, weak] = await Promise.all([
        fetch("/api/sample/strong_fit").then((r) => r.text()),
        fetch("/api/sample/weak_fit").then((r) => r.text()),
      ]);
      state.files.push(
        new File([strong], "sample_strong_fit.txt", { type: "text/plain" }),
        new File([weak], "sample_weak_fit.txt", { type: "text/plain" }),
      );
      renderFileList();
      showToast("Loaded 2 sample resumes from the real dataset.");
    } catch { showToast("Could not load sample resumes.", true); }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const jobDescription = el("jobDescription").value.trim();
    if (!jobDescription) return showToast("Paste a job description first.", true);
    if (state.files.length === 0) return showToast("Add at least one resume.", true);

    runBtn.disabled = true;
    runBtnText.textContent = "Screening…";

    const fd = new FormData();
    fd.append("job_description", jobDescription);
    fd.append("target_category", el("targetCategory").value);
    state.files.forEach((f) => fd.append("resumes", f));

    try {
      const res = await fetch("/api/screen", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Screening failed.");

      state.sessionId = data.session_id;
      state.targetCategory = data.target_category;
      state.candidates = data.candidates;

      renderQueue();
      downloadBtn.disabled = false;

      if (data.errors && data.errors.length) showToast(`${data.errors.length} file(s) skipped — check format.`, true);
      else showToast(`Screened ${data.candidates.length} candidate(s) for ${data.target_category}.`);
    } catch (err) {
      showToast(err.message || "Something went wrong.", true);
    } finally {
      runBtn.disabled = false;
      runBtnText.textContent = "Run screening";
    }
  });

  function renderQueue() {
    emptyState.style.display = state.candidates.length ? "none" : "block";
    queueTitle.textContent = `Candidate queue — ${state.targetCategory}`;
    queueSub.textContent = `${state.candidates.length} candidate(s), ranked by match score`;
    candidateGrid.innerHTML = "";
    state.candidates.slice().sort((a, b) => b.match_probability - a.match_probability)
      .forEach((c) => candidateGrid.appendChild(dossierCard(c)));
  }

  function dossierCard(c) {
    const card = document.createElement("div");
    card.className = "dossier";
    const matchedChips = c.matched_skills.slice(0, 4).map((s) => `<span class="chip matched">${s}</span>`).join("");
    const extra = c.matched_skills.length > 4 ? `<span class="chip">+${c.matched_skills.length - 4} more</span>` : "";
    const stamp = c.hitl_status !== "pending" ? `<div class="stamp ${c.hitl_status}">${c.hitl_status}</div>` : "";
    card.innerHTML = `
      ${stamp}
      <div class="dossier-top">
        <div><p class="dossier-name">${c.candidate_name}</p><p class="dossier-role">${c.target_category}</p></div>
        ${gaugeSVG(c.match_probability)}
      </div>
      <div class="dossier-skills">${matchedChips}${extra}</div>
      <div class="dossier-footer">${c.filename} · ${c.years_experience}+ yrs signal</div>
    `;
    card.addEventListener("click", () => openDrawer(c));
    return card;
  }

  downloadBtn.addEventListener("click", () => {
    if (!state.sessionId) return;
    window.location.href = `/api/report/${state.sessionId}`;
  });

  // ============================================================
  // DRAWER (shared by screening queue, candidates table, history)
  // ============================================================
  const drawer = el("drawer");
  const drawerBackdrop = el("drawerBackdrop");
  const drawerContent = el("drawerContent");

  function openDrawer(c) {
    drawer.classList.add("open");
    drawerBackdrop.classList.add("open");

    const xaiRows = c.xai_breakdown.map((r) => `
      <div class="xai-row">
        <span>${r.label}</span><span class="impact">${r.impact_pct}%</span>
        <div class="bar-track"><div class="bar-fill" style="width:${Math.min(r.impact_pct, 100)}%"></div></div>
      </div>`).join("");

    const topCats = c.top_categories.map((t) => `
      <div class="top-cat-row"><span>${t.category}</span><span>${(t.probability * 100).toFixed(1)}%</span></div>`).join("");

    const matched = c.matched_skills.map((s) => `<span class="chip matched">${s}</span>`).join("") || "<span class='chip'>None detected</span>";
    const missing = c.missing_skills.map((s) => `<span class="chip">${s}</span>`).join("") || "<span class='chip'>None</span>";

    drawerContent.innerHTML = `
      <h2>${c.candidate_name}</h2>
      <p class="role-line">${c.filename} · Target role: ${c.target_category}</p>
      <div class="score-hero">
        ${gaugeSVG(c.match_probability, 64)}
        <div><div class="num">${Math.round(c.match_probability * 100)}%</div><div class="label">Match probability</div></div>
      </div>
      <section><h3>AI explanation</h3><p class="explanation-text">${c.ai_explanation}</p></section>
      <section><h3>Why this score</h3>${xaiRows}</section>
      <section><h3>Closest job categories (ANN output)</h3><div class="top-categories">${topCats}</div></section>
      <section><h3>Matched skills</h3><div class="dossier-skills">${matched}</div></section>
      <section><h3>Missing skills</h3><div class="dossier-skills">${missing}</div></section>
      <section>
        <h3>Human-in-the-loop decision</h3>
        <div class="hitl-actions">
          <button class="hitl-btn approve ${c.hitl_status === 'approved' ? 'active' : ''}" data-decision="approved">Approve</button>
          <button class="hitl-btn edit ${c.hitl_status === 'edited' ? 'active' : ''}" data-decision="edited">Edit</button>
          <button class="hitl-btn reject ${c.hitl_status === 'rejected' ? 'active' : ''}" data-decision="rejected">Reject</button>
        </div>
        <textarea class="note-field" id="hitlNote" rows="2" placeholder="Optional note for the report…">${c.hitl_note || ""}</textarea>
      </section>
    `;
    drawerContent.querySelectorAll(".hitl-btn").forEach((btn) => {
      btn.addEventListener("click", () => submitHitl(c.id, btn.dataset.decision));
    });
  }

  async function submitHitl(candidateId, decision) {
    const note = el("hitlNote") ? el("hitlNote").value : "";
    try {
      const res = await fetch(`/api/hitl/${candidateId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, note }),
      });
      const updated = await res.json();
      if (!res.ok) throw new Error(updated.error || "Could not save decision.");

      const idx = state.candidates.findIndex((x) => x.id === candidateId);
      if (idx !== -1) { state.candidates[idx] = updated; renderQueue(); }
      state.allCandidatesCache[candidateId] = updated;

      openDrawer(updated);
      showToast(`Marked as ${decision}.`);
    } catch (err) { showToast(err.message, true); }
  }

  el("drawerClose").addEventListener("click", closeDrawer);
  drawerBackdrop.addEventListener("click", closeDrawer);
  function closeDrawer() { drawer.classList.remove("open"); drawerBackdrop.classList.remove("open"); }

  // ============================================================
  // CANDIDATES (all, search & filter, compare selection)
  // ============================================================
  const candSearch = el("candSearch");
  const candStatusFilter = el("candStatusFilter");
  const candCategoryFilter = el("candCategoryFilter");
  const candidatesTableBody = el("candidatesTableBody");
  const candidatesEmptyState = el("candidatesEmptyState");
  const compareSelectedBtn = el("compareSelectedBtn");
  const compareCount = el("compareCount");

  let searchDebounce;
  [candSearch].forEach((input) => input.addEventListener("input", () => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(loadAllCandidates, 250);
  }));
  [candStatusFilter, candCategoryFilter].forEach((sel) => sel.addEventListener("change", loadAllCandidates));

  function loadAllCandidates() {
    const params = new URLSearchParams({
      search: candSearch.value.trim(),
      status: candStatusFilter.value,
      category: candCategoryFilter.value,
    });
    fetch(`/api/all-candidates?${params}`)
      .then((r) => r.json())
      .then(renderCandidatesTable)
      .catch(() => showToast("Could not load candidates.", true));
  }

  function renderCandidatesTable(rows) {
    candidatesEmptyState.style.display = rows.length ? "none" : "block";
    candidatesTableBody.innerHTML = rows.map((c) => {
      state.allCandidatesCache[c.id] = c;
      const checked = state.compareSelection.has(c.id) ? "checked" : "";
      return `
        <tr data-id="${c.id}">
          <td><input type="checkbox" class="compare-check" data-id="${c.id}" ${checked}></td>
          <td>${c.candidate_name}<br><span class="mono-line">${c.filename}</span></td>
          <td>${c.target_category}</td>
          <td class="score-cell">${Math.round(c.match_probability * 100)}%</td>
          <td><span class="status-pill ${c.hitl_status}">${c.hitl_status}</span></td>
          <td class="mono-line">${new Date(c.created_at).toLocaleDateString()}</td>
        </tr>`;
    }).join("");

    candidatesTableBody.querySelectorAll("tr").forEach((tr) => {
      tr.addEventListener("click", (e) => {
        if (e.target.classList.contains("compare-check")) return;
        openDrawer(state.allCandidatesCache[tr.dataset.id]);
      });
    });
    candidatesTableBody.querySelectorAll(".compare-check").forEach((cb) => {
      cb.addEventListener("change", () => {
        if (cb.checked) state.compareSelection.add(cb.dataset.id);
        else state.compareSelection.delete(cb.dataset.id);
        updateCompareButton();
      });
    });
    updateCompareButton();
  }

  function updateCompareButton() {
    const n = state.compareSelection.size;
    compareCount.textContent = n;
    compareSelectedBtn.disabled = n < 2;
  }

  compareSelectedBtn.addEventListener("click", () => {
    switchView("compare");
    renderCompareView();
  });

  // ============================================================
  // COMPARE VIEW
  // ============================================================
  function renderCompareView() {
    const ids = Array.from(state.compareSelection);
    const candidates = ids.map((id) => state.allCandidatesCache[id]).filter(Boolean);
    const table = el("compareTable");
    const empty = el("compareEmpty");

    if (candidates.length < 2) {
      table.style.display = "none";
      empty.style.display = "block";
      return;
    }
    empty.style.display = "none";
    table.style.display = "table";

    const rows = [
      { label: "Target role", get: (c) => c.target_category },
      { label: "Match score", get: (c) => `${Math.round(c.match_probability * 100)}%` },
      ...Object.entries(FEATURE_LABELS).map(([key, label]) => ({
        label,
        get: (c) => {
          const row = c.xai_breakdown.find((r) => r.feature === key);
          return row ? `${row.value} (${row.impact_pct}%)` : "—";
        },
      })),
      { label: "Matched skills", get: (c) => c.matched_skills.join(", ") || "—" },
      { label: "Missing skills", get: (c) => c.missing_skills.join(", ") || "—" },
      { label: "Human decision", get: (c) => c.hitl_status },
    ];

    let html = "<thead><tr><th>Signal</th>";
    candidates.forEach((c) => { html += `<th>${c.candidate_name}</th>`; });
    html += "</tr></thead><tbody>";
    rows.forEach((row) => {
      html += `<tr><td>${row.label}</td>`;
      candidates.forEach((c) => { html += `<td>${row.get(c)}</td>`; });
      html += "</tr>";
    });
    html += "</tbody>";
    table.innerHTML = html;
  }

  // ============================================================
  // SESSION HISTORY
  // ============================================================
  function loadSessions() {
    fetch("/api/sessions").then((r) => r.json()).then(renderSessions).catch(() => showToast("Could not load sessions.", true));
  }

  function renderSessions(sessions) {
    const list = el("sessionList");
    if (!sessions.length) {
      list.innerHTML = `<div class="empty-state"><span class="empty-icon">◷</span><p>No sessions yet — run a screening first.</p></div>`;
      return;
    }
    list.innerHTML = sessions.map((s) => `
      <div class="session-card" data-id="${s.id}">
        <div>
          <p class="session-role">${s.target_category}</p>
          <p class="session-meta">${new Date(s.created_at).toLocaleString()} · ${s.candidate_count} candidate(s)</p>
        </div>
        <div class="session-stat">
          <div class="n">${s.avg_score ? Math.round(s.avg_score * 100) : 0}%</div>
          <div class="label">avg score</div>
        </div>
      </div>
    `).join("");

    list.querySelectorAll(".session-card").forEach((card) => {
      card.addEventListener("click", () => reopenSession(card.dataset.id));
    });
  }

  async function reopenSession(sessionId) {
    try {
      const res = await fetch(`/api/candidates/${sessionId}`);
      const data = await res.json();
      if (!res.ok) throw new Error("Could not load this session.");
      state.sessionId = data.session.id;
      state.targetCategory = data.session.target_category;
      state.candidates = data.candidates;
      downloadBtn.disabled = false;
      switchView("screening");
      renderQueue();
      showToast(`Reopened session — ${data.candidates.length} candidate(s).`);
    } catch (err) { showToast(err.message, true); }
  }

  // ============================================================
  // MODEL INFO
  // ============================================================
  function loadModelInfo() {
    Promise.all([
      fetch("/api/model-info").then((r) => r.json()),
      fetch("/api/scoring-weights").then((r) => r.json()),
    ]).then(([info, weights]) => {
      el("modelAccuracy").textContent = `${(info.test_accuracy * 100).toFixed(1)}%`;
      el("modelSamples").textContent = info.n_samples;
      el("modelCategories").textContent = info.n_categories;
      el("modelArchitecture").textContent = info.architecture;
      el("modelDataset").textContent = info.dataset;

      el("modelWeights").innerHTML = Object.entries(weights).map(([k, v]) => `
        <div class="weight-row"><span>${FEATURE_LABELS[k] || k}</span><span>${Math.round(v * 100)}%</span></div>
      `).join("");

      el("modelCategoryChips").innerHTML = info.categories.map((c) => `<span class="chip">${c}</span>`).join("");
    }).catch(() => showToast("Could not load model info.", true));
  }

  // ============================================================
  // INIT
  // ============================================================
  switchView("dashboard");
})();
