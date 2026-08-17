// API types matching chatpid/api.py

export interface ToolUsage {
  name: string;
  args: Record<string, unknown>;
}

export interface AskResponse {
  answer: string;
  tools_used: ToolUsage[];
  latency_seconds: number;
  graph_node_ids: string[];
}

export interface GraphNode {
  id: string;
  label: string;
  tags: string[];
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  level: string;
  total_nodes: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function askQuestion(question: string): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getGraph(level = 'conceptual', limit = 200): Promise<GraphResponse> {
  const res = await fetch(`${API_BASE}/graph?level=${level}&limit=${limit}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
