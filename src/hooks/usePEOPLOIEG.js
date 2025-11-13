import { useState, useEffect } from "react";
import {
  IEGtoPEO as defaultIEGtoPEO,
  PEOtoPLO as defaultPEOtoPLO,
  IEG,
} from "../data/usmMapping";

export default function usePEOPLOIEG() {
  const [mapping, setMapping] = useState(null);

  useEffect(() => {
    const saved = localStorage.getItem("USMMapping");

    if (saved) {
      // LOAD FROM LOCALSTORAGE (custom mapping)
      const parsed = JSON.parse(saved);

      setMapping({
        IEG,
        IEGtoPEO: parsed.IEGtoPEO || defaultIEGtoPEO,
        PEOtoPLO: parsed.PEOtoPLO || defaultPEOtoPLO,
        PEOstatements: parsed.PEOstatements || {
          Diploma: {},
          Degree: {},
          Master: {},
          PhD: {},
        },
        PLOstatements: parsed.PLOstatements || {},
        PLOtoVBE: parsed.PLOtoVBE || {},
        PLOIndicators: parsed.PLOIndicators || {},
      });

    } else {
      // LOAD FROM DEFAULT FILE + EMPTY EXTRAS
      setMapping({
        IEG,
        IEGtoPEO: defaultIEGtoPEO,
        PEOtoPLO: defaultPEOtoPLO,
        PEOstatements: {
          Diploma: {},
          Degree: {},
          Master: {},
          PhD: {},
        },
        PLOstatements: {},
        PLOtoVBE: {},
        PLOIndicators: {},
      });
    }
  }, []);

  return mapping;
}
