import React, { useEffect, useState, useMemo } from "react";
import usePEOPLOIEG from "../hooks/usePEOPLOIEG";
import { saveAs } from "file-saver";
import * as XLSX from "xlsx";

/*
Advanced CLO Auto-Linker Module
Features:
- PEO selector -> auto-fill PLO & IEG
- Suggest Bloom verbs by cognitive level
- Auto-suggest assessment methods mapped to PLO types
- Bulk-generate CLOs for multiple courses
- Export generated CLOs to XLSX / CSV / JSON
- Generate printable PDF (via html2canvas + jsPDF) - integration notes included

Dependencies:
- file-saver
- xlsx
- html2canvas (optional, for PDF)
- jspdf (optional, for PDF)

Install:
npm install file-saver xlsx html2canvas jspdf

Usage:
- Place this file in /src/components/AdvancedCLOGenerator.js
- Ensure usePEOPLOIEG hook loads /public/data/peo_plo_ieg.json
- Import and render <AdvancedCLOGenerator courseName={...} /> inside your app
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
  PLO1: ["Written exam", "Open-book exam", "Quiz"],
  PLO2: ["Critical review assignment", "Journal critique"],
  PLO3: ["Practical test", "Lab report", "OSCE"],
  PLO4: ["Peer-assessment", "Group project"],
  PLO5: ["Presentation", "Oral exam", "Poster"],
  PLO6: ["Digital portfolio", "Data analysis assignment"],
  PLO7: ["Problem set", "Calculation test"],
  PLO8: ["Leadership project", "Team-based assignment"],
  PLO9: ["Reflective journal", "Learning log"],
  PLO10: ["Business plan", "Entrepreneurship pitch"],
  PLO11: ["Professional conduct assessment", "Case study"],
};

function dedupe(arr) { return Array.from(new Set(arr)); }

export default function AdvancedCLOGenerator({ courseName = "[Course Name]" }) {
  const mapping = usePEOPLOIEG();
  const [selectedPEO, setSelectedPEO] = useState("");
  const [selectedPLOs, setSelectedPLOs] = useState([]);
  const [selectedIEGs, setSelectedIEGs] = useState([]);
  const [bloomLevel, setBloomLevel] = useState("Apply");
  const [customVerb, setCustomVerb] = useState("");
  const [cloText, setCloText] = useState("");
  const [assessmentMethods, setAssessmentMethods] = useState([]);
  const [generatedList, setGeneratedList] = useState([]);
  const [bulkCourses, setBulkCourses] = useState(""); // newline-separated course codes

  useEffect(() => {
    if (!mapping || !selectedPEO) return;
    setSelectedPLOs(mapping[selectedPEO].PLO || []);
    setSelectedIEGs(mapping[selectedPEO].IEG || []);
  }, [mapping, selectedPEO]);

  useEffect(() => {
    // auto-suggest assessment methods based on selectedPLOs
    const suggestions = selectedPLOs.flatMap(p => ASSESSMENT_SUGGESTIONS[p] || []);
    setAssessmentMethods(dedupe(suggestions).slice(0,5));
  }, [selectedPLOs]);

  const bloomVerbs = useMemo(() => BLOOM_VERBS[bloomLevel] || [], [bloomLevel]);

  function generateCLO(courseLabel = courseName) {
    if (!selectedPEO) return "";
    const PLOs = selectedPLOs.join(", ");
    const IEGs = selectedIEGs.join(", ");
    const verb = customVerb || bloomVerbs[0] || "demonstrate";

    const text = `Upon successful completion of ${courseLabel}, the student will be able to ${verb} ${selectedPLOs.length>0 ? `competencies related to ${PLOs}` : "the expected learning outcomes"}. This aligns to ${selectedPEO} and develops graduate attributes: ${IEGs}. Recommended assessment methods: ${assessmentMethods.join(", ")}.`;
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
    // clear cloText to avoid duplicate saves
    setCloText("");
  }

  function bulkGenerate() {
    const rows = bulkCourses.split(/\n|,|;/).map(s => s.trim()).filter(Boolean);
    const items = rows.map(r => {
      const label = r;
      const text = generateCLO(label);
      return { course: label, peo: selectedPEO, plos: selectedPLOs, iegs: selectedIEGs, clo: text };
    });
    setGeneratedList(prev => [...prev, ...items]);
  }

  function exportXLSX() {
    const ws = XLSX.utils.json_to_sheet(generatedList.map((g, i) => ({
      No: i+1,
      Course: g.course,
      PEO: g.peo,
      PLOs: g.plos.join("; "),
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

  return (
    <div className="p-4 bg-white rounded-lg shadow">
      <h2 className="text-xl font-semibold mb-3">Advanced CLO Auto-Linker</h2>

      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium">Select PEO</label>
          <select className="w-full border rounded px-3 py-2 mt-1" value={selectedPEO} onChange={(e)=>setSelectedPEO(e.target.value)}>
            <option value="">-- choose PEO --</option>
            {mapping && Object.keys(mapping).map(peo => <option key={peo} value={peo}>{peo}</option>)}
          </select>

          <div className="mt-3 text-sm">
            <div className="font-medium">Mapped PLO(s)</div>
            <div className="flex flex-wrap gap-2 mt-2">
              {selectedPLOs.map(p => <span key={p} className="px-2 py-1 bg-blue-100 rounded">{p}</span>)}
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
          <input className="w-full border rounded px-3 py-2" value={courseName} onChange={(e)=>{/* if you'd like to edit per instance, connect prop or state */}} readOnly />

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
