'use client';

import { useEffect, useState, useCallback, useMemo } from 'react';
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
  Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from '@dagrejs/dagre';
import { Loader2, Network, Search, X, Info } from 'lucide-react';
import { getGraph, type GraphResponse, type GraphNode } from '@/lib/api';

// Node type colors based on label
const NODE_COLORS: Record<string, string> = {
  CentrifugalPump: '#0071CE',
  Pump: '#0071CE',
  HeatExchanger: '#F47C6D',
  Heater: '#F47C6D',
  Tank: '#4DB848',
  Vessel: '#4DB848',
  ProcessColumn: '#2E86AB',
  Compressor: '#E36B6B',
  Mixer: '#9B59B6',
  OperatedValve: '#A27CC9',
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

// Group labels for the legend (collapses valve variants into one entry)
const LEGEND_GROUPS: { label: string; color: string; aliases: string[] }[] = [
  { label: 'Pump', color: NODE_COLORS.Pump, aliases: ['CentrifugalPump', 'Pump'] },
  { label: 'Heat Exchanger', color: NODE_COLORS.HeatExchanger, aliases: ['HeatExchanger', 'Heater'] },
  { label: 'Tank / Vessel', color: NODE_COLORS.Tank, aliases: ['Tank', 'Vessel'] },
  { label: 'Process Column', color: NODE_COLORS.ProcessColumn, aliases: ['ProcessColumn'] },
  { label: 'Compressor', color: NODE_COLORS.Compressor, aliases: ['Compressor'] },
  { label: 'Mixer', color: NODE_COLORS.Mixer, aliases: ['Mixer'] },
  { label: 'Valve', color: NODE_COLORS.OperatedValve, aliases: ['OperatedValve', 'Valve', 'BallValve', 'GlobeValve', 'SwingCheckValve', 'ControlValve'] },
  { label: 'Safety Valve', color: NODE_COLORS.SafetyValve, aliases: ['SafetyValve'] },
  { label: 'Pipe Fitting', color: NODE_COLORS.PipeTee, aliases: ['PipeTee', 'PipeReducer'] },
  { label: 'Connector', color: NODE_COLORS.OffPageConnector, aliases: ['OffPageConnector', 'FlowInPipeOffPageConnector', 'FlowOutPipeOffPageConnector'] },
  { label: 'Other', color: '#64748B', aliases: [] },
];

function getNodeColor(label: string): string {
  return NODE_COLORS[label] || '#64748B';
}

// Dagre layout — hierarchical, flow-direction-aware (left to right)
function layoutGraph(nodes: Node[], edges: Edge[], direction: 'LR' | 'TB' = 'LR'): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, nodesep: 40, ranksep: 80, marginx: 20, marginy: 20 });

  nodes.forEach((node) => {
    g.setNode(node.id, { width: 120, height: 40 });
  });
  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  dagre.layout(g);

  const layoutedNodes = nodes.map((node) => {
    const pos = g.node(node.id);
    return { ...node, position: { x: pos.x - 60, y: pos.y - 20 } };
  });

  return { nodes: layoutedNodes, edges };
}

interface GraphPanelProps {
  highlightedNodes?: string[];
  level?: string;
}

// Custom node component
function PidNode({ data }: { data: { label: string; tag: string; highlighted: boolean; properties?: Record<string, unknown> } }) {
  const color = getNodeColor(data.label);
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
          boxShadow: data.highlighted ? `0 0 12px ${color}80` : 'none',
          transition: 'all 0.2s',
          cursor: 'pointer',
        }}
      >
        {data.tag || data.label}
      </div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </>
  );
}

const nodeTypes: NodeTypes = { pidNode: PidNode };

