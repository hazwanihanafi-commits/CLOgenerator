import React, { useState, useEffect } from "react";
import { IEG, IEGtoPEO as defaultIEGtoPEO, PEOtoPLO as defaultPEOtoPLO } from "../data/usmMapping";

export default function MappingEditor() {
  const [IEGtoPEO, setIEGtoPEO] = useState({});
  const [PEOtoPLO, setPEOtoPLO] = useState({});

  /* --------------------------------------------
     Load mapping from localStorage OR defaults
  -------------------------------------------- */
  useEffect(() => {
    const saved = localStorage.getItem("USMMapping");
    if (saved) {
      const parsed = JSON.parse(saved);
      setIEGtoPEO(parsed.IEGtoPEO);
      setPEOtoPLO(parsed.PEOtoPLO);
    } else {
      setIEGtoPEO(defaultIEGtoPEO);
      setPEOtoPLO(defaultPEOtoPLO);
    }
  }, []);

  /* --------------------------------------------
      Save to localStorage
  -------------------------------------------- */
  const saveMapping = () => {
    const data = {
      IEGtoPEO,
      PEOtoPLO
    };
    localStorage.setItem("USMMapping", JSON.stringify(data));
    alert("Mapping saved successfully!");
  };

  /* --------------------------------------------
      Reset to default
  -------------------------------------------- */
  const resetDefault = () => {
    setIEGtoPEO(defaultIEGtoPEO);
    setPEOtoPLO(defaultPEOtoPLO);
    localStorage.removeItem("USMMapping");
  };

  /* --------------------------------------------
      Toggle selection for Mapping Buttons
  -------------------------------------------- */
  const toggleMapping = (map, setMap, key, value) => {
    const current = map[key] || [];
    const updated = current.includes(value)
      ? current.filter(v => v !== value)
      : [...current, value];
    setMap({ ...map, [key]: updated });
  };

  /* --------------------------------------------
      PLO List (MQF 11 Domains)
  -------------------------------------------- */
  const PLO_LIST = Array.from({ length: 11 }, (_, i) => `PLO${i + 1}`);

  return (
    <div className="p-6">
      <h1 className="text-xl font-bold mb-4">USM Mapping Editor</h1>

      {/* ----------------- IEG → PEO ----------------- */}
      <h2 className="text-lg font-semibold mt-6 mb-2">IEG → PEO Mapping</h2>

      {Object.keys(IEG).map((ieg) => (
        <div key={ieg} className="mb-4 p-3 border rounded">
          <div className="font-medium mb-2">{ieg} — {IEG[ieg]}</div>

          <div className="flex flex-wrap gap-2">
            {["PEO1", "PEO2", "PEO3", "PEO4", "PEO5"].map((peo) => (
              <button
                key={peo}
                className={`px-3 py-1 rounded border ${
                  IEGtoPEO[ieg]?.includes(peo)
                    ? "bg-green-300 border-green-600"
                    : "bg-gray-100 border-gray-400"
                }`}
                onClick={() =>
                  toggleMapping(IEGtoPEO, setIEGtoPEO, ieg, peo)
                }
              >
                {peo}
              </button>
            ))}
          </div>
        </div>
      ))}

      {/* ----------------- PEO → PLO ----------------- */}
      <h2 className="text-lg font-semibold mt-8 mb-2">PEO → PLO Mapping (11 PLOs)</h2>

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
                onClick={() =>
                  toggleMapping(PEOtoPLO, setPEOtoPLO, peo, plo)
                }
              >
                {plo}
              </button>
            ))}
          </div>
        </div>
      ))}

      {/* ----------------- Save / Reset ----------------- */}
      <div className="flex gap-3 mt-8">
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
