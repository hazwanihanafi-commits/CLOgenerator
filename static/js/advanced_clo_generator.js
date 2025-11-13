/* advanced_clo_generator.js
   Vanilla JS module to add Advanced CLO Auto-Linker into static templates.
   Dependencies: none for JSON export. For XLSX export we use SheetJS via CDN.
   Usage: include this file and the SheetJS CDN in your template, and add <div id="advanced-clo-generator"></div>
*/

(function () {
  // --------- Configuration ----------
  const JSON_PATH = "/static/data/peo_plo_ieg.json"; // edit if you put JSON elsewhere (e.g. "/data/peo_plo_ieg.json")
  const TARGET_ID = "advanced-clo-generator";

  // Bloom verbs and assessment suggestions (kept small & editable)
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

  // Utility
  function create(tag, attrs = {}, children = []) {
    const el = document.createElement(tag);
    for (const k in attrs) {
      if (k === "class") el.className = attrs[k];
      else if (k === "html") el.innerHTML = attrs[k];
      else el.setAttribute(k, attrs[k]);
    }
    (Array.isArray(children) ? children : [children]).forEach(c => {
      if (!c) return;
      el.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return el;
  }

  function downloadJSON(data, filename = "generated_clos.json") {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  }

  function exportToXLSX(data, filename = "generated_clos.xlsx") {
    // Requires SheetJS (XLSX) loaded as global 'XLSX' (we include CDN in template)
    if (typeof XLSX === "undefined") {
      alert("XLSX library not loaded. Add the SheetJS CDN before advanced_clo_generator.js to enable XLSX export.");
      return;
    }
    const flat = data.map((g, i) => ({
      No: i+1,
      Course: g.course || "",
      PEO: g.peo || "",
      PLOs: (g.plos || []).join("; "),
      IEGs: (g.iegs || []).join("; "),
      Bloom: g.bloom || "",
      Verb: g.verb || "",
      Assessment: (g.assessment || []).join("; "),
      CLO: g.clo || "",
      SavedAt: g.timestamp || ""
    }));
    const ws = XLSX.utils.json_to_sheet(flat);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Generated CLOs");
    const wbout = XLSX.write(wb, { bookType: "xlsx", type: "array" });
    try {
      const blob = new Blob([wbout], { type: "application/octet-stream" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (e) {
      console.error(e);
      alert("Export failed: " + e.message);
    }
  }

  // --------- Main UI builder ----------
  function render(container, mapping) {
    // State
    const state = {
      mapping,
      selectedPEO: "",
      selectedPLOs: [],
      selectedIEGs: [],
      bloomLevel: "Apply",
      customVerb: "",
      assessmentMethods: [],
      cloText: "",
      generatedList: [],
      bulkCourses: ""
    };

    // Container clear and base styles
    container.innerHTML = "";
    container.classList.add("acl-container");

    // Header
    container.appendChild(create("h2", { class: "acl-title", html: "Advanced CLO Auto-Linker" }));

    // Grid
    const grid = create("div", { class: "acl-grid" });
    container.appendChild(grid);

    // Left panel
    const left = create("div", { class: "acl-panel" });
    const right = create("div", { class: "acl-panel" });
    grid.appendChild(left); grid.appendChild(right);

    // PEO selector
    left.appendChild(create("label", { class: "acl-label", html: "Select PEO" }));
    const peoSel = create("select", { class: "acl-input" });
    peoSel.appendChild(create("option", { value: "" }, "— choose PEO —"));
    Object.keys(mapping).forEach(k => {
      peoSel.appendChild(create("option", { value: k }, k));
    });
    peoSel.addEventListener("change", (e) => {
      state.selectedPEO = e.target.value;
      state.selectedPLOs = state.selectedPEO ? (mapping[state.selectedPEO].PLO || []) : [];
      state.selectedIEGs = state.selectedPEO ? (mapping[state.selectedPEO].IEG || []) : [];
      updatePLOs(); updateIEGs(); updateAssessmentSuggestions();
    });
    left.appendChild(peoSel);

    // Mapped PLOs
    left.appendChild(create("div", { class: "acl-sub" }, create("div", { class: "acl-subtitle", html: "Mapped PLO(s)" })));
    const plosWrap = create("div", { class: "acl-tags" }); left.appendChild(plosWrap);

    function updatePLOs() {
      plosWrap.innerHTML = "";
      state.selectedPLOs.forEach(p => {
        const btn = create("span", { class: "acl-tag" }, p);
        plosWrap.appendChild(btn);
      });
    }

    // Mapped IEGs
    left.appendChild(create("div", { class: "acl-sub" }, create("div", { class: "acl-subtitle", html: "Mapped IEG(s)" })));
    const iegsWrap = create("div", { class: "acl-tags" }); left.appendChild(iegsWrap);

    function updateIEGs() {
      iegsWrap.innerHTML = "";
      state.selectedIEGs.forEach(i => {
        iegsWrap.appendChild(create("span", { class: "acl-tag acl-tag-green" }, i));
      });
    }

    // Bloom
    left.appendChild(create("div", { class: "acl-sub" }));
    left.appendChild(create("label", { class: "acl-label", html: "Bloom level (verb suggestion)" }));
    const bloomSel = create("select", { class: "acl-input" });
    Object.keys(BLOOM_VERBS).forEach(b => bloomSel.appendChild(create("option", { value: b }, b)));
    bloomSel.value = state.bloomLevel;
    bloomSel.addEventListener("change", (e) => { state.bloomLevel = e.target.value; updateVerbSuggestion(); });
    left.appendChild(bloomSel);

    const verbSug = create("div", { class: "acl-note" }, "Suggested verbs: " + BLOOM_VERBS[state.bloomLevel].join(", "));
    left.appendChild(verbSug);

    function updateVerbSuggestion() {
      verbSug.textContent = "Suggested verbs: " + (BLOOM_VERBS[state.bloomLevel] || []).join(", ");
    }

    left.appendChild(create("label", { class: "acl-label", html: "Override verb (optional)" }));
    const verbInput = create("input", { class: "acl-input", placeholder: "e.g., design" });
    verbInput.addEventListener("input", (e) => { state.customVerb = e.target.value; });
    left.appendChild(verbInput);

    // Assessment suggestions
    left.appendChild(create("div", { class: "acl-sub" }));
    left.appendChild(create("label", { class: "acl-label", html: "Assessment methods (suggested)" }));
    const assessWrap = create("div", { class: "acl-tags" }); left.appendChild(assessWrap);

    function updateAssessmentSuggestions() {
      assessWrap.innerHTML = "";
      const suggestions = [].concat(...state.selectedPLOs.map(p => ASSESSMENT_SUGGESTIONS[p] || []));
      const uniques = Array.from(new Set(suggestions)).slice(0, 8);
      uniques.forEach(a => {
        const btn = create("button", { class: "acl-assess-btn" }, a);
        btn.addEventListener("click", () => {
          // toggle in state.assessmentMethods
          if (state.assessmentMethods.includes(a)) state.assessmentMethods = state.assessmentMethods.filter(x => x !== a);
          else state.assessmentMethods.push(a);
          // reflect selection style
          Array.from(assessWrap.children).forEach(ch => {
            if (state.assessmentMethods.includes(ch.textContent)) ch.classList.add("active");
            else ch.classList.remove("active");
          });
        });
        assessWrap.appendChild(btn);
      });
    }

    // Right panel: course label, generate, generated CLO text, bulk
    right.appendChild(create("label", { class: "acl-label", html: "Course label (used in CLO)" }));
    const courseInput = create("input", { class: "acl-input", value: "[Course Name]" });
    right.appendChild(courseInput);

    const btnRow = create("div", { class: "acl-buttons" });
    const genBtn = create("button", { class: "acl-btn acl-btn-primary" }, "Generate CLO");
    const saveBtn = create("button", { class: "acl-btn acl-btn-success" }, "Save CLO");
    btnRow.appendChild(genBtn); btnRow.appendChild(saveBtn);
    right.appendChild(btnRow);

    function generateCLOText(label) {
      const peo = state.selectedPEO || "";
      const plos = state.selectedPLOs.join(", ");
      const iegs = state.selectedIEGs.join(", ");
      const verb = state.customVerb || (BLOOM_VERBS[state.bloomLevel] && BLOOM_VERBS[state.bloomLevel][0]) || "demonstrate";
      const text = `Upon successful completion of ${label}, the student will be able to ${verb} ${state.selectedPLOs.length>0 ? `competencies related to ${plos}` : "the expected learning outcomes"}. This aligns to ${peo} and develops graduate attributes: ${iegs}. Recommended assessment methods: ${state.assessmentMethods.join(", ")}.`;
      state.cloText = text;
      cloArea.value = text;
      return text;
    }

    genBtn.addEventListener("click", () => generateCLOText(courseInput.value));
    saveBtn.addEventListener("click", () => {
      if (!state.cloText) { alert("Generate a CLO first."); return; }
      const item = {
        course: courseInput.value,
        peo: state.selectedPEO,
        plos: [...state.selectedPLOs],
        iegs: [...state.selectedIEGs],
        bloom: state.bloomLevel,
        verb: state.customVerb || (BLOOM_VERBS[state.bloomLevel] && BLOOM_VERBS[state.bloomLevel][0]) || "",
        assessment: [...state.assessmentMethods],
        clo: state.cloText,
        timestamp: new Date().toISOString()
      };
      state.generatedList.push(item);
      refreshGeneratedList();
      // clear clo text
      state.cloText = "";
      cloArea.value = "";
    });

    right.appendChild(create("label", { class: "acl-label", html: "Generated CLO" }));
    const cloArea = create("textarea", { class: "acl-textarea", rows: 5 });
    right.appendChild(cloArea);

    // Bulk courses
    right.appendChild(create("label", { class: "acl-label", html: "Bulk courses (newline or comma separated)" }));
    const bulkArea = create("textarea", { class: "acl-textarea", rows: 3 });
    right.appendChild(bulkArea);
    const bulkBtn = create("button", { class: "acl-btn acl-btn-indigo" }, "Bulk Generate");
    right.appendChild(bulkBtn);
    bulkBtn.addEventListener("click", () => {
      const list = (bulkArea.value || "").split(/\n|,|;/).map(s => s.trim()).filter(Boolean);
      if (!list.length) { alert("Provide course names for bulk generate"); return; }
      list.forEach(lbl => {
        const text = generateCLOText(lbl);
        state.generatedList.push({
          course: lbl,
          peo: state.selectedPEO,
          plos: [...state.selectedPLOs],
          iegs: [...state.selectedIEGs],
          clo: text,
          timestamp: new Date().toISOString()
        });
      });
      refreshGeneratedList();
    });

    // Generated list area
    const genWrap = create("div", { class: "acl-generated" });
    container.appendChild(genWrap);

    function refreshGeneratedList() {
      genWrap.innerHTML = "";
      const header = create("div", { class: "acl-gen-header" }, `Generated CLOs (${state.generatedList.length})`);
      genWrap.appendChild(header);
      state.generatedList.forEach((g, idx) => {
        const row = create("div", { class: "acl-gen-row" });
        const leftc = create("div", { class: "acl-gen-left" });
        leftc.appendChild(create("div", { class: "acl-gen-title", html: `${g.course} — ${g.peo || ""}` }));
        leftc.appendChild(create("div", { class: "acl-gen-clo", html: g.clo || "" }));
        leftc.appendChild(create("div", { class: "acl-gen-meta", html: `PLOs: ${(g.plos||[]).join(", ")} • IEG: ${(g.iegs||[]).join(", ")}` }));
        row.appendChild(leftc);
        const rightc = create("div", { class: "acl-gen-actions" });
        const del = create("button", { class: "acl-btn acl-btn-danger" }, "Delete");
        del.addEventListener("click", () => {
          state.generatedList.splice(idx, 1); refreshGeneratedList();
        });
        rightc.appendChild(del);
        row.appendChild(rightc);
        genWrap.appendChild(row);
      });

      // export buttons
      const exRow = create("div", { class: "acl-export-row" });
      const exX = create("button", { class: "acl-btn acl-btn-sky" }, "Export XLSX");
      const exJ = create("button", { class: "acl-btn acl-btn-green" }, "Export JSON");
      const clearBtn = create("button", { class: "acl-btn acl-btn-gray" }, "Clear All");
      exX.addEventListener("click", () => exportToXLSX(state.generatedList));
      exJ.addEventListener("click", () => downloadJSON(state.generatedList));
      clearBtn.addEventListener("click", () => { if (confirm("Clear all generated CLOs?")) { state.generatedList = []; refreshGeneratedList(); }});
      exRow.appendChild(exX); exRow.appendChild(exJ); exRow.appendChild(clearBtn);
      genWrap.appendChild(exRow);
    }

    // initial empty generated
    refreshGeneratedList();
  }

  // --------- Fetch mapping and mount ----------
  function mount() {
    const target = document.getElementById(TARGET_ID);
    if (!target) {
      console.warn("Advanced CLO Generator: target element #" + TARGET_ID + " not found.");
      return;
    }
    fetch(JSON_PATH)
      .then(res => res.ok ? res.json() : Promise.reject(new Error("Mapping JSON not found at " + JSON_PATH)))
      .then(data => {
        render(target, data);
      })
      .catch(err => {
        console.error(err);
        target.innerHTML = "<div style='color:#900'>Failed to load PEO–PLO–IEG mapping: " + err.message + "</div>";
      });
  }

  // Run on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }

  // Append minimal CSS once
  (function injectCSS(){
    if (document.getElementById("acl-styles")) return;
    const css = `
    .acl-container{font-family:Inter,system-ui,Segoe UI,Arial;margin:12px;padding:12px;border-radius:8px;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,0.06)}
    .acl-title{font-size:18px;margin-bottom:8px}
    .acl-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .acl-panel{padding:8px}
    .acl-label{font-size:13px;font-weight:600;margin-top:6px;display:block}
    .acl-input{width:100%;padding:8px;margin-top:6px;border:1px solid #ddd;border-radius:6px}
    .acl-tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
    .acl-tag{background:#e6f0ff;padding:6px 8px;border-radius:6px;font-size:12px}
    .acl-tag-green{background:#e6ffef}
    .acl-subtitle{font-weight:600;font-size:13px}
    .acl-note{font-size:12px;color:#555;margin-top:6px}
    .acl-assess-btn{border:1px solid #ddd;padding:6px 8px;border-radius:6px;background:#f7f7f7;cursor:pointer}
    .acl-assess-btn.active{background:#ffeeba}
    .acl-btn{padding:8px 10px;border-radius:6px;border:0;cursor:pointer;margin-right:6px}
    .acl-btn-primary{background:#1f6feb;color:#fff}
    .acl-btn-success{background:#16a34a;color:#fff}
    .acl-btn-indigo{background:#4f46e5;color:#fff}
    .acl-btn-danger{background:#ef4444;color:#fff}
    .acl-textarea{width:100%;padding:8px;border-radius:6px;border:1px solid #ddd}
    .acl-generated{margin-top:18px}
    .acl-gen-row{display:flex;justify-content:space-between;padding:10px;border:1px solid #eee;border-radius:6px;margin-bottom:8px}
    .acl-gen-title{font-weight:700}
    .acl-export-row{margin-top:8px;display:flex;gap:8px}
    .acl-btn-sky{background:#0ea5e9;color:#fff;padding:8px 10px;border-radius:6px;border:0}
    .acl-btn-green{background:#10b981;color:#fff;padding:8px 10px;border-radius:6px;border:0}
    .acl-btn-gray{background:#94a3b8;color:#fff;padding:8px 10px;border-radius:6px;border:0}
    `;
    const style = document.createElement("style"); style.id="acl-styles"; style.innerHTML = css;
    document.head.appendChild(style);
  })();

})();
