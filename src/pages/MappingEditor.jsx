import React, { useState, useEffect } from "react";
import {
  IEG,
  IEGtoPEO as defaultIEGtoPEO,
  PEOtoPLO as defaultPEOtoPLO
} from "../data/usmMapping";

export default function MappingEditor() {
  const [IEGtoPEO, setIEGtoPEO] = useState({});
  const [PEOtoPLO, setPEOtoPLO] = useState({});
  const [PEOstatements, setPEOstatements] = useState({});
  const [PLOstatements, setPLOstatements] = useState({});
  const [PLOtoVBE, setPLOtoVBE] = useState({});
  const [PLOIndicators, setPLOIndicators] = useState({});

  const LEVELS = ["Diploma", "Degree", "Master", "PhD"];
  const PLO_LIST = Array.from({ length: 11 }, (_, i) => `PLO${i + 1}`);
  const VBE_OPTIONS = [
    "Ethics & Professionalism",
    "Humanity & Compassion",
    "Professionalism in Practice",
    "Civic-mindedness / Citizenship",
    "Sustainability Awareness",
    "Well-being & Resilience"
  ];

  /* --------------------------------------------
     Load mapping from localStorage OR defaults
  -------------------------------------------- */
  useEffect(() => {
    const saved = localStorage.getItem("USMMapping");
    if (saved) {
      const parsed = JSON.parse(saved);

      setIEGtoPEO(parsed.IEGtoPEO || defaultIEGtoPEO);
      setPEOtoPLO(parsed.PEOtoPLO || defaultPEOtoPLO);
      setPEOstatements(parsed.PEOstatements || {});
      setPLOstatements(parsed.PLOstatements || {});
      setPLOtoVBE(parsed.PLOtoVBE || {});
      setPLOIndicators(parsed.PLOIndicators || {});
    } else {
      setIEGtoPEO(defaultIEGtoPEO);
      setPEOtoPLO(defaultPEOtoPLO);

      setPEOstatements({
        Diploma: {},
        Degree: {},
        Master: {},
        PhD: {}
      });

      setPLOstatements({});
      setPLOtoVBE({});
      setPLOIndicators({});
    }
  }, []);

  /* --------------------------------------------
      Save to localStorage
  -------------------------------------------- */
  const saveMapping = () => {
    const data = {
      IEGtoPEO,
      PEOtoPLO,
      PEOstatements,
      PLOstatements,
      PLOtoVBE,
      PLOIndicators
    };
    localStorage.setItem("USMMapping", JSON.stringify(data));
    alert("Mapping saved successfully!");
  };

  /* --------------------------------------------
      Reset to default
  -------------------------------------------- */
  const resetDefault = () => {
    if (!window.confirm("Reset to default mappings?")) return;

    setIEGtoPEO(defaultIEGtoPEO);
    setPEOtoPLO(defaultPEOtoPLO);

    setPEOstatements({
      Diploma: {},
      Degree: {},
      Master: {},
      PhD: {}
    });

    setPLOstatements({});
    setPLOtoVBE({});
    setPLOIndicators({});
    localStorage.removeItem("USMMapping");
  };

  /* --------------------------------------------
      Toggle selection for mapping buttons
  -------------------------------------------- */
  const toggleMapping = (map, setMap, key, value) => {
    const current = map[key] || [];
    const updated = current.includes(value)
      ? current.filter(v => v !== value)
      : [...current, value];

    setMap({ ...map, [key]: updated });
  };

  return (
    <div className="p-6">
      <h1 className="text-xl font-bold mb-6">USM Mapping Editor</h1>

      {/* ======================================
           IEG → PEO
      ====================================== */}
      <h2 className="text-lg font-semibold mt-6 mb-2">IEG → PEO Mapping</h2>

      {Object.keys(IEG).map((ieg) => (
        <div key={ieg} className="mb-4 p-3 border rounded">
          <div className="font-medium mb-2">
            {ieg} — {IEG[ieg]}
          </div>

          <div className="flex flex-wrap gap-2">
            {["PEO1", "PEO2", "PEO3", "PEO4", "PEO5"].map((peo) => (
              <button
                key={peo}
                className={`px-3 py-1 rounded border ${
                  IEGtoPEO[ieg]?.includes(peo)
                    ? "bg-green-300 border-green-600"
                    : "bg-gray-100 border-gray-400"
                }`}
                onClick={() => toggleMapping(IEGtoPEO, setIEGtoPEO, ieg, peo)}
              >
                {peo}
              </button>
            ))}
          </div>
        </div>
      ))}

      {/* ======================================
           PEO → PLO Mapping
      ====================================== */}
      <h2 className="text-lg font-semibold mt-10 mb-2">
        PEO → PLO Mapping (11 PLOs)
      </h2>

      {["PEO1", "PEO2", "PEO3", "PEO4", "PEO5"].map((peo) => (
        <div key={peo} className="mb-4 p-3 border rounded">
          <div className="font-medium mb-2">{peo}</div>

          <div className="flex flex-wrap gap-2">
            {PLO_LIST.map((plo) => (
              <button
                key={plo}
                className={`px-3 py-1 rounded border ${
                  PEOtoPLO[peo]?.includes(plo)
                    ? "bg-blue-300 border-blue-600"
                    : "bg-gray-100 border-gray-400"
                }`}
                onClick={() => toggleMapping(PEOtoPLO, setPEOtoPLO, peo, plo)}
              >
                {plo}
              </button>
            ))}
          </div>
        </div>
      ))}

      {/* ======================================
           PEO STATEMENTS (Levels)
      ====================================== */}
      <h2 className="text-lg font-semibold mt-10 mb-2">
        PEO Statements (Diploma · Degree · Master · PhD)
      </h2>

      {LEVELS.map(level => (
        <div key={level} className="border p-3 rounded mb-4">
          <div className="font-medium mb-2">{level}</div>

          {["PEO1", "PEO2", "PEO3", "PEO4", "PEO5"].map(peo => (
            <div key={peo} className="mt-2">
              <label className="text-sm">{peo}</label>
              <textarea
                rows={2}
                className="w-full border p-2 rounded mt-1"
                value={PEOstatements[level]?.[peo] || ""}
                onChange={(e) =>
                  setPEOstatements(prev => ({
                    ...prev,
                    [level]: { ...prev[level], [peo]: e.target.value }
                  }))
                }
              />
            </div>
          ))}
        </div>
      ))}

      {/* ======================================
           PLO STATEMENTS
      ====================================== */}
      <h2 className="text-lg font-semibold mt-10 mb-2">PLO Statements</h2>

      {PLO_LIST.map(plo => (
        <div key={plo} className="border p-3 rounded mb-3">
          <label className="font-medium">{plo}</label>
          <textarea
            rows={2}
            className="w-full border rounded p-2 mt-1"
            value={PLOstatements[plo] || ""}
            onChange={(e) =>
              setPLOstatements(prev => ({ ...prev, [plo]: e.target.value }))
            }
          />
        </div>
      ))}

      {/* ======================================
           PLO → VBE
      ====================================== */}
      <h2 className="text-lg font-semibold mt-10 mb-2">
        PLO → VBE Mapping
      </h2>

      {PLO_LIST.map(plo => (
        <div key={plo} className="border p-3 rounded mb-3">
          <div className="font-medium">{plo}</div>

          <select
            className="w-full border rounded p-2 mt-2"
            value={PLOtoVBE[plo] || ""}
            onChange={(e) =>
              setPLOtoVBE(prev => ({ ...prev, [plo]: e.target.value }))
            }
          >
            <option value="">-- select VBE --</option>
            {VBE_OPTIONS.map(v => (
              <option key={v} value={v}>{v}</option>
            ))}
          </select>
        </div>
      ))}

      {/* ======================================
           PLO → Indicator
      ====================================== */}
      <h2 className="text-lg font-semibold mt-10 mb-2">
        PLO → Indicator (Measurement)
      </h2>

      {PLO_LIST.map(plo => (
        <div key={plo} className="border p-3 rounded mb-3">
          <label className="font-medium">{plo}</label>
          <input
            className="w-full border p-2 rounded mt-2"
            placeholder="% pass exam, ≥70% rubric, ≥3/5 practical"
            value={PLOIndicators[plo] || ""}
            onChange={(e) =>
              setPLOIndicators(prev => ({
                ...prev,
                [plo]: e.target.value
              }))
            }
          />
        </div>
      ))}

      /* ============================
   PLO → SC (Sub-Competency)
============================ */
<h2 className="text-lg font-semibold mt-10 mb-2">
  PLO → SC (Sub-Competency)
</h2>

{PLO_LIST.map(plo => (
  <div key={plo} className="border p-3 rounded mb-3">
    <label className="font-medium">{plo} — SC</label>
    <input
      className="w-full border p-2 rounded mt-2"
      placeholder="e.g., SC4, SC6, SC7"
      value={SCmapping[plo] || ""}
      onChange={(e) =>
        setSCmapping(prev => ({ ...prev, [plo]: e.target.value }))
      }
    />
  </div>
))}


      {/* ======================================
           SAVE / RESET BUTTONS
      ====================================== */}
      <div className="flex gap-3 mt-10">
        <button
          onClick={saveMapping}
          className="px-4 py-2 bg-green-600 text-white rounded"
        >
          Save Mapping
        </button>

        <button
          onClick={resetDefault}
          className="px-4 py-2 bg-red-600 text-white rounded"
        >
          Reset Default
        </button>
      </div>
    </div>
  );
}
