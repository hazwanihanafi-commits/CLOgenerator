import React, { useEffect, useState, useMemo } from "react";
import usePEOPLOIEG from "../hooks/usePEOPLOIEG";
import { saveAs } from "file-saver";
import * as XLSX from "xlsx";

/**
 * AdvancedCLOAutoLinker.jsx
 * - Keeps PEO-first UI & flow
 * - Supports PLOtoVBE as simple strings (Option 1)
 * - Includes SC support (will be empty for Option 1 data)
 * - Exports XLSX/JSON including SC column (empty for Option 1)
 */

const BLOOM_VERBS = {
  Remember: ["list", "name", "recall", "define"],
  Understand: ["explain", "describe", "summarize", "interpret"],
  Apply: ["apply", "demonstrate", "use", "execute"],
  Analyze: ["analyze", "compare", "differentiate", "organize"],
  Evaluate: ["evaluate", "judge", "critique", "assess"],
  Create: ["design", "construct", "compose", "formulate"]
};

const ASSESSMENT_SUGGESTIONS = {
  PLO1: ["Written exam", "Quiz"],
  PLO2: ["Critical review"],
  PLO3: ["Practical test", "OSCE"],
  PLO4: ["Group project", "Peer assessment"],
  PLO5: ["Presentation", "Oral exam"],
  PLO6: ["Digital portfolio"],
  PLO7: ["Calculation test"],
  PLO8: ["Team-based assignment"],
  PLO9: ["Business plan", "Pitch"],
  PLO10: ["Professional ethics assessment"],
  PLO11: ["Leadership project"]
};

function dedupe(arr) { return Array.from(new Set(arr)); }

// Helper: get VBE when mapping is simple string or object (handles both shapes)
const getVBEfromMapping = (mapping, plo) => {
  if (!mapping) return "";
  const v = mapping.PLOtoVBE?.[plo];
  if (!v) return "";
  return typeof v === "string" ? v : (v.VBE || "");
};

// Helper: get SC when mapping may include SC (Option 2/3). For Option1 returns ""
const getSCfromMapping = (mapping, plo) => {
  if (!mapping) return "";
  const v = mapping.PLOtoVBE?.[plo];
  if (!v) return "";
  return typeof v === "string" ? "" : (v.SC || "");
};

