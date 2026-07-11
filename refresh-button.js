// ============================================================
// XAU Master Dashboard — Frissítés gomb (egygombos teljes refresh)
// Indítja a full-refresh GitHub Actions workflow-t, majd követi az állapotát.
// PAT a böngésző memóriájában él (NEM localStorage — sandbox-biztos).
// ============================================================
(function () {
  const OWNER = "bagiramester";
  const REPO  = "xau-master-dashboard";
  const WF     = "full-refresh.yml";
  const BRANCH = "main";

  let PAT = null;               // memóriában tartott token
  const btn = document.getElementById("refresh-btn");
  const statusEl = document.getElementById("refresh-status");

  const setState = (label, cls) => {
    btn.textContent = label;
    statusEl.className = "refresh-state " + (cls || "");
    btn.disabled = (cls === "running");
  };

  async function api(path, opts = {}) {
    const res = await fetch(`https://api.github.com${path}`, {
      ...opts,
      headers: {
        "Authorization": `Bearer ${PAT}`,
        "Accept": "application/vnd.github+json",
        ...(opts.headers || {}),
      },
    });
    if (!res.ok && res.status !== 204) throw new Error(`GitHub API ${res.status}`);
    return res.status === 204 ? null : res.json();
  }

  // Workflow indítás
  async function dispatch() {
    await api(`/repos/${OWNER}/${REPO}/actions/workflows/${WF}/dispatches`, {
      method: "POST",
      body: JSON.stringify({ ref: BRANCH }),
    });
  }

  // Futó run figyelése — a jobok neve alapján mutatjuk az állapotot
  async function pollRun() {
    const STAGES = {
      "collect-data":   "Adatgyűjtés…",
      "assemble-state": "Állapot építése…",
      "bagira-ai":      "Bagira elemez…",
      "validate-and-push": "Ellenőrzés…",
    };
    for (let i = 0; i < 60; i++) {          // max ~5 perc (5s * 60)
      await new Promise(r => setTimeout(r, 5000));
      const runs = await api(`/repos/${OWNER}/${REPO}/actions/workflows/${WF}/runs?per_page=1`);
      const run = runs.workflow_runs && runs.workflow_runs[0];
      if (!run) continue;

      if (run.status === "completed") {
        if (run.conclusion === "success") { setState("✅ Kész", "done"); await reloadData(); return; }
        setState("⚠️ Hiba", "error"); return;
      }
      // aktuális futó job kikeresése
      const jobs = await api(`/repos/${OWNER}/${REPO}/actions/runs/${run.id}/jobs`);
      const active = (jobs.jobs || []).find(j => j.status === "in_progress");
      if (active && STAGES[active.name]) setState(STAGES[active.name], "running");
    }
    setState("⚠️ Időtúllépés", "error");
  }

  // Friss data.json betöltése cache-busterrel
  async function reloadData() {
    const res = await fetch(`./data.json?ts=${Date.now()}`);
    const data = await res.json();
    if (window.renderDashboard) window.renderDashboard(data);   // a te render függvényed
  }

  btn.addEventListener("click", async () => {
    try {
      if (!PAT) {
        PAT = window.prompt("Add meg a GitHub PAT-ot (Actions: read/write):");
        if (!PAT) return;
      }
      setState("Adatgyűjtés…", "running");
      await dispatch();
      await pollRun();
    } catch (e) {
      setState("⚠️ Hiba", "error");
      console.error(e);
      PAT = null;   // hibás token esetén újrakérjük
    }
  });
})();
