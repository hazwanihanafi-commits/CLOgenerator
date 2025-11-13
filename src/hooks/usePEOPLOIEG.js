import { useState, useEffect } from "react";

export default function usePEOPLOIEG() {
  const [mapping, setMapping] = useState(null);

  useEffect(() => {
    async function loadMapping() {
      try {
        const res = await fetch("/data/peo_plo_ieg.json");

        if (!res.ok) {
          console.error("Failed to load /data/peo_plo_ieg.json");
          return;
        }

        const json = await res.json();

        // Ensure the mapping has all needed keys
        const cleanMapping = {
          IEGtoPEO: json.IEGtoPEO || {},
          PEOtoPLO: json.PEOtoPLO || {},
          IEGdefinitions: json.IEGdefinitions || {},
          PLOdefinitions: json.PLOdefinitions || {}
        };

        setMapping(cleanMapping);

      } catch (err) {
        console.error("Error loading mapping JSON:", err);
      }
    }

    loadMapping();
  }, []);

  return mapping;
}
