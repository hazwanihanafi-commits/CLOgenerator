/* advanced_clo_generator.js
   Full multi-level support (Diploma/Degree/Master/PhD).
   Drop into /static/js and the UI will render and load /static/data/peo_plo_ieg.json.
*/

(function () {
  "use strict";

  /* ---------- Utility helpers ---------- */
  function el(tag, attrs = {}, children = []) {
    const e = document.createElement(tag);
    for (const k in attrs) {
      if (k === "class") e.className = attrs[k];
      else if (k === "html") e.innerHTML = attrs[k];
      else if (k === "style") e.style.cssText = attrs[k];
      else e.setAttribute(k, attrs[k]);
    }
    (Array.isArray(children) ? children : [children]).forEach((c) => {
      if (c === null || c === undefined) return;
      if (typeof c === "string") e.appendChild(document.createTextNode(c));
      else e.appendChild(c);
    });
    return e;
  }

  function q(sel, scope = document) { return scope.querySelector(sel); }
  function qa(sel, scope = document) { return Array.from(scope.querySelectorAll(sel)); }

  function fmtDateShort(d = new Date()) { return d.toISOString().slice(0,10); }

  function downloadFile(filename, content, mime = "text/plain") {
    const blob = new Blob([content], { type: mime });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(()=>{ URL.revokeObjectURL(a.href); a.remove(); }, 4000);
  }

  function arrayToCSV(rows) {
    if (!rows || !rows.length) return "";
    const cols = Object.keys(rows[0]);
    const esc = s => (s===null||s===undefined) ? "" : (`"${String(s).replace(/"/g,'""')}"`);
    const header = cols.map(esc).join(",");
    const lines = rows.map(r => cols.map(c => esc(r[c])).join(","));
    return header + "\n" + lines.join("\n");
  }

  /* ---------- Find container ---------- */
  const candidateIds = ["clogenerator","generator-root","app","root","content","main","body"];
  let container = null;
  for (const id of candidateIds) {
    const found = document.getElementById(id);
    if (found) { container = found; break; }
  }
  if (!container) container = document.body;

  /* ---------- App layout ---------- */
  const appWrap = el("div", { class: "clo-generator-wrap", style: "font-family: Arial, sans-serif; max-width:1100px; margin:10px auto; color:#1f2937;" });

  const style = el("style", { html: `
    .clo-card { background:#fff; border:1px solid #e5e7eb; padding:14px; border-radius:8px; box-shadow:0 1px 2px rgba(0,0,0,0.03); }
    .clo-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    .clo-label { font-size:13px; font-weight:600; margin-bottom:6px; display:block; }
    .clo-input, .clo-select, .clo-textarea { width:100%; padding:8px; border:1px solid #d1d5db; border-radius:6px; font-size:14px; }
    .clo-btn { padding:8px 12px; border-radius:6px; border:0; cursor:pointer; }
    .btn-blue { background:#2563eb; color:#fff; }
    .btn-green { background:#059669; color:#fff; }
    .btn-gray { background:#6b7280; color:#fff; }
    .tiny { font-size:12px; color:#374151; }
    .chip { display:inline-block; padding:6px 8px; border-radius:999px; background:#eef2ff; margin:4px 6px 4px 0; font-size:13px; }
    .chip-sc { background:#fef3c7; }
    .list-row { border:1px solid #e6e6e6; padding:8px; border-radius:6px; background:#fbfbfb; margin-bottom:8px; }
    .flex { display:flex; gap:8px; align-items:center; }
    .col { display:flex; flex-direction:column; gap:6px; }
    .muted { color:#6b7280; font-size:13px; }
    .generated-list { max-height:320px; overflow:auto; margin-top:8px; }
  `});

  const header = el("div", { class: "clo-card", style: "margin-bottom:12px" }, [
    el("h2", { html: "Advanced CLO Auto-Linker (No React build required)" }),
    el("div", { class: "muted", html: "Auto-maps: IEG → PEO → PLO (multi-level) → SC/VBE/Indicator. Exports CSV/JSON. Uses localStorage overrides if Mapping Editor saved." })
  ]);

  const bodyCard = el("div", { class: "clo-card" });
  const grid = el("div", { class: "clo-grid" });

  // Left column
  const leftCol = el("div", { class: "col" });

  leftCol.appendChild(el("label", { class: "clo-label" }, "Select PEO"));
  const peoSelect = el("select", { class: "clo-select" }, []);
  leftCol.appendChild(peoSelect);

  leftCol.appendChild(el("label", { class: "clo-label", style: "margin-top:8px" }, "Programme Level"));
  const levelSelect = el("select", { class: "clo-select" }, [
    el("option", { value: "Diploma" }, "Diploma"),
    el("option", { value: "Degree", selected: true }, "Degree"),
    el("option", { value: "Master" }, "Master"),
    el("option", { value: "PhD" }, "PhD")
  ]);
  leftCol.appendChild(levelSelect);

  leftCol.appendChild(el("div", { class: "clo-label" }, "Mapped PLO(s)"));
  const ploChips = el("div", {});
  leftCol.appendChild(ploChips);

  leftCol.appendChild(el("div", { class: "clo-label" }, "Mapped IEG(s)"));
  const iegChips = el("div", {});
  leftCol.appendChild(iegChips);

  leftCol.appendChild(el("div", { class: "clo-label" }, "Bloom level"));
  const bloomSelect = el("select", { class: "clo-select" }, []);
  leftCol.appendChild(bloomSelect);

  leftCol.appendChild(el("div", { class: "clo-label" }, "Override verb (optional)"));
  const verbInput = el("input", { class: "clo-input", placeholder: "e.g., design" });
  leftCol.appendChild(verbInput);

  leftCol.appendChild(el("div", { class: "clo-label" }, "Suggested assessment methods"));
  const assWrap = el("div", {});
  leftCol.appendChild(assWrap);

  // Right column
  const rightCol = el("div", { class: "col" });
  rightCol.appendChild(el("div", { class: "clo-label" }, "Course label (used in CLO)"));
  const courseInput = el("input", { class: "clo-input", value: "[Course Name]" });
  rightCol.appendChild(courseInput);

  const btnRow = el("div", { class: "flex" });
  const genBtn = el("button", { class: "clo-btn btn-blue" }, "Generate CLO");
  const saveBtn = el("button", { class: "clo-btn btn-green" }, "Save CLO");
  btnRow.appendChild(genBtn); btnRow.appendChild(saveBtn);
  rightCol.appendChild(btnRow);

  rightCol.appendChild(el("div", { class: "clo-label", style: "margin-top:8px" }, "Generated CLO"));
  const cloArea = el("textarea", { class: "clo-textarea", rows: 6 });
  rightCol.appendChild(cloArea);

  rightCol.appendChild(el("div", { class: "clo-label", style: "margin-top:6px" }, "Bulk courses (newline or comma separated)"));
  const bulkArea = el("textarea", { class: "clo-textarea", rows: 3 });
  const bulkBtn = el("button", { class: "clo-btn btn-gray" }, "Bulk Generate");
  rightCol.appendChild(bulkArea); rightCol.appendChild(bulkBtn);

  const bottomCard = el("div", { class: "clo-card", style: "margin-top:12px" });
  const genHeader = el("div", { class: "flex" }, [
    el("h3", { html: "Generated CLOs" }),
    el("div", { class: "muted", style: "margin-left:8px" }, "(session only)")
  ]);
  bottomCard.appendChild(genHeader);
  const genList = el("div", { class: "generated-list" });
  bottomCard.appendChild(genList);

  const exportRow = el("div", { class: "flex", style: "margin-top:8px" });
  const exportCsvBtn = el("button", { class: "clo-btn btn-blue" }, "Export CSV");
  const exportJsonBtn = el("button", { class: "clo-btn btn-gray" }, "Export JSON");
  const clearBtn = el("button", { class: "clo-btn", style: "background:#ef4444;color:#fff" }, "Clear All");
  exportRow.appendChild(exportCsvBtn); exportRow.appendChild(exportJsonBtn); exportRow.appendChild(clearBtn);
  bottomCard.appendChild(exportRow);

  grid.appendChild(leftCol); grid.appendChild(rightCol);
  bodyCard.appendChild(grid);
  appWrap.appendChild(style); appWrap.appendChild(header); appWrap.appendChild(bodyCard); appWrap.appendChild(bottomCard);
  container.appendChild(appWrap);

  /* ---------- State ---------- */
  let mapping = null;
  let selectedPEO = "";
  let selectedPLOs = [];
  let selectedIEGs = [];
  let generatedListState = [];

  /* ---------- Static dictionaries ---------- */
  const BLOOM_VERBS = {
    Remember: ["list","name","recall","define"],
    Understand: ["explain","describe","summarize","interpret"],
    Apply: ["apply","demonstrate","use","execute"],
    Analyze: ["analyze","compare","differentiate","organize"],
    Evaluate: ["evaluate","judge","critique","assess"],
    Create: ["design","construct","compose","formulate"]
  };

  const ASSESSMENT_SUGGESTIONS = {
    PLO1: ["Written exam","Open-book exam","Quiz"],
    PLO2: ["Critical review assignment","Journal critique"],
    PLO3: ["Practical test","Lab report","OSCE"],
    PLO4: ["Peer-assessment","Group project"],
    PLO5: ["Presentation","Oral exam","Poster"],
    PLO6: ["Digital portfolio","Data analysis assignment"],
    PLO7: ["Problem set","Calculation test"],
    PLO8: ["Leadership project","Team-based assignment"],
    PLO9: ["Reflective journal","Learning log"],
    PLO10: ["Business plan","Entrepreneurship pitch"],
    PLO11: ["Professional conduct assessment","Case study"]
};

/* ---------- FORCE FRESH MAPPING (Fixes old cached data) ---------- */
localStorage.removeItem("USMMapping");

/* ---------- Load mapping (multi-level aware) ---------- */
function loadMapping() {
    return fetch("/static/data/peo_plo_ieg.json", { cache: "no-store" })
      .then(r => {
        if (!r.ok) throw new Error("Failed to load mapping JSON");
        return r.json();
      })
      .then(json => {
        // base
        let final = json || {};

        // local override merging
        try {
          const saved = localStorage.getItem("USMMapping");
          if (saved) {
            const custom = JSON.parse(saved);
            final.IEGtoPEO      = custom.IEGtoPEO      || final.IEGtoPEO || {};
            final.PEOtoPLO      = custom.PEOtoPLO      || final.PEOtoPLO || {};
            final.PLOstatements = custom.PLOstatements || final.PLOstatements || {};
            final.PEOstatements = custom.PEOstatements || final.PEOstatements || {};
            final.PLOtoVBE      = custom.PLOtoVBE      || final.PLOtoVBE || {};
            final.PLOIndicators = custom.PLOIndicators || final.PLOIndicators || {};
            final.SCmapping     = custom.SCmapping     || final.SCmapping || {};
          } else {
            final.PLOstatements = final.PLOstatements || {};
            final.PEOstatements = final.PEOstatements || {};
            final.PLOtoVBE      = final.PLOtoVBE || {};
            final.PLOIndicators = final.PLOIndicators || {};
            final.SCmapping     = final.SCmapping || {};
          }
        } catch (e) {
          console.warn("USMMapping parse error:", e);
        }

        mapping = final;
        populatePEOSelect();
        populateBloom();
      });
  }

  /* ---------- UI population ---------- */
  function populatePEOSelect() {
    peoSelect.innerHTML = "";
    peoSelect.appendChild(el("option", { value: "" }, "-- choose PEO --"));
    if (!mapping || !mapping.PEOtoPLO) return;
    const peos = Object.keys(mapping.PEOtoPLO);
    peos.forEach(peo => {
      peoSelect.appendChild(el("option", { value: peo }, peo));
    });
  }

  function populateBloom() {
    bloomSelect.innerHTML = "";
    Object.keys(BLOOM_VERBS).forEach(b => {
      bloomSelect.appendChild(el("option", { value: b }, b));
    });
  }

  /* ---------- mapping getters ---------- */
  function getSC(plo) { return mapping?.SCmapping?.[plo] || ""; }
  function getVBE(plo) { return mapping?.PLOtoVBE?.[plo] || ""; }
  function getIndicator(plo) { return mapping?.PLOIndicators?.[plo] || ""; }
  function getPLOStatementForLevel(plo, level) {
    return mapping?.PLOstatements?.[level]?.[plo] || "";
  }
  function getPEOStatementForLevel(peo, level) {
    return mapping?.PEOstatements?.[level]?.[peo] || "";
  }

  /* ---------- render functions ---------- */
  function renderSelectedPLOs() {
    ploChips.innerHTML = "";
    selectedPLOs.forEach(p => {
      const sc = getSC(p);
      const vbe = getVBE(p);
      const chip = el("div", { class: "chip" }, [
        el("div", { html: p + (vbe ? (" — " + vbe) : "") }),
        sc ? el("div", { class: "tiny chip-sc", html: "SC: " + sc }) : null
      ]);
      ploChips.appendChild(chip);
    });
  }

  function renderIEGs() {
    iegChips.innerHTML = "";
    selectedIEGs.forEach(i => {
      iegChips.appendChild(el("span", { class: "chip", html: i }));
    });
  }

  function renderAssessmentSuggestions() {
    assWrap.innerHTML = "";
    const suggestions = selectedPLOs.flatMap(p => ASSESSMENT_SUGGESTIONS[p] || []);
    const uniq = Array.from(new Set(suggestions)).slice(0,6);
    uniq.forEach(s => {
      const b = el("button", { class: "clo-btn", style:"background:#f3f4f6;border:1px solid #e5e7eb;margin-right:6px" }, s);
      b.addEventListener("click", () => {
        cloArea.value = cloArea.value + (cloArea.value ? "\n" : "") + "Assessment: " + s;
      });
      assWrap.appendChild(b);
    });
  }

  /* ---------- CLO generation (multi-level) ---------- */
  function generateCLO(courseLabel) {
    if (!selectedPLOs || !selectedPLOs.length) {
      alert("Please select a PEO (which auto-populates PLOs)");
      return "";
    }

    const verb = (verbInput.value && verbInput.value.trim()) ? verbInput.value.trim() : (BLOOM_VERBS[bloomSelect.value]?.[0] || "demonstrate");
    const level = levelSelect.value || "Degree";

    const plostmts = selectedPLOs.map(p => getPLOStatementForLevel(p, level)).filter(Boolean);
    const ploWithSC = selectedPLOs.map(p => {
      const sc = getSC(p); return sc ? `${p} (SC: ${sc})` : p;
    }).join(", ");

    const plostmtText = plostmts.length ? ("PLO statements: " + plostmts.join("; ")) : "";
    const vbedomains = Array.from(new Set(selectedPLOs.map(p => getVBE(p)).filter(Boolean))).join(", ");
    const indicators = selectedPLOs.map(p => `${p}: ${getIndicator(p) || "(no indicator set)"}`).join("; ");

    const text = `Upon successful completion of ${courseLabel}, students will be able to ${verb} competencies related to ${ploWithSC}. ${plostmtText} This aligns to ${selectedPEO || "the programme PEO(s)"} and develops graduate attributes: ${selectedIEGs.join(", ") || "N/A"}. VBE domain(s): ${vbedomains || "N/A"}. Performance indicators: ${indicators}.`.trim();

    cloArea.value = text;
    return text;
  }

  /* ---------- Save / Render generated ---------- */
  function saveGenerated(courseLabel) {
    const txt = cloArea.value.trim();
    if (!txt) { alert("No CLO to save. Generate one first."); return; }
    const item = {
      course: courseLabel || courseInput.value || "[Course Name]",
      level: levelSelect.value || "Degree",
      peo: selectedPEO,
      plos: selectedPLOs.slice(),
      sc: selectedPLOs.map(p => getSC(p)),
      vbe: selectedPLOs.map(p => getVBE(p)),
      indicators: selectedPLOs.map(p => getIndicator(p)),
      clo: txt,
      savedAt: new Date().toISOString()
    };
    generatedListState.push(item);
    renderGeneratedList();
    cloArea.value = "";
  }

  function renderGeneratedList() {
    genList.innerHTML = "";
    generatedListState.forEach((g, idx) => {
      const row = el("div", { class: "list-row" }, [
        el("div", { class: "flex", html: `<strong>${g.course}</strong>` }),
        el("div", { class: "muted", html: `PEO: ${g.peo} • Level: ${g.level} • PLOs: ${g.plos.join(", ")}` }),
        el("div", { html: g.clo }),
        el("div", { class: "flex" }, [
          el("button", { class: "clo-btn", style: "background:#ef4444;color:#fff" }, "Delete"),
          el("button", { class: "clo-btn", style: "background:#6b7280;color:#fff;margin-left:6px" }, "Copy")
        ])
      ]);

      row.querySelectorAll("button")[0].addEventListener("click", () => {
        generatedListState.splice(idx,1); renderGeneratedList();
      });
      row.querySelectorAll("button")[1].addEventListener("click", () => {
        navigator.clipboard.writeText(g.clo).then(()=> alert("CLO copied to clipboard"));
      });

      genList.appendChild(row);
    });
  }

  /* ---------- Exporters ---------- */
  function exportCSV() {
    if (!generatedListState.length) return alert("Nothing to export");
    const rows = generatedListState.map((g,i)=>({
      No: i+1,
      Course: g.course,
      Level: g.level,
      PEO: g.peo,
      PLOs: g.plos.join("; "),
      SC: g.sc.join("; "),
      VBE: g.vbe.join("; "),
      Indicators: g.indicators.join("; "),
      CLO: g.clo,
      SavedAt: g.savedAt
    }));
    const csv = arrayToCSV(rows); downloadFile(`generated_clos_${fmtDateShort()}.csv`, csv, "text/csv");
  }

  function exportJSON() {
    if (!generatedListState.length) return alert("Nothing to export");
    downloadFile(`generated_clos_${fmtDateShort()}.json`, JSON.stringify(generatedListState, null, 2), "application/json");
  }

  function clearAll() {
    if (!confirm("Clear all generated CLOs from this session?")) return;
    generatedListState = []; renderGeneratedList();
  }

  /* ---------- Events ---------- */
  peoSelect.addEventListener("change", (e) => {
    selectedPEO = e.target.value || "";
    selectedPLOs = mapping?.PEOtoPLO?.[selectedPEO] ? mapping.PEOtoPLO[selectedPEO].slice() : [];
    selectedIEGs = Object.keys(mapping?.IEGtoPEO || {}).filter(ieg => (mapping.IEGtoPEO[ieg] || []).includes(selectedPEO));
    renderSelectedPLOs(); renderIEGs(); renderAssessmentSuggestions();
  });

  bloomSelect.addEventListener("change", (e) => {});
  genBtn.addEventListener("click", () => { generateCLO(courseInput.value || "[Course Name]"); });
  saveBtn.addEventListener("click", () => { saveGenerated(courseInput.value || "[Course Name]"); });
  bulkBtn.addEventListener("click", () => {
    const rows = (bulkArea.value || "").split(/\n|,|;/).map(s=>s.trim()).filter(Boolean);
    if (!rows.length) { alert("No courses entered"); return; }
    rows.forEach(r => { generateCLO(r); saveGenerated(r); });
  });

  exportCsvBtn.addEventListener("click", exportCSV);
  exportJsonBtn.addEventListener("click", exportJSON);
  clearBtn.addEventListener("click", clearAll);

  /* ---------- Init ---------- */
  loadMapping()
    .then(()=> {
      bloomSelect.value = "Apply";
      renderAssessmentSuggestions();
    })
    .catch(err => {
      console.error("Failed to initialize CLO generator:", err);
      appWrap.appendChild(el("div", { class: "muted", html: "Could not load configuration. Check /static/data/peo_plo_ieg.json" }));
    });

})(); // end IIFE
