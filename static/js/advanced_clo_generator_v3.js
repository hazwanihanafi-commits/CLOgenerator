/* advanced_clo_generator_v2.js
   Multi-level PEO–IEG–PLO Auto-Linker (Diploma/Degree/Master/PhD)
   Loads: /static/data/peo_plo_ieg.json
   Automatically maps: IEG → PEO → PLO → SC/VBE/Indicators
   Safe: Uses its own IDs (al_*) so it never touches main CLO UI
*/

(function () {
  "use strict";

  console.log("Advanced CLO Auto-Linker v2 loaded ✔");

  /* -------------------------------------------------------
     Find container in generator.html
  ------------------------------------------------------- */
  const mountPoint = document.getElementById("advanced-clo-generator");
  if (!mountPoint) {
    console.warn("⚠ No mount point for Auto-Linker (#advanced-clo-generator).");
    return;
  }

  /* -------------------------------------------------------
     Build UI Box (non-invasive)
  ------------------------------------------------------- */
  const box = document.createElement("div");
  box.style.background = "#fafafa";
  box.style.padding = "16px";
  box.style.border = "1px solid #e5e5e5";
  box.style.borderRadius = "10px";
  box.style.marginTop = "16px";
  box.style.marginBottom = "24px";
  box.style.boxShadow = "0 1px 3px rgba(0,0,0,0.05)";

  box.innerHTML = `
      <h5 class="fw-bold mb-2">
        ⚡ Advanced PLO Auto-Linker
      </h5>
      <div class="text-muted small mb-3">
        Auto-maps: IEG → PEO → PLO → SC / VBE / Indicator  
      </div>

      <div class="row g-3">
        <div class="col-md-4">
          <label class="form-label">Programme Level</label>
          <select id="al_level" class="form-select">
            <option>Diploma</option>
            <option selected>Degree</option>
            <option>Master</option>
            <option>PhD</option>
          </select>
        </div>

        <div class="col-md-4">
          <label class="form-label">Select PEO</label>
          <select id="al_peo" class="form-select">
            <option value="" disabled selected>-- choose PEO --</option>
          </select>
        </div>

      <hr>
      <div id="al_output"></div>
  `;

  mountPoint.appendChild(box);

  /* -------------------------------------------------------
      LOAD MAIN JSON
  ------------------------------------------------------- */
  let MAP = null;

  async function loadMapping() {
    try {
      const res = await fetch("/static/data/peo_plo_ieg.json", { cache: "no-store" });
      MAP = await res.json();

      const saved = localStorage.getItem("USMMapping");
      if (saved) Object.assign(MAP, JSON.parse(saved));

      populatePEOs();
      console.log("Loaded mapping JSON ✔");

    } catch (e) {
      console.error("❌ Failed loading mapping:", e);
    }
  }

  /* -------------------------------------------------------
      POPULATE PEO DROPDOWN
  ------------------------------------------------------- */
  function populatePEOs() {
    const sel = document.getElementById("al_peo");

    sel.innerHTML = `<option value="" disabled selected>-- choose PEO --</option>`;

    Object.keys(MAP?.PEOtoPLO || {}).forEach(peo => {
      const opt = document.createElement("option");
      opt.value = peo;
      opt.textContent = peo;
      sel.appendChild(opt);
    });
  }

  /* -------------------------------------------------------
     Update Mapping Preview
  ------------------------------------------------------- */
  const output = document.getElementById("al_output");

  function showMapping(peo, level) {
    if (!peo || !level) return;

    const plos = MAP.PEOtoPLO?.[peo] || [];
    const peoStatement = MAP.PEOstatements?.[level]?.[peo] || "(no PEO statement)";

    const iegList = Object.keys(MAP.IEGtoPEO || {})
      .filter(ieg => MAP.IEGtoPEO[ieg].includes(peo));

    output.innerHTML = `
      <div class="card card-body shadow-sm border-0">
        <h6 class="fw-bold text-primary">${peo} — ${level} Level</h6>
        <p class="text-muted small">${peoStatement}</p>

        <h6 class="fw-bold mt-3">Mapped IEG(s)</h6>
        ${iegList.map(i => `<span class="badge bg-info me-1">${i}</span>`).join("")}

        <h6 class="fw-bold mt-3">Mapped PLO(s)</h6>
        ${plos.map(p => `
          <div class="border rounded p-2 mb-2">
            <strong>${p}</strong><br>
            <small class="text-muted">
              ${MAP.PLOstatements?.[level]?.[p] || "(no PLO statement)"}
            </small><br>
            <span class="badge bg-warning text-dark mt-1">SC: ${MAP.SCmapping?.[p] || "-"}</span>
            <span class="badge bg-secondary mt-1">VBE: ${MAP.PLOtoVBE?.[p] || "-"}</span>
            <span class="badge bg-success mt-1">Indicator: ${MAP.PLOIndicators?.[p] || "-"}</span>
          </div>
        `).join("")}
      </div>
    `;
  }

  /* -------------------------------------------------------
      LISTENERS
  ------------------------------------------------------- */
  document.getElementById("al_peo").addEventListener("change", () => {
    showMapping(
      document.getElementById("al_peo").value,
      document.getElementById("al_level").value
    );
  });

  document.getElementById("al_level").addEventListener("change", () => {
    showMapping(
      document.getElementById("al_peo").value,
      document.getElementById("al_level").value
    );
  });
document.addEventListener("DOMContentLoaded", async () => {

    console.log("Advanced CLO Generator v3 Loaded");

    /* ============================================================
       LOAD MAPPING JSON (IEG → PEO → PLO)
    ============================================================ */
    let mapping = {};
    try {
        const res = await fetch("/static/data/peo_plo_ieg.json", { cache: "no-store" });
        mapping = await res.json();
        console.log("Mapping loaded:", mapping);
    } catch (err) {
        console.error("Error loading mapping JSON:", err);
        return;
    }

    /* ============================================================
       SELECT ELEMENTS
    ============================================================ */
    const iegSel   = document.getElementById("ieg");
    const peoSel   = document.getElementById("peo");
    const ploSel   = document.getElementById("plo");

    const bloomSel = document.getElementById("bloom");
    const verbSel  = document.getElementById("verb");

    const scCode   = document.getElementById("sc_code");
    const scDesc   = document.getElementById("sc_desc");
    const vbe      = document.getElementById("vbe");
    const domain   = document.getElementById("domain");
    const condEl   = document.getElementById("condition");
    const critEl   = document.getElementById("criterion");
    const assessEl = document.getElementById("assessment");
    const evidEl   = document.getElementById("evidence");

    const profileSel = document.getElementById("profile");
    const profileHidden = document.getElementById("profileHidden");

    /* ============================================================
       HELPER: Profile suffix
    ============================================================ */
    function suffix() {
        const p = profileHidden.value || profileSel.value;
        return p ? `?profile=${p}` : "";
    }

    async function fetchJSON(url) {
        const r = await fetch(url);
        return r.ok ? r.json() : null;
    }

    /* ============================================================
       POPULATE IEG
    ================

  loadMapping();
})();
