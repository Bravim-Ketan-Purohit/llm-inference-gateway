"use client";

import { useState, useEffect } from "react";

interface CacheStats {
  hits: number;
  misses: number;
  hitRate: number;
}

export default function CacheView() {
  const [stats, setStats] = useState<CacheStats>({
    hits: 0,
    misses: 0,
    hitRate: 0,
  });

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch("/api/metrics");
        if (res.ok) {
          const text = await res.text();
          // Parse Prometheus metrics
          const hits = parseMetric(text, "gateway_cache_hits_total");
          const misses = parseMetric(text, "gateway_cache_misses_total");
          const total = hits + misses;
          setStats({
            hits,
            misses,
            hitRate: total > 0 ? hits / total : 0,
          });
        }
      } catch {
        // Gateway not available
      }
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Cache Performance</h2>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-gray-800 rounded-lg p-4">
          <p className="text-gray-400 text-sm">Hit Rate</p>
          <p className="text-2xl font-bold text-green-400">
            {(stats.hitRate * 100).toFixed(1)}%
          </p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <p className="text-gray-400 text-sm">Hits</p>
          <p className="text-2xl font-bold">{stats.hits}</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <p className="text-gray-400 text-sm">Misses</p>
          <p className="text-2xl font-bold">{stats.misses}</p>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg p-4">
        <p className="text-gray-400 text-sm mb-2">Cache Hit Rate</p>
        <div className="w-full bg-gray-700 rounded-full h-4">
          <div
            className="bg-green-500 h-4 rounded-full transition-all duration-500"
            style={{ width: `${stats.hitRate * 100}%` }}
            role="progressbar"
            aria-valuenow={stats.hitRate * 100}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Cache hit rate"
          />
        </div>
      </div>
    </div>
  );
}

function parseMetric(text: string, name: string): number {
  const lines = text.split("\n");
  let total = 0;
  for (const line of lines) {
    if (line.startsWith(name) && !line.startsWith("#")) {
      const parts = line.split(" ");
      total += parseFloat(parts[parts.length - 1]) || 0;
    }
  }
  return total;
}
