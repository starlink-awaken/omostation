import React, { useState } from "react";
import type { McpHookState } from "../hooks/useMcp";
import type { SearchResult } from "../mcp/types";

const MOCK_RESULTS: SearchResult[] = [
  { id: "1", title: "Ontology Engineering with OWL 2", snippet: "A comprehensive guide to building OWL 2 ontologies including class hierarchies, property restrictions, and reasoning patterns for knowledge graph construction.", score: 0.96, source: "arXiv" },
  { id: "2", title: "Vector Embeddings for Semantic Search", snippet: "Techniques for generating and indexing dense vector representations of textual data, enabling semantic similarity search across large knowledge corpora.", score: 0.91, source: "Technical Blog" },
  { id: "3", title: "Multi-Agent Orchestration Patterns", snippet: "A survey of architectural patterns for coordinating multiple AI agents, including consensus mechanisms, task delegation, and fault tolerance strategies.", score: 0.87, source: "Conference Paper" },
  { id: "4", title: "Knowledge Graph Construction Pipeline", snippet: "End-to-end pipeline for extracting entities and relationships from unstructured text, entity resolution, and graph population at scale.", score: 0.82, source: "Omostation Docs" },
  { id: "5", title: "MCP Protocol: A Technical Overview", snippet: "Deep dive into the Model Context Protocol, covering transport layers, tool discovery, and security considerations for AI-agent integration.", score: 0.78, source: "GitHub Wiki" },
  { id: "6", title: "Distributed Query Processing", snippet: "Techniques for distributed SPARQL query execution across federated knowledge graph endpoints with cost-based optimization.", score: 0.71, source: "arXiv" },
];

export default function DashboardPage({ mcp }: { mcp: McpHookState }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    setSearched(true);
    try {
      if (mcp.connected) {
        const res = await mcp.callTool("search", { query: query.trim() }) as { results: SearchResult[] } | null;
        setResults(res?.results ?? []);
      } else {
        await new Promise(r => setTimeout(r, 400));
        const q = query.toLowerCase();
        setResults(MOCK_RESULTS.filter(r => r.title.toLowerCase().includes(q) || r.snippet.toLowerCase().includes(q)));
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Search failed");
      setResults(MOCK_RESULTS);
    }
    setSearching(false);
  };

  const stats = results.length > 0 ? {
    total: results.length,
    sources: new Set(results.map(r => r.source)).size,
    avgScore: (results.reduce((a, r) => a + r.score, 0) / results.length).toFixed(2),
  } : null;

  return (
    <div style={{ padding: 32, maxWidth: 960, margin: "0 auto" }}>
      <h2 style={{ color: "#eee", fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Knowledge Dashboard</h2>
      <p style={{ color: "#888", fontSize: 13, marginBottom: 24 }}>
        Semantic search across the omostation knowledge graph
        {!mcp.connected && <span style={{ color: "#e94560" }}> (offline mock data)</span>}
      </p>

      <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        <input value={query} onChange={e => setQuery(e.target.value)}
          placeholder="Search ontologies, papers, concepts..."
          onKeyDown={e => e.key === "Enter" && handleSearch()}
          disabled={searching}
          style={{ flex: 1, padding: "10px 16px", borderRadius: 6, border: "1px solid #2a2a4a", backgroundColor: "#1a1a2e", color: "#c0c0d0", fontSize: 14, outline: "none" }} />
        <button onClick={handleSearch} disabled={searching}
          style={{ padding: "10px 24px", borderRadius: 6, border: "none", backgroundColor: "#e94560", color: "#fff", cursor: "pointer", fontWeight: 600, opacity: searching ? 0.5 : 1 }}>
          {searching ? "Searching..." : "Search"}
        </button>
      </div>

      {error && <div style={{ padding: "10px 16px", marginBottom: 16, backgroundColor: "#2a1515", borderRadius: 6, border: "1px solid #5a2020", color: "#e06060", fontSize: 13 }}>{error}</div>}

      {stats && (
        <div style={{ display: "flex", gap: 16, marginBottom: 24 }}>
          {[{ label: "Total Results", value: stats.total }, { label: "Sources", value: stats.sources }, { label: "Avg Score", value: stats.avgScore }].map(s => (
            <div key={s.label} style={{ flex: 1, padding: "14px 18px", backgroundColor: "#16213e", borderRadius: 8, border: "1px solid #1a1a3e" }}>
              <div style={{ color: "#888", fontSize: 12, marginBottom: 4 }}>{s.label}</div>
              <div style={{ color: "#eee", fontSize: 20, fontWeight: 700 }}>{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {searching && <p style={{ color: "#888", textAlign: "center", padding: 24 }}>Searching knowledge graph...</p>}

      {!searching && searched && results.length === 0 && (
        <div style={{ textAlign: "center", padding: 48, color: "#555" }}>
          <p>No results found for "{query}"</p>
        </div>
      )}

      {!searching && results.map(r => (
        <div key={r.id} style={{ padding: "14px 18px", backgroundColor: "#16213e", borderRadius: 8, border: "1px solid #1a1a3e", marginBottom: 12 }}>
          <div style={{ color: "#e94560", fontSize: 15, fontWeight: 600, marginBottom: 4 }}>{r.title}</div>
          <div style={{ color: "#a0a0b8", fontSize: 13, marginBottom: 6, lineHeight: 1.5 }}>{r.snippet}</div>
          <div style={{ color: "#666", fontSize: 11, display: "flex", gap: 16 }}>
            <span>{r.source}</span>
            <span style={{ color: "#4ecdc4" }}>Score: {r.score.toFixed(2)}</span>
          </div>
        </div>
      ))}

      {!searched && (
        <div style={{ textAlign: "center", padding: 48, color: "#555" }}>
          <p>Enter a query above to search the knowledge graph</p>
        </div>
      )}
    </div>
  );
}
