"use client";

import { useState, useEffect } from "react";

interface HealthStatus {
  backends: Record<string, boolean>;
  circuitBreakers: Record<string, string>;
}

export default function LiveView() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [rps, setRps] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch("/api/v1/backends/health");
        if (res.ok) {
          const data = await res.json();
          setHealth({
            backends: data.backends || {},
            circuitBreakers: data.circuit_breakers || {},
          });
          setError(null);
        }
      } catch {
        setError("Gateway not reachable");
      }
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">System Status</h2>

      {error && (
        <div className="bg-red-900/50 border border-red-700 rounded-lg p-4">
          <p className="text-red-300">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-3">Backends</h3>
          {health ? (
            <ul className="space-y-2">
              {Object.entries(health.backends).map(([name, healthy]) => (
                <li key={name} className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      healthy ? "bg-green-400" : "bg-red-400"
                    }`}
                    aria-hidden="true"
                  />
                  <span>{name}</span>
                  <span className="text-xs text-gray-500">
                    {healthy ? "healthy" : "down"}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-500">Loading...</p>
          )}
        </div>

        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-3">
            Circuit Breakers
          </h3>
          {health ? (
            <ul className="space-y-2">
              {Object.entries(health.circuitBreakers).map(([name, state]) => (
                <li key={name} className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      state === "closed"
                        ? "bg-green-400"
                        : state === "half_open"
                        ? "bg-yellow-400"
                        : "bg-red-400"
                    }`}
                    aria-hidden="true"
                  />
                  <span>{name}</span>
                  <span className="text-xs text-gray-500">{state}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-500">Loading...</p>
          )}
        </div>
      </div>
    </div>
  );
}
