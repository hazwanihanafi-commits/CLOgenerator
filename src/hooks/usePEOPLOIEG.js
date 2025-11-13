import { useState, useEffect } from "react";
import { IEGtoPEO as defaultIEG, PEOtoPLO as defaultPEO } from "../data/usmMapping";

export default function usePEOPLOIEG() {
  const [mapping, setMapping] = useState(null);

  useEffect(() => {

    const saved = localStorage.getItem("USMMapping");

    if (saved) {
      // Load customized mapping
      const parsed = JSON.parse(saved);
      setMapping(parsed);
    } else {
      // Load default mapping
      setMapping({
        IEGtoPEO: defaultIEG,
        PEOtoPLO: defaultPEO
      });
    }

  }, []);

  return mapping;
}
