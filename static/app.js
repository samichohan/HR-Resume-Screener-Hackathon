(() => {
  const state = {
    sessionId: null,
    targetCategory: null,
    candidates: [],
    files: [],
  };

  const el = (id) => document.getElementById(id);
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
  const drawer = el("drawer");
  const drawerBackdrop = el("drawerBackdrop");
  const drawerContent = el("drawerContent");
  const toastEl = el("toast");

  // ---------- model badge ----------
  fetch("/api/model-info")
    .then((r) => r.json())
    .then((info) => {
      const badge = el("modelBadge");
      badge.classList.remove("loading");
      el("modelBadgeText").textContent =
        `ANN live · ${(info.test_accuracy * 100).toFixed(1)}% test accuracy · ${info.n_samples} real resumes`;
    })
    .catch(() => {
      el("modelBadgeText").textContent = "Model status unavailable";
    });

  // ---------- dropzone ----------
  dropzone.addEventListener("click", () => resumeInput.click());
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
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

  // ---------- sample data ----------
  el("loadSampleJD").addEventListener("click", async () => {
    const text = await fetch("/api/sample/job_description")
      .then((r) => (r.ok ? r.text() : null))
      .catch(() => null);
    if (text) {
      el("jobDescription").value = text;
      el("targetCategory").value = "Python Developer";
    } else {
      showToast("Sample JD not available in this deployment.", true);
    }
  });

  el("loadSampleJDAI").addEventListener("click", async () => {
    const text = await fetch("/api/sample/job_description_ai_engineer")
      .then((r) => (r.ok ? r.text() : null))
      .catch(() => null);
    if (text) {
      el("jobDescription").value = text;
      el("targetCategory").value = "AI Engineer";
    } else {
      showToast("Sample JD not available in this deployment.", true);
    }
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
    } catch {
      showToast("Could not load sample resumes.", true);
    }
  });

  // ---------- submit ----------
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

      if (data.errors && data.errors.length) {
        showToast(`${data.errors.length} file(s) skipped — check format.`, true);
      } else {
        showToast(`Screened ${data.candidates.length} candidate(s) for ${data.target_category}.`);
      }
    } catch (err) {
      showToast(err.message || "Something went wrong.", true);
    } finally {
      runBtn.disabled = false;
      runBtnText.textContent = "Run screening";
    }
  });

  // ---------- render queue ----------
  function renderQueue() {
    emptyState.style.display = state.candidates.length ? "none" : "block";
    queueTitle.textContent = `Candidate queue — ${state.targetCategory}`;
    queueSub.textContent = `${state.candidates.length} candidate(s), ranked by match score`;
    candidateGrid.innerHTML = "";
    state.candidates
      .slice()
      .sort((a, b) => b.match_probability - a.match_probability)
      .forEach((c) => candidateGrid.appendChild(dossierCard(c)));
  }

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

  function dossierCard(c) {
    const card = document.createElement("div");
    card.className = "dossier";
    const matchedChips = c.matched_skills.slice(0, 4)
      .map((s) => `<span class="chip matched">${s}</span>`).join("");
    const extra = c.matched_skills.length > 4 ? `<span class="chip">+${c.matched_skills.length - 4} more</span>` : "";

    const stamp = c.hitl_status !== "pending"
      ? `<div class="stamp ${c.hitl_status}">${c.hitl_status}</div>` : "";

    card.innerHTML = `
      ${stamp}
      <div class="dossier-top">
        <div>
          <p class="dossier-name">${c.candidate_name}</p>
          <p class="dossier-role">${c.target_category}</p>
        </div>
        ${gaugeSVG(c.match_probability)}
      </div>
      <div class="dossier-skills">${matchedChips}${extra}</div>
      <div class="dossier-footer">${c.filename} · ${c.years_experience}+ yrs signal</div>
    `;
    card.addEventListener("click", () => openDrawer(c));
    return card;
  }

  // ---------- drawer ----------
  function openDrawer(c) {
    drawer.classList.add("open");
    drawerBackdrop.classList.add("open");

    const xaiRows = c.xai_breakdown.map((r) => `
      <div class="xai-row">
        <span>${r.label}</span>
        <span class="impact">${r.impact_pct}%</span>
        <div class="bar-track"><div class="bar-fill" style="width:${Math.min(r.impact_pct, 100)}%"></div></div>
      </div>
    `).join("");

    const topCats = c.top_categories.map((t) => `
      <div class="top-cat-row"><span>${t.category}</span><span>${(t.probability * 100).toFixed(1)}%</span></div>
    `).join("");

    const matched = c.matched_skills.map((s) => `<span class="chip matched">${s}</span>`).join("") || "<span class='chip'>None detected</span>";
    const missing = c.missing_skills.map((s) => `<span class="chip">${s}</span>`).join("") || "<span class='chip'>None</span>";

    drawerContent.innerHTML = `
      <h2>${c.candidate_name}</h2>
      <p class="role-line">${c.filename} · Target role: ${c.target_category}</p>

      <div class="score-hero">
        ${gaugeSVG(c.match_probability, 64)}
        <div>
          <div class="num">${Math.round(c.match_probability * 100)}%</div>
          <div class="label">Match probability</div>
        </div>
      </div>

      <section>
        <h3>AI explanation</h3>
        <p class="explanation-text">${c.ai_explanation}</p>
      </section>

      <section>
        <h3>Why this score</h3>
        ${xaiRows}
      </section>

      <section>
        <h3>Closest job categories (ANN output)</h3>
        <div class="top-categories">${topCats}</div>
      </section>

      <section>
        <h3>Matched skills</h3>
        <div class="dossier-skills">${matched}</div>
      </section>

      <section>
        <h3>Missing skills</h3>
        <div class="dossier-skills">${missing}</div>
      </section>

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
      if (idx !== -1) state.candidates[idx] = updated;
      renderQueue();
      openDrawer(updated);
      showToast(`Marked as ${decision}.`);
    } catch (err) {
      showToast(err.message, true);
    }
  }

  el("drawerClose").addEventListener("click", closeDrawer);
  drawerBackdrop.addEventListener("click", closeDrawer);
  function closeDrawer() {
    drawer.classList.remove("open");
    drawerBackdrop.classList.remove("open");
  }

  // ---------- report ----------
  downloadBtn.addEventListener("click", () => {
    if (!state.sessionId) return;
    window.location.href = `/api/report/${state.sessionId}`;
  });

  // ---------- toast ----------
  let toastTimer;
  function showToast(msg, isError = false) {
    clearTimeout(toastTimer);
    toastEl.textContent = msg;
    toastEl.classList.toggle("error", isError);
    toastEl.classList.add("show");
    toastTimer = setTimeout(() => toastEl.classList.remove("show"), 3200);
  }
})();
