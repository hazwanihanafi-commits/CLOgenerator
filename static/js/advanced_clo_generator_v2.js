/* advanced_clo_generator_v2.js
   Multi-level PEO–IEG–PLO Auto-Linker (Diploma/Degree/Master/PhD)
   Loads: /static/data/peo_plo_ieg.json
   Automatically maps: IEG → PEO → PLO → SC/VBE/Indicators
   Does NOT interfere with existing Flask CLO Generator UI
*/

(function () {
  "use strict";

  console.log("Advanced CLO Auto-Linker v2 loaded ✔");

  /* -------------------------------------------------------
     Find container for Auto-Linker (non-Invasive Insert)
  ------------------------------------------------------- */
  const mountPoint = document.getElementById("advanced-clo-generator");
  if (!mountPoint) {
    console.warn("⚠ advanced-clo-generator div not found.");
    return;
  }

  /* -------------------------------------------------------
     UI Container
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
        <i class="bi bi-lightning"></i> Advanced CLO Auto-Linker
      </h5>
      <div class="text-muted small mb-3">
        Auto-maps: IEG → PEO → PLO → SC / VBE / Indicator  
        <br>Uses: /static/data/peo_plo_ieg.json + localStorage overrides
      </div>

      <div class="row g-3">

        <div class="col-md-4">
          <label class="form-label">Programme Level</label>
          <select id="al_level" class="form-select">
            <option value="Diploma">Diploma</option>
            <option value="Degree" selected>Degree</option>
            <option value="Master">Master</option>
            <option value="PhD">PhD</option>
          </select>
        </div>

        <div class="col-md-4">
          <label class="form-label">Select PEO</label>
          <select id="al_peo" class="form-select">
            <option value="" selected disabled>-- choose PEO --</option>
          </select>
        </div>

        <div class="col-md-4">
          <label class="form-label">Bloom Level</label>
          <select id="al_bloom" class="form-select">
            <option value="Understand">Understand</option>
            <option value="Apply" selected>Apply</option>
            <option value="Analyze">Analyze</option>
            <option value="Evaluate">Evaluate</option>
            <option value="Create">Create</option>
          </select>
        </div>

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

      // Apply overrides if exist
      const saved = localStorage.getItem("USMMapping");
      if (saved) {
        const override = JSON.parse(saved);
        Object.assign(MAP, override);
        console.log("Applied USMMapping override:", override);
      }

      populatePEOs();
      console.log("Loaded mapping:", MAP);

    } catch (e) {
      console.error("❌ Failed loading mapping:", e);
    }
  }

  /* -------------------------------------------------------
      POPULATE PEO DROPDOWN
  ------------------------------------------------------- */
  function populatePEOs() {
    const sel = document.getElementById("al_peo");
    if (!MAP || !MAP.PEOtoPLO) return;

    sel.innerHTML = `<option value="" disabled selected>-- choose PEO --</option>`;

    Object.keys(MAP.PEOtoPLO).forEach(peo => {
      const opt = document.createElement("option");
      opt.value = peo;
      opt.textContent = peo;
      sel.appendChild(opt);
    });
  }

  /* -------------------------------------------------------
     WHEN PEO SELECTED → Show mapping
  ------------------------------------------------------- */
  const output = document.getElementById("al_output");

  document.getElementById("al_peo").addEventListener("change", () => {
    const peo = document.getElementById("al_peo").value;
    const lvl = document.getElementById("al_level").value;
    showMapping(peo, lvl);
  });

  document.getElementById("al_level").addEventListener("change", () => {
    const peo = document.getElementById("al_peo").value;
    const lvl = document.getElementById("al_level").value;
    if (peo) showMapping(peo, lvl);
  });

  /* -------------------------------------------------------
     Render Mapping Preview
  ------------------------------------------------------- */
  function showMapping(peo, level) {
    const plos = MAP.PEOtoPLO?.[peo] || [];
    const peoStatement = MAP.PEOstatements?.[level]?.[peo] || "(no PEO statement)";
    const iegList = Object.keys(MAP.IEGtoPEO || {})
      .filter(ieg => MAP.IEGtoPEO[ieg].includes(peo));

    const html = `
      <div class="card card-body border-0 shadow-sm">

        <h6 class="fw-bold mb-2 text-primary">${peo} — ${level} Level</h6>
        <p class="small text-muted">${peoStatement}</p>

        <hr>

        <h6 class="fw-bold">Mapped IEG(s)</h6>
        <div class="mb-2">
          ${iegList.map(i => `<span class="badge bg-info me-1">${i}</span>`).join("")}
        </div>

        <h6 class="fw-bold">Mapped PLO(s)</h6>
        <div>
          ${plos.map(p => `
            <div class="border rounded p-2 mb-2">
              <strong>${p}</strong><br>
              <small class="text-muted">
                ${MAP.PLOstatements?.[level]?.[p] || "(no PLO statement)"}
              </small>
              <br>
              <span class="badge bg-warning text-dark mt-1">SC: ${MAP.SCmapping?.[p] || "-"}</span>
              <span class="badge bg-secondary mt-1">VBE: ${MAP.PLOtoVBE?.[p] || "-"}</span>
              <span class="badge bg-success mt-1">Indicator: ${MAP.PLOIndicators?.[p] || "-"}</span>
            </div>
          `).join("")}
        </div>

      </div>
    `;

    output.innerHTML = html;
  }

  loadMapping();

})();
