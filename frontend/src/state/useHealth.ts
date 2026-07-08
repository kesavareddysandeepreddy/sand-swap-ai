import { useCallback, useEffect, useState } from "react";

import { apiClient, ApiError } from "../api/client";
import type { HealthResponse } from "../types/api";

const POLL_INTERVAL_MS = 15000;

export const useHealth = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadHealth = useCallback(async () => {
    try {
      const next = await apiClient.getHealth();
      setHealth(next);
      setError(null);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Failed to load API health.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const initialFetch = window.setTimeout(() => {
      void loadHealth();
    }, 0);

    const interval = window.setInterval(() => {
      void loadHealth();
    }, POLL_INTERVAL_MS);

    return () => {
      window.clearTimeout(initialFetch);
      window.clearInterval(interval);
    };
  }, [loadHealth]);

  return {
    health,
    isLoading,
    error,
    refresh: loadHealth,
  };
};
