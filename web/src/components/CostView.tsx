"use client";

import { useState, useEffect } from "react";

interface CostData {
  totalTokens: number;
  cachedTokens: number;
  estimatedSavings: number;
}

export default function CostView() {
  const [cost, setCost] = useState<CostData>({
    totalTokens: 0,
    cachedTokens: 0,
    estimatedSavings: 0,
  });

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch("/api/metrics");
        if (res.ok) {
          const text = await res.text();
          const totalTokens = parseMetric(text, "gateway_tokens_total");
          const cacheHits = parseMetric(text, "gateway_cache_hits_total");
          // Estimate: avg 500 tokens per cached response at $0.01/1K tokens
          const estimatedSavings = cacheHits * 500 * 0.00001;
          setCost({
            totalTokens,
            cachedTokens: cacheHits * 500,
            estimatedSavings,
          });
        }
      } catch {
        // Gateway not available
      }
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Cost Savings</h2>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-gray-800 rounded-lg p-4">
          <p className="text-gray-400 text-sm">Total Tokens</p>
          <p className="text-2xl font-bold">
            {cost.totalTokens.toLocaleString()}
          </p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <p className="text-gray-400 text-sm">Cached Tokens</p>
          <p className="text-2xl font-bold text-green-400">
            {cost.cachedTokens.toLocaleString()}
          </p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <p className="text-gray-400 text-sm">Est. Savings</p>
          <p className="text-2xl font-bold text-green-400">
            ${cost.estimatedSavings.toFixed(4)}
          </p>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg p-4">
        <h3 className="text-sm text-gray-400 mb-2">Savings Breakdown</h3>
        <p className="text-gray-300 text-sm">
          Every cache hit saves an LLM inference call. With semantic caching,
          paraphrased queries also benefit from previously computed responses.
        </p>
        <p className="text-gray-500 text-xs mt-2">
          Cost estimate based on $0.01 per 1K tokens (varies by provider)
        </p>
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
