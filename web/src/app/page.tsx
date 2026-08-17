"use client";

import { useState } from "react";
import CacheView from "@/components/CacheView";
import LatencyView from "@/components/LatencyView";
import LiveView from "@/components/LiveView";
import CostView from "@/components/CostView";
import PlaygroundView from "@/components/PlaygroundView";

type Tab = "live" | "cache" | "latency" | "cost" | "playground";

export default function Home() {
  const [tab, setTab] = useState<Tab>("live");

  const tabs: { id: Tab; label: string }[] = [
    { id: "live", label: "Live" },
    { id: "cache", label: "Cache" },
    { id: "latency", label: "Latency" },
    { id: "cost", label: "Cost" },
    { id: "playground", label: "Playground" },
  ];

  return (
    <main className="max-w-7xl mx-auto px-4 py-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold">LLM Gateway Dashboard</h1>
        <p className="text-gray-400 mt-1">
          Real-time monitoring for inference gateway
        </p>
      </header>

      <nav className="flex gap-2 mb-6" role="tablist" aria-label="Dashboard views">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              tab === t.id
                ? "bg-primary-600 text-white"
                : "bg-gray-800 text-gray-300 hover:bg-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <section aria-label="Dashboard content">
        {tab === "live" && <LiveView />}
        {tab === "cache" && <CacheView />}
        {tab === "latency" && <LatencyView />}
        {tab === "cost" && <CostView />}
        {tab === "playground" && <PlaygroundView />}
      </section>
    </main>
  );
}