export function GraphPanel({ highlightedNodes = [], level: initialLevel = 'conceptual' }: GraphPanelProps) {
  const [currentLevel, setCurrentLevel] = useState<string>(initialLevel);
  const [selectedDoc, setSelectedDoc] = useState<string>('');
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalNodes, setTotalNodes] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [showLegend, setShowLegend] = useState(true);

  const loadGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data: GraphResponse = await getGraph(currentLevel, 500, selectedDoc);
      setTotalNodes(data.total_nodes);

      const highlightSet = new Set(highlightedNodes.map((t) => t.toLowerCase()));

      const flowNodes: Node[] = data.nodes.map((n: GraphNode) => {
        const tag = n.tags[0] || '';
        const isHighlighted = highlightSet.has(tag.toLowerCase());
        return {
          id: n.id,
          type: 'pidNode',
          position: { x: 0, y: 0 }, // will be set by dagre
          data: { label: n.label, tag, highlighted: isHighlighted, properties: n.properties },
        };
      });

      // Only show edge labels if there are multiple distinct relationship types
      // (if all edges are the same type, e.g. all PIPE, labels add noise without info)
      const edgeTypes = new Set(data.edges.map((e) => e.type));
      const showEdgeLabels = edgeTypes.size > 1;

      const flowEdges: Edge[] = data.edges.map((e) => ({
        id: `${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        animated: false,
        label: showEdgeLabels ? (e.type || undefined) : undefined,
        labelStyle: { fill: 'var(--muted-text)', fontSize: 9, fontWeight: 500 },
        labelBgStyle: { fill: 'var(--card-bg)', fillOpacity: 0.8 },
        labelBgPadding: [4, 2] as [number, number],
        style: { stroke: 'var(--muted-text)', strokeWidth: 1.5 },
      }));

      // Apply dagre layout
      const { nodes: laidOutNodes, edges: laidOutEdges } = layoutGraph(flowNodes, flowEdges);
      setNodes(laidOutNodes);
      setEdges(laidOutEdges);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load graph');
    } finally {
      setLoading(false);
    }
  }, [currentLevel, selectedDoc, highlightedNodes.join(',')]);

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

  // Filter nodes by search query — dims non-matching nodes
  const displayNodes = useMemo(() => {
    if (!searchQuery.trim()) return nodes;
    const q = searchQuery.toLowerCase();
    return nodes.map((n) => {
      const tag = ((n.data as { tag?: string }).tag || '').toLowerCase();
      const label = ((n.data as { label?: string }).label || '').toLowerCase();
      const matches = tag.includes(q) || label.includes(q);
      return {
        ...n,
        style: matches ? undefined : { opacity: 0.15 },
      };
    });
  }, [nodes, searchQuery]);

  // Equipment type counts for legend
  const equipmentCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    nodes.forEach((n) => {
      const label = (n.data as { label?: string }).label || 'Unknown';
      counts[label] = (counts[label] || 0) + 1;
    });
    return counts;
  }, [nodes]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
  }, []);

  return (
    <div className="flex h-full flex-col" style={{ backgroundColor: 'var(--pane-bg)' }}>
      {/* Header with Level Switcher & P&ID selector */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2.5" style={{ borderColor: 'var(--pane-border)' }}>
        <div className="flex items-center gap-2">
          <Network className="h-4 w-4" style={{ color: 'var(--brand-primary)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--primary-text)' }}>
            P&amp;ID Graph
          </h2>

          {/* Document selector */}
          <select
            value={selectedDoc}
            onChange={(e) => setSelectedDoc(e.target.value)}
            className="text-xs border rounded px-2 py-1 outline-none"
            style={{
              backgroundColor: 'var(--card-bg)',
              borderColor: 'var(--pane-border)',
              color: 'var(--primary-text)',
            }}
          >
            <option value="">All P&amp;IDs</option>
            <option value="C01V04">C01 (Reference P&amp;ID)</option>
            <option value="C02V03">C02 (BASF Column)</option>
            <option value="C03V04">C03 (Equinor Piping)</option>
          </select>
        </div>

        {/* Level Switcher (Conceptual / Process / Complete) */}
        <div className="flex items-center gap-1 rounded-md p-0.5 border" style={{ borderColor: 'var(--pane-border)', backgroundColor: 'var(--card-bg)' }}>
          {(['conceptual', 'process', 'complete'] as const).map((lvl) => (
            <button
              key={lvl}
              onClick={() => setCurrentLevel(lvl)}
              className="px-2.5 py-0.5 text-xs rounded font-medium capitalize transition-colors"
              style={{
                backgroundColor: currentLevel === lvl ? 'var(--brand-primary)' : 'transparent',
                color: currentLevel === lvl ? 'var(--inverse-text)' : 'var(--muted-text)',
              }}
            >
              {lvl}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          {/* Search box */}
          <div className="relative">
            <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2" style={{ color: 'var(--muted-text)' }} />
            <input
              type="text"
              placeholder="Search tag..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-28 rounded-md border py-1 pl-7 pr-2 text-xs outline-none"
              style={{
                backgroundColor: 'var(--card-bg)',
                borderColor: 'var(--pane-border)',
                color: 'var(--primary-text)',
              }}
            />
          </div>
          <span className="text-xs font-mono" style={{ color: 'var(--muted-text)' }}>
            {totalNodes} nodes
          </span>
        </div>
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
            nodes={displayNodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodeClick={onNodeClick}
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

            {/* Legend */}
            {showLegend && (
              <Panel position="top-left">
                <div
                  className="rounded-lg border p-3"
                  style={{
                    backgroundColor: 'var(--card-bg)',
                    borderColor: 'var(--pane-border)',
                    maxWidth: '200px',
                  }}
                >
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-semibold" style={{ color: 'var(--primary-text)' }}>
                      Equipment Types
                    </span>
                    <button
                      onClick={() => setShowLegend(false)}
                      className="opacity-50 hover:opacity-100"
                      style={{ color: 'var(--muted-text)' }}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                  <div className="flex flex-col gap-1">
                    {LEGEND_GROUPS.filter((g) => {
                      // Only show groups that have nodes in this graph
                      return g.aliases.some((a) => equipmentCounts[a]) || (g.label === 'Other' && Object.keys(equipmentCounts).some((k) => !NODE_COLORS[k]));
                    }).map((group) => {
                      const count = group.aliases.reduce((sum, a) => sum + (equipmentCounts[a] || 0), 0);
                      return (
                        <div key={group.label} className="flex items-center gap-2">
                          <div
                            className="h-3 w-3 flex-shrink-0 rounded"
                            style={{ backgroundColor: group.color }}
                          />
                          <span className="text-xs" style={{ color: 'var(--primary-text)' }}>
                            {group.label}
                          </span>
                          {count > 0 && (
                            <span className="ml-auto text-xs opacity-50" style={{ color: 'var(--muted-text)' }}>
                              {count}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </Panel>
            )}
            {!showLegend && (
              <Panel position="top-left">
                <button
                  onClick={() => setShowLegend(true)}
                  className="flex items-center gap-1 rounded-lg border px-2 py-1 text-xs"
                  style={{
                    backgroundColor: 'var(--card-bg)',
                    borderColor: 'var(--pane-border)',
                    color: 'var(--muted-text)',
                  }}
                >
                  <Info className="h-3 w-3" /> Legend
                </button>
              </Panel>
            )}

            {/* Node properties panel */}
            {selectedNode && (
              <Panel position="top-right">
                <div
                  className="rounded-lg border p-3"
                  style={{
                    backgroundColor: 'var(--card-bg)',
                    borderColor: 'var(--pane-border)',
                    maxWidth: '260px',
                  }}
                >
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-semibold" style={{ color: 'var(--primary-text)' }}>
                      Node Properties
                    </span>
                    <button
                      onClick={() => setSelectedNode(null)}
                      className="opacity-50 hover:opacity-100"
                      style={{ color: 'var(--muted-text)' }}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    {(() => {
                      const props = selectedNode.data.properties as Record<string, unknown> | undefined;
                      const propEntries = props && typeof props === 'object'
                        ? Object.entries(props)
                            .filter(([k]) => !['embedding', 'embedding_vector'].includes(k))
                            .slice(0, 12)
                        : [];
                      return (
                        <>
                    <div className="flex items-center gap-2">
                      <div
                        className="h-3 w-3 flex-shrink-0 rounded"
                        style={{ backgroundColor: getNodeColor((selectedNode.data as { label?: string }).label || '') }}
                      />
                      <span className="text-xs font-medium" style={{ color: 'var(--primary-text)' }}>
                        {(selectedNode.data as { tag?: string }).tag || (selectedNode.data as { label?: string }).label}
                      </span>
                    </div>
                    <div className="text-xs opacity-60" style={{ color: 'var(--muted-text)' }}>
                      Type: {(selectedNode.data as { label?: string }).label}
                    </div>
                    {propEntries.length > 0 && (
                      <div className="mt-1 flex flex-col gap-0.5">
                        {propEntries.map(([key, value]) => (
                            <div key={key} className="flex justify-between gap-2 text-xs">
                              <span className="opacity-50" style={{ color: 'var(--muted-text)' }}>{key}:</span>
                              <span className="text-right" style={{ color: 'var(--primary-text)' }}>
                                {typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'
                                  ? String(value)
                                  : Array.isArray(value)
                                    ? `${value.length} items`
                                    : '...'}
                              </span>
                            </div>
                          ))}
                      </div>
                    )}
                        </>
                      );
                    })()}
                  </div>
                </div>
              </Panel>
            )}
          </ReactFlow>
        )}
      </div>
    </div>
  );
}
