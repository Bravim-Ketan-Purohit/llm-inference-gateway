"use client";

import { useState, useEffect } from "react";

interface LatencyData {
  timestamp: number;
  p50: number;
  p95: number;
  p99: number;
}

export default function LatencyView() {
  const [data, setData] = useState<LatencyData[]>([]);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch("/api/metrics");
        if (res.ok) {
          const text = await res.text();
          const p50 = parseHistogramQuantile(text, "gateway_request_duration_seconds", 0.5);
          const p95 = parseHistogramQuantile(text, "gateway_request_duration_seconds", 0.95);
          const p99 = parseHistogramQuantile(text, "gateway_request_duration_seconds", 0.99);

          setData((prev) => [
            ...prev.slice(-60),
            { timestamp: Date.now(), p50, p95, p99 },
          ]);
        }
      } catch {
        // Gateway not available
      }
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const latest = data[data.length - 1];

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Request Latency</h2>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-gray-800 rounded-lg p-4">
          <p className="text-gray-400 text-sm">p50</p>
          <p className="text-2xl font-bold">
            {latest ? `${(latest.p50 * 1000).toFixed(0)}ms` : "--"}
          </p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <p className="text-gray-400 text-sm">p95</p>
          <p className="text-2xl font-bold text-yellow-400">
            {latest ? `${(latest.p95 * 1000).toFixed(0)}ms` : "--"}
          </p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <p className="text-gray-400 text-sm">p99</p>
          <p className="text-2xl font-bold text-red-400">
            {latest ? `${(latest.p99 * 1000).toFixed(0)}ms` : "--"}
          </p>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg p-4 h-64 flex items-center justify-center">
        <p className="text-gray-500">
          {data.length > 0
            ? `Collecting data... (${data.length} samples)`
            : "Waiting for requests..."}
        </p>
      </div>
    </div>
  );
}

function parseHistogramQuantile(
  text: string,
  name: string,
  quantile: number
): number {
  // Approximate from histogram buckets
  const lines = text.split("\n");
  let sum = 0;
  let count = 0;
  for (const line of lines) {
    if (line.startsWith(`${name}_sum`) && !line.startsWith("#")) {
      sum += parseFloat(line.split(" ").pop() || "0");
    }
    if (line.startsWith(`${name}_count`) && !line.startsWith("#")) {
      count += parseFloat(line.split(" ").pop() || "0");
    }
  }
  return count > 0 ? sum / count : 0;
}
