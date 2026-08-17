'use client';

import { useEffect, useState, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeTypes,
  Position,
  Handle,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Loader2, Network } from 'lucide-react';
import { getGraph, type GraphResponse, type GraphNode } from '@/lib/api';

// Node type colors based on label
const NODE_COLORS: Record<string, string> = {
  CentrifugalPump: '#0071CE',
  HeatExchanger: '#F47C6D',
  Tank: '#4DB848',
  Valve: '#A27CC9',
  BallValve: '#A27CC9',
  GlobeValve: '#A27CC9',
  SwingCheckValve: '#A27CC9',
  SafetyValve: '#DC3545',
  ControlValve: '#A27CC9',
  PipeTee: '#F5BD1E',
  PipeReducer: '#F5BD1E',
  BlindFlange: '#A7A9AC',
  PipingNodeOwner: '#374785',
  OffPageConnector: '#00B5E2',
  FlowInPipeOffPageConnector: '#00B5E2',
  FlowOutPipeOffPageConnector: '#00B5E2',
};

interface GraphPanelProps {
  highlightedNodes?: string[]; // tags touched by last answer
  level?: string;
}

// Custom node component
function PidNode({ data }: { data: { label: string; tag: string; highlighted: boolean } }) {
  const color = NODE_COLORS[data.label] || '#64748B';
  return (
    <>
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <div
        style={{
          padding: '6px 10px',
          borderRadius: '8px',
          backgroundColor: data.highlighted ? color : 'var(--card-bg)',
          color: data.highlighted ? '#fff' : 'var(--primary-text)',
          border: `2px solid ${color}`,
          fontSize: '11px',
          fontWeight: 500,
          minWidth: '60px',
          textAlign: 'center',
          boxShadow: data.highlighted ? `0 0 8px ${color}80` : 'none',
          transition: 'all 0.2s',
        }}
      >
        {data.tag || data.label}
      </div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </>
  );
}

const nodeTypes: NodeTypes = { pidNode: PidNode };

export function GraphPanel({ highlightedNodes = [], level = 'conceptual' }: GraphPanelProps) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalNodes, setTotalNodes] = useState(0);

  const loadGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data: GraphResponse = await getGraph(level, 200);
      setTotalNodes(data.total_nodes);

      // Build a tag-to-nodeId map for highlighting
      const highlightSet = new Set(highlightedNodes.map((t) => t.toLowerCase()));

      const flowNodes: Node[] = data.nodes.map((n: GraphNode, i) => {
        const tag = n.tags[0] || '';
        const isHighlighted = highlightSet.has(tag.toLowerCase());
        return {
          id: n.id,
          type: 'pidNode',
          position: {
            // Circular layout
            x: Math.cos((i / data.nodes.length) * 2 * Math.PI) * 250 + 300,
            y: Math.sin((i / data.nodes.length) * 2 * Math.PI) * 250 + 300,
          },
          data: { label: n.label, tag, highlighted: isHighlighted },
        };
      });

      const flowEdges: Edge[] = data.edges.map((e) => ({
        id: `${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        animated: false,
        style: { stroke: 'var(--muted-text)', strokeWidth: 1.5 },
      }));

      setNodes(flowNodes);
      setEdges(flowEdges);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load graph');
    } finally {
      setLoading(false);
    }
  }, [level, highlightedNodes.join(',')]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  // Update highlighted nodes when they change
  useEffect(() => {
    const highlightSet = new Set(highlightedNodes.map((t) => t.toLowerCase()));
    setNodes((nds) =>
      nds.map((n) => {
        const tag = (n.data as { tag?: string }).tag || '';
        return {
          ...n,
          data: {
            ...n.data,
            highlighted: highlightSet.has(tag.toLowerCase()),
          },
        };
      })
    );
  }, [highlightedNodes]);

  return (
    <div className="flex h-full flex-col" style={{ backgroundColor: 'var(--pane-bg)' }}>
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: 'var(--pane-border)' }}>
        <div className="flex items-center gap-2">
          <Network className="h-4 w-4" style={{ color: 'var(--brand-primary)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--primary-text)' }}>
            P&amp;ID Graph
          </h2>
        </div>
        <span className="text-xs" style={{ color: 'var(--muted-text)' }}>
          {totalNodes} nodes · {level}
        </span>
      </div>

      {/* Graph */}
      <div className="relative flex-1 overflow-hidden">
        {loading && (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin" style={{ color: 'var(--muted-text)' }} />
          </div>
        )}
        {error && (
          <div className="flex h-full items-center justify-center p-4 text-center">
            <div>
              <p className="text-sm" style={{ color: 'var(--status-error)' }}>{error}</p>
              <p className="mt-2 text-xs" style={{ color: 'var(--muted-text)' }}>
                Make sure the API is running on port 8000
              </p>
            </div>
          </div>
        )}
        {!loading && !error && (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            proOptions={{ hideAttribution: true }}
            style={{ backgroundColor: 'var(--app-bg)' }}
          >
            <Background color="var(--pane-border)" gap={20} />
            <Controls
              style={{
                backgroundColor: 'var(--card-bg)',
                borderColor: 'var(--pane-border)',
              }}
            />
            <MiniMap
              pannable
              zoomable
              style={{
                backgroundColor: 'var(--card-bg)',
              }}
            />
          </ReactFlow>
        )}
      </div>
    </div>
  );
}
