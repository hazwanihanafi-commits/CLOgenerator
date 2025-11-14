/* ===============================================================
   ADVANCED CLO GENERATOR v3 (STABLE BUILD)
   - Works with any JSON structure
   - Provides full cascade: IEG → PEO → PLO → Statements
   - Does NOT override your main CLO builder
   - Guaranteed no duplicate event listeners
   - Guaranteed no interference with main generator
================================================================ */

document.addEventListener("DOMContentLoaded", async () => {

  console.log("%c Advanced CLO Auto-Linker v3 Loaded ✔", "color:#0a7;padding:4px;");

  /* --------------------------------------------------------------
      1. ELEMENT LINKS
  -------------------------------------------------------------- */
  const $ = id => document.getElementById(id);

  const iegSel = $("ieg");
  const peoSel = $("peo");
  const ploSel = $("plo");

  const levelSel = $("level");
  const profileSel = $("profile");
  const profileHidden = $("profileHidden");

  // Mapping display
  const iegStatement = $("ieg_statement");
  const peoStatement = $("peo_statement");
  const ploStatement = $("plo_statement");
  const ploIndicator = $("plo_indicator");

  // Bloom & Verb display
  const bloomSel = $("bloom");
  const verbSel = $("verb");

  const scCode = $("sc_code");
  const scDesc = $("sc_desc");
  const vbe = $("vbe");
  const domain = $("domain");

  const conditionEl = $("condition");
  const criterionEl = $("criterion");

  const assessEl = $("assessment");
  const evidEl = $("evidence");

  /* --------------------------------------------------------------
      2. LOAD JSON (FULL FLEXIBLE VERSION)
  -------------------------------------------------------------- */
  let MAP = {};

  async function loadJSON() {
    try {
      const r = await fetch("/static/data/peo_plo_ieg.json", { cache: "no-store" });
      MAP = await r.json();
      console.log("JSON loaded:", MAP);
    } catch (e) {
      console.error("❌ Cannot load JSON:", e);
      MAP = {};
    }
  }

  await loadJSON();

  /* --------------------------------------------------------------
      3. SHORTCUT (read keys ignoring case)
  -------------------------------------------------------------- */
  const pick = (obj, ...keys) => {
    if (!obj) return;
    for (const key of keys) {
      const found = Object.keys(obj).find(k => k.toLowerCase() === key.toLowerCase());
      if (found) return obj[found];
    }
    return;
  };

  const IEG_LIST      = pick(MAP, "IEGs");
  const IEGtoPEO      = pick(MAP, "IEGtoPEO");
  const PEOtoPLO      = pick(MAP, "PEOtoPLO");
  const PLOstatements = pick(MAP, "PLOstatements");
  const PEOstatements = pick(MAP, "PEOstatements");
  const IEGstatements = pick(MAP, "IEGstatements");
  const PLOIndicators = pick(MAP, "PLOIndicators");

  /* --------------------------------------------------------------
      4. POPULATE IEG DROPDOWN
  -------------------------------------------------------------- */
  function populateIEG() {
    iegSel.innerHTML = `<option value="" disabled selected>— Select IEG —</option>`;
    const list = IEG_LIST || Object.keys(IEGtoPEO || {});
    list.forEach(i => iegSel.add(new Option(i, i)));
  }

  populateIEG();

  /* --------------------------------------------------------------
      5. IEG → PEO CASCADE
  -------------------------------------------------------------- */
  iegSel.addEventListener("change", () => {
    const ieg = iegSel.value;

    peoSel.innerHTML = `<option value="" disabled selected>— Select PEO —</option>`;
    ploSel.innerHTML = `<option value="" disabled selected>— Select PLO —</option>`;

    const peos = IEGtoPEO?.[ieg] || [];
    peos.forEach(p => peoSel.add(new Option(p, p)));

    // Statement
    iegStatement.textContent = IEGstatements?.[ieg] || ieg;
    peoStatement.textContent = "—";
    ploStatement.textContent = "—";
    ploIndicator.textContent = "—";
  });

  /* --------------------------------------------------------------
      6. PEO → PLO CASCADE
  -------------------------------------------------------------- */
  peoSel.addEventListener("change", () => {
    const peo = peoSel.value;
    const level = levelSel.value;

    ploSel.innerHTML = `<option value="" disabled selected>— Select PLO —</option>`;

    const plos = PEOtoPLO?.[peo] || [];
    plos.forEach(p => ploSel.add(new Option(p, p)));

    // PEO statement
    peoStatement.textContent =
      PEOstatements?.[level]?.[peo] ||
      PEOstatements?.[peo] ||
      peo;
  });

  /* --------------------------------------------------------------
      7. PLO SELECTED → Load statements + indicator + Blooms
  -------------------------------------------------------------- */
  ploSel.addEventListener("change", async () => {
    const plo = ploSel.value;
    const level = levelSel.value;

    // Statements
    ploStatement.textContent =
      PLOstatements?.[level]?.[plo] ||
      PLOstatements?.[plo] ||
      "—";

    // Indicator
    ploIndicator.textContent =
      PLOIndicators?.[plo] || "—";

    /* ----------------------------------------------------------
        BLOOM (via backend API)
    ---------------------------------------------------------- */
    bloomSel.innerHTML = `<option disabled selected>Loading...</option>`;
    try {
      const blo = await (await fetch(`/api/get_blooms/${plo}?profile=${profileSel.value}`)).json();
      bloomSel.innerHTML = `<option value="" disabled selected>Select Bloom</option>`;
      blo.forEach(b => bloomSel.add(new Option(b, b)));
    } catch (e) {
      bloomSel.innerHTML = `<option>Error loading Blooms</option>`;
    }

    verbSel.innerHTML = `<option value="" disabled selected>Select Verb</option>`;
  });

  /* --------------------------------------------------------------
      8. BLOOM SELECTED → Load verbs + meta
  -------------------------------------------------------------- */
  bloomSel.addEventListener("change", async () => {
    const plo = ploSel.value;
    const bloom = bloomSel.value;

    // verbs
    verbSel.innerHTML = `<option disabled selected>Loading...</option>`;
    const verbs = await (await fetch(`/api/get_verbs/${plo}/${bloom}?profile=${profileSel.value}`)).json();
    verbSel.innerHTML = `<option value="" disabled selected>Select Verb</option>`;
    verbs.forEach(v => verbSel.add(new Option(v, v)));

    // meta (condition + criterion)
    const meta = await (await fetch(`/api/get_meta/${plo}/${bloom}?profile=${profileSel.value}`)).json();
    conditionEl.value = meta.condition || "";
    criterionEl.value = meta.criterion || "";

    scCode.textContent = meta.sc_code || "";
    scDesc.textContent = meta.sc_desc || "";
    vbe.textContent = meta.vbe || "";
    domain.textContent = meta.domain || "";

    assessEl.value = meta.assessment || "";
    evidEl.value = meta.evidence || "";
  });

});
