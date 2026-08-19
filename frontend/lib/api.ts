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

export async function askQuestion(
  question: string,
  level: string = 'conceptual',
  documentId: string = ''
): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      level,
      document_id: documentId,
    }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getGraph(level = 'conceptual', limit = 200, documentId = ''): Promise<GraphResponse> {
  const params = new URLSearchParams({ level, limit: String(limit) });
  if (documentId) params.set('document_id', documentId);
  const res = await fetch(`${API_BASE}/graph?${params}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface PidFile {
  filename: string;
  directory: string;
}

export async function listPidFiles(): Promise<PidFile[]> {
  const res = await fetch(`${API_BASE}/pid/files`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  const data = await res.json();
  return data.files;
}

export function getPidSvgUrl(filename: string): string {
  return `${API_BASE}/pid/svg?filename=${encodeURIComponent(filename)}`;
}
