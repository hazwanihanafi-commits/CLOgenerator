import { useEffect, useState } from "react";

export default function usePEOPLOIEG() {
  const [mapping, setMapping] = useState(null);

  useEffect(() => {
    fetch("/data/peo_plo_ieg.json")
      .then((res) => res.json())
      .then((data) => setMapping(data));
  }, []);

  return mapping;
}
