import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../utils/format";

/**
 * Loads data from an API call and exposes { data, loading, error, reload }.
 * Existing data is kept while a reload is in flight.
 */
export default function useApi(fetcher, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const mounted = useRef(true);

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fetcherRef.current();
      if (mounted.current) setState({ data, loading: false, error: null });
    } catch (err) {
      if (mounted.current) setState((s) => ({ ...s, loading: false, error: errorMessage(err) }));
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    load();
    return () => {
      mounted.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load, ...deps]);

  return { ...state, reload: load };
}