export default function AdvancedCLOAutoLinker({ courseName = "[Course Name]" }) {
  const mapping = usePEOPLOIEG();

  // original states kept
  const [selectedPEO, setSelectedPEO] = useState("");
  const [selectedPLOs, setSelectedPLOs] = useState([]);
  const [selectedIEGs, setSelectedIEGs] = useState([]);
  const [bloomLevel, setBloomLevel] = useState("Apply");
  const [customVerb, setCustomVerb] = useState("");
  const [cloText, setCloText] = useState("");
  const [assessmentMethods, setAssessmentMethods] = useState([]);
  const [generatedList, setGeneratedList] = useState([]);
  const [bulkCourses, setBulkCourses] = useState("");

  // When mapping or selectedPEO changes -> auto-fill PLO & IEG
  useEffect(() => {
    if (!mapping || !selectedPEO) {
      setSelectedPLOs([]);
      setSelectedIEGs([]);
      return;
    }
    const plos = mapping.PEOtoPLO?.[selectedPEO] || [];
    setSelectedPLOs(plos);

    // derive IEGs from PLOs via reverse or mapping stored earlier:
    // your original shape may have PEO->IEG or PLO->IEG. Try mapping[selectedPEO].IEG first
    if (mapping[selectedPEO]?.IEG) {
      setSelectedIEGs(mapping[selectedPEO].IEG);
    } else if (mapping.PLOtoIEG) {
      // if mapping.PLOtoIEG exists (PLO->IEG), aggregate
      const iegs = dedupe(plos.flatMap(p => mapping.PLOtoIEG?.[p] || []));
      setSelectedIEGs(iegs);
    } else if (mapping.IEGtoPEO) {
      // fallback: find IEGs where PEO appears (IEG->PEO reverse)
      const iegs = Object.keys(mapping.IEGtoPEO || {}).filter(ieg =>
        (mapping.IEGtoPEO[ieg] || []).includes(selectedPEO)
      );
      setSelectedIEGs(iegs);
    } else {
      setSelectedIEGs([]);
    }
  }, [mapping, selectedPEO]);

  // Auto-suggest assessment methods based on selectedPLOs
  useEffect(() => {
    const suggestions = selectedPLOs.flatMap(p => ASSESSMENT_SUGGESTIONS[p] || []);
    setAssessmentMethods(dedupe(suggestions).slice(0, 5));
  }, [selectedPLOs]);

  const bloomVerbs = useMemo(() => BLOOM_VERBS[bloomLevel] || [], [bloomLevel]);

  function generateCLO(courseLabel = courseName) {
    if (!selectedPEO && selectedPLOs.length === 0) return "";

    const PLOs = selectedPLOs.map(p => {
      // include SC if present in mapping (Option1: blank)
      const sc = getSCfromMapping(mapping, p);
      return sc ? `${p} (SC: ${sc})` : p;
    }).join(", ");

    const IEGs = selectedIEGs.join(", ");
    const verb = customVerb || bloomVerbs[0] || "demonstrate";

    // optional inclusion of PLO statements if present
    const ploStatements = selectedPLOs.map(p => mapping?.PLOstatements?.[p]).filter(Boolean);
    const ploStatementText = ploStatements.length ? ` PLO statements: ${ploStatements.join("; ")}.` : "";

    const assessmentText = assessmentMethods.length ? ` Recommended assessment methods: ${assessmentMethods.join(", ")}.` : "";

    const text = `Upon successful completion of ${courseLabel}, the student will be able to ${verb} competencies related to ${PLOs}.${ploStatementText} This aligns to ${selectedPEO || "the programme PEO(s)"} and develops graduate attributes: ${IEGs || "N/A"}.${assessmentText}`;

    setCloText(text);
    return text;
  }

  function saveGenerated() {
    if (!cloText) return;
    setGeneratedList(prev => [...prev, {
      course: courseName,
      peo: selectedPEO,
      plos: [...selectedPLOs],
      iegs: [...selectedIEGs],
      bloom: bloomLevel,
      verb: customVerb || bloomVerbs[0],
      assessment: [...assessmentMethods],
      clo: cloText,
      timestamp: new Date().toISOString()
    }]);
    setCloText("");
  }

  function bulkGenerate() {
    const rows = bulkCourses.split(/\n|,|;/).map(s => s.trim()).filter(Boolean);
    const items = rows.map(r => {
      const label = r;
      const text = generateCLO(label);
      return { course: label, peo: selectedPEO, plos: selectedPLOs, iegs: selectedIEGs, clo: text, timestamp: new Date().toISOString() };
    });
    setGeneratedList(prev => [...prev, ...items]);
  }

  function exportXLSX() {
    const ws = XLSX.utils.json_to_sheet(generatedList.map((g, i) => ({
      No: i+1,
      Course: g.course,
      PEO: g.peo,
      PLOs: g.plos.map(p => {
        const sc = getSCfromMapping(mapping, p);
        return sc ? `${p} (SC: ${sc})` : p;
      }).join("; "),
      IEGs: g.iegs.join("; "),
      Bloom: g.bloom || "",
      Verb: g.verb || "",
      Assessment: g.assessment ? g.assessment.join("; ") : "",
      CLO: g.clo || "",
      SavedAt: g.timestamp || ""
    })));
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Generated CLOs");
    const xlsxData = XLSX.write(wb, { bookType: "xlsx", type: "array" });
    saveAs(new Blob([xlsxData], { type: "application/octet-stream" }), `generated_clos_${new Date().toISOString().slice(0,10)}.xlsx`);
  }

  function exportJSON() {
    const blob = new Blob([JSON.stringify(generatedList, null, 2)], { type: "application/json" });
    saveAs(blob, `generated_clos_${new Date().toISOString().slice(0,10)}.json`);
  }

  function clearAll() { setGeneratedList([]); }

  /* ---------- UI ---------- */
  return (
    <div className="p-4 bg-white rounded-lg shadow">
      <h2 className="text-xl font-semibold mb-3">Advanced CLO Auto-Linker</h2>

      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium">Select PEO</label>
          <select className="w-full border rounded px-3 py-2 mt-1" value={selectedPEO} onChange={(e)=>setSelectedPEO(e.target.value)}>
            <option value="">-- choose PEO --</option>
            {mapping && Object.keys(mapping.PEOtoPLO || {}).map(peo => <option key={peo} value={peo}>{peo}</option>)}
          </select>

          <div className="mt-3 text-sm">
            <div className="font-medium">Mapped PLO(s) { /* SC shown if present */}</div>
            <div className="flex flex-wrap gap-2 mt-2">
              {selectedPLOs.map(p => {
                const sc = getSCfromMapping(mapping, p);
                return (
                  <div key={p} className="px-2 py-1 bg-blue-100 rounded">
                    <div className="font-semibold text-sm">{p}</div>
                    {sc ? <div className="text-xs">SC: {sc}</div> : null}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="mt-3 text-sm">
            <div className="font-medium">Mapped IEG(s)</div>
            <div className="flex flex-wrap gap-2 mt-2">
              {selectedIEGs.map(i => <span key={i} className="px-2 py-1 bg-green-100 rounded">{i}</span>)}
            </div>
          </div>

          <div className="mt-4">
            <label className="block text-sm font-medium">Bloom level (verb suggestion)</label>
            <select className="w-full border rounded px-3 py-2 mt-1" value={bloomLevel} onChange={(e)=>setBloomLevel(e.target.value)}>
              {Object.keys(BLOOM_VERBS).map(b => <option key={b} value={b}>{b}</option>)}
            </select>
            <div className="mt-2 text-sm">Suggested verbs: {bloomVerbs.join(", ")}</div>

            <label className="block text-sm font-medium mt-3">Override verb (optional)</label>
            <input className="w-full border rounded px-3 py-2 mt-1" placeholder="e.g., design" value={customVerb} onChange={(e)=>setCustomVerb(e.target.value)} />
          </div>

          <div className="mt-4">
            <label className="block text-sm font-medium">Assessment methods (suggested)</label>
            <div className="flex flex-wrap gap-2 mt-2">
              {assessmentMethods.map(a => <button key={a} onClick={()=> setAssessmentMethods(prev => prev.includes(a)? prev.filter(x=>x!==a) : [...prev, a])} className={`px-2 py-1 rounded ${assessmentMethods.includes(a)? 'bg-yellow-200' : 'bg-gray-100'}`}>{a}</button>)}
            </div>
          </div>

        </div>

        <div>
          <label className="block text-sm font-medium">Course label (used in CLO)</label>
          <input className="w-full border rounded px-3 py-2" value={courseName} onChange={(e)=>{/* readOnly or leave as prop */}} readOnly />

          <div className="mt-3">
            <button onClick={()=> setCloText(generateCLO(courseName))} className="px-4 py-2 bg-blue-600 text-white rounded mr-2">Generate CLO</button>
            <button onClick={saveGenerated} className="px-4 py-2 bg-green-600 text-white rounded">Save CLO</button>
          </div>

          <div className="mt-4">
            <label className="block text-sm font-medium">Generated CLO</label>
            <textarea className="w-full border rounded p-2" rows={6} value={cloText} onChange={(e)=>setCloText(e.target.value)} />
          </div>

          <div className="mt-4">
            <label className="block text-sm font-medium">Bulk courses (newline or comma separated)</label>
            <textarea className="w-full border rounded p-2" rows={4} value={bulkCourses} onChange={(e)=>setBulkCourses(e.target.value)} />
            <div className="mt-2">
              <button onClick={bulkGenerate} className="px-3 py-2 bg-indigo-600 text-white rounded mr-2">Bulk Generate</button>
            </div>
          </div>

        </div>
      </div>

      <div className="mt-6">
        <h3 className="font-semibold">Generated CLOs ({generatedList.length})</h3>
        <div className="mt-3 space-y-2">
          {generatedList.map((g, i) => (
            <div key={i} className="p-3 border rounded flex justify-between items-start">
              <div>
                <div className="font-medium">{g.course} — {g.peo}</div>
                <div className="text-sm text-gray-600 mt-1">{g.clo}</div>
                <div className="text-xs text-gray-500 mt-2">PLOs: {g.plos?.join(', ')} • IEG: {g.iegs?.join(', ')}</div>
              </div>
              <div className="text-right">
                <button onClick={()=> {
                  const copy = [...generatedList]; copy.splice(i,1); setGeneratedList(copy);
                }} className="px-2 py-1 bg-red-500 text-white rounded">Delete</button>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 flex gap-2">
          <button onClick={exportXLSX} className="px-4 py-2 bg-sky-600 text-white rounded">Export XLSX</button>
          <button onClick={exportJSON} className="px-4 py-2 bg-emerald-600 text-white rounded">Export JSON</button>
          <button onClick={clearAll} className="px-4 py-2 bg-gray-400 text-white rounded">Clear All</button>
        </div>

        <div className="mt-4 text-sm text-gray-500">
          Note: To enable PDF export, install <code>html2canvas</code> and <code>jspdf</code>. Use a wrapper ref around the generated list and capture it.
        </div>
      </div>

    </div>
  );
}
