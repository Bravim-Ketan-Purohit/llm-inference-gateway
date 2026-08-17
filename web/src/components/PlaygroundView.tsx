"use client";

import { useState } from "react";

export default function PlaygroundView() {
  const [prompt, setPrompt] = useState("");
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);
  const [model, setModel] = useState("llama3.2:1b");
  const [temperature, setTemperature] = useState(0);
  const [metadata, setMetadata] = useState<Record<string, string>>({});

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    setLoading(true);
    setResponse("");

    try {
      const res = await fetch("/api/v1/chat/completions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer dev-key-1",
        },
        body: JSON.stringify({
          model,
          messages: [{ role: "user", content: prompt }],
          temperature,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const content = data.choices?.[0]?.message?.content || "No response";
        setResponse(content);
        setMetadata({
          model: data.model || model,
          cached: data.system_fingerprint === "cache-hit" ? "yes" : "no",
          tokens: `${data.usage?.total_tokens || 0}`,
        });
      } else {
        setResponse(`Error: ${res.status} ${res.statusText}`);
      }
    } catch (err) {
      setResponse(`Error: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Playground</h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex gap-4">
          <div className="flex-1">
            <label htmlFor="model" className="block text-sm text-gray-400 mb-1">
              Model
            </label>
            <select
              id="model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full bg-gray-800 rounded-lg px-3 py-2 text-white border border-gray-700"
            >
              <option value="llama3.2:1b">llama3.2:1b (Ollama)</option>
              <option value="meta-llama/llama-3.1-8b-instruct">
                Llama 3.1 8B (OpenRouter)
              </option>
            </select>
          </div>
          <div>
            <label
              htmlFor="temperature"
              className="block text-sm text-gray-400 mb-1"
            >
              Temperature: {temperature}
            </label>
            <input
              id="temperature"
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-32"
            />
          </div>
        </div>

        <div>
          <label htmlFor="prompt" className="block text-sm text-gray-400 mb-1">
            Prompt
          </label>
          <textarea
            id="prompt"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={4}
            className="w-full bg-gray-800 rounded-lg px-3 py-2 text-white border border-gray-700 resize-none"
            placeholder="Enter your prompt..."
          />
        </div>

        <button
          type="submit"
          disabled={loading || !prompt.trim()}
          className="px-6 py-2 bg-primary-600 rounded-lg font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Generating..." : "Send"}
        </button>
      </form>

      {response && (
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex gap-2 mb-2">
            {Object.entries(metadata).map(([k, v]) => (
              <span
                key={k}
                className={`text-xs px-2 py-1 rounded ${
                  k === "cached" && v === "yes"
                    ? "bg-green-900 text-green-300"
                    : "bg-gray-700 text-gray-300"
                }`}
              >
                {k}: {v}
              </span>
            ))}
          </div>
          <pre className="whitespace-pre-wrap text-sm text-gray-200">
            {response}
          </pre>
        </div>
      )}
    </div>
  );
}
