'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeTypes,
  type NodeChange,
  type OnNodesChange,
  Position,
  Handle,
  Panel,
  useNodesState,
  useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  forceX,
  forceY,
  type Simulation,
  type SimulationNodeDatum,
} from 'd3-force';
import { Loader2, Network, Search, X, Info } from 'lucide-react';
import { getGraph, type GraphResponse, type GraphNode } from '@/lib/api';

// Node type colors based on label
const NODE_COLORS: Record<string, string> = {
  // Pumps
  CentrifugalPump: '#0071CE',
  ReciprocatingPump: '#0071CE',
  Pump: '#0071CE',

  // Heat Exchangers
  PlateHeatExchanger: '#F47C6D',
  TubularHeatExchanger: '#F47C6D',
  HeatExchanger: '#F47C6D',
  Heater: '#F47C6D',

  // Tanks & Columns
  Tank: '#4DB848',
  Vessel: '#4DB848',
  PressureVessel: '#4DB848',
  ProcessColumn: '#2E86AB',
  Compressor: '#E36B6B',
  Mixer: '#9B59B6',

  // Valves
  OperatedValve: '#A27CC9',
  Valve: '#A27CC9',
  BallValve: '#A27CC9',
  GlobeValve: '#8E44AD',
  ButterflyValve: '#9B59B6',
  SwingCheckValve: '#6C5CE7',
  CheckValve: '#6C5CE7',
  ControlValve: '#A27CC9',

  // Safety Valves
  SafetyValveOrFitting: '#DC3545',
  SpringLoadedGlobeSafetyValve: '#DC3545',
  SafetyValve: '#DC3545',

  // Pipe Fittings
  PipeTee: '#F5BD1E',
  PipeReducer: '#E67E22',
  BlindFlange: '#A7A9AC',
  Flange: '#B2BEC3',
  PipeFitting: '#F5BD1E',
  RestrictionOrifice: '#D35400',

  // Instrumentation & Controls
  ProcessInstrumentationFunction: '#10B981',
  ProcessSignalGeneratingFunction: '#059669',
  ActuatingFunction: '#047857',

  // Connectors
  OffPageConnector: '#00B5E2',
  FlowInPipeOffPageConnector: '#00B5E2',
  FlowOutPipeOffPageConnector: '#0984E3',
  PipeOffPageConnectorReferenceByNumber: '#74B9FF',
  PipeOffPageConnectorReference: '#74B9FF',
};

// Group labels for the legend
const LEGEND_GROUPS: { label: string; color: string; aliases: string[] }[] = [
  { label: 'Pump', color: '#0071CE', aliases: ['CentrifugalPump', 'ReciprocatingPump', 'Pump'] },
  { label: 'Heat Exchanger', color: '#F47C6D', aliases: ['PlateHeatExchanger', 'TubularHeatExchanger', 'HeatExchanger', 'Heater'] },
  { label: 'Tank / Vessel', color: '#4DB848', aliases: ['Tank', 'Vessel', 'PressureVessel'] },
  { label: 'Process Column', color: '#2E86AB', aliases: ['ProcessColumn'] },
  { label: 'Valve', color: '#A27CC9', aliases: ['OperatedValve', 'Valve', 'BallValve', 'GlobeValve', 'ButterflyValve', 'SwingCheckValve', 'CheckValve', 'ControlValve'] },
  { label: 'Safety Valve', color: '#DC3545', aliases: ['SafetyValveOrFitting', 'SpringLoadedGlobeSafetyValve', 'SafetyValve'] },
  { label: 'Pipe Fitting', color: '#F5BD1E', aliases: ['PipeTee', 'PipeReducer', 'BlindFlange', 'Flange', 'PipeFitting', 'RestrictionOrifice'] },
  { label: 'Instrumentation', color: '#10B981', aliases: ['ProcessInstrumentationFunction', 'ProcessSignalGeneratingFunction', 'ActuatingFunction'] },
  { label: 'Connector', color: '#00B5E2', aliases: ['OffPageConnector', 'FlowInPipeOffPageConnector', 'FlowOutPipeOffPageConnector', 'PipeOffPageConnectorReferenceByNumber', 'PipeOffPageConnectorReference'] },
  { label: 'Other', color: '#64748B', aliases: [] },
];

function getNodeColor(label: string): string {
  return NODE_COLORS[label] || '#64748B';
}

// --- d3-force types ---
interface SimNode extends SimulationNodeDatum {
  id: string;
}
interface SimLink {
  source: string | SimNode;
  target: string | SimNode;
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
          transition: 'background-color 0.2s, box-shadow 0.2s',
          cursor: 'grab',
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
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges] = useEdgesState<Edge>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalNodes, setTotalNodes] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [showLegend, setShowLegend] = useState(true);

  // d3-force simulation ref — kept across renders, cleaned up on unmount/data change
  const simulationRef = useRef<Simulation<SimNode, SimLink> | null>(null);
  // Sim node array ref — mutable objects d3-force updates in-place
  const simNodesRef = useRef<SimNode[]>([]);
  const simLinksRef = useRef<SimLink[]>([]);
  // Map from ReactFlow node id -> index in simNodesRef for fast lookups
  const idToIndexRef = useRef<Map<string, number>>(new Map());
  // Track whether the user is actively dragging a node
  const draggingRef = useRef<string | null>(null);

  const highlightedKey = highlightedNodes.join(',');
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
          position: { x: 0, y: 0 },
          data: { label: n.label, tag, highlighted: isHighlighted, properties: n.properties },
        };
      });

      // Only show edge labels if there are multiple distinct relationship types
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

      setNodes(flowNodes);
      setEdges(flowEdges);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load graph');
    } finally {
      setLoading(false);
    }
  }, [currentLevel, selectedDoc, highlightedKey]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  // --- d3-force simulation: start/restart whenever nodes or edges change ---
  useEffect(() => {
    if (nodes.length === 0) return;

    // Stop any previous simulation
    if (simulationRef.current) {
      simulationRef.current.stop();
    }

    // Build mutable sim node objects. Seed positions in a circle to avoid
    // everything starting at (0,0) and exploding outward.
    const simNodes: SimNode[] = nodes.map((n, i) => {
      const angle = (i / nodes.length) * 2 * Math.PI;
      const radius = 200 + Math.random() * 50;
      return {
        id: n.id,
        x: Math.cos(angle) * radius + (Math.random() - 0.5) * 40,
        y: Math.sin(angle) * radius + (Math.random() - 0.5) * 40,
      };
    });

    const idMap = new Map<string, number>();
    simNodes.forEach((sn, i) => idMap.set(sn.id, i));

    const simLinks: SimLink[] = edges.map((e) => ({
      source: e.source,
      target: e.target,
    }));

    simNodesRef.current = simNodes;
    simLinksRef.current = simLinks;
    idToIndexRef.current = idMap;

    // Tuned forces for a "bouncy / fluid" feel:
    //  - charge: strong negative repulsion so nodes spread out
    //  - link: medium-distance springs
    //  - center: gentle pull toward origin so the graph doesn't drift away
    //  - collide: prevents overlap
    //  - forceX/forceY: very mild centering to keep graph centered
    const nodeCount = simNodes.length;
    const chargeStrength = nodeCount > 100 ? -400 : -250;
    const linkDistance = nodeCount > 100 ? 60 : 90;

    const sim = forceSimulation<SimNode>(simNodes)
      .force(
        'link',
        forceLink<SimNode, SimLink>(simLinks)
          .id((d) => d.id)
          .distance(linkDistance)
          .strength(0.3)
      )
      .force('charge', forceManyBody().strength(chargeStrength).distanceMax(500))
      .force('center', forceCenter(0, 0).strength(0.05))
      .force('collide', forceCollide(45))
      .force('x', forceX(0).strength(0.02))
      .force('y', forceY(0).strength(0.02))
      .alpha(1)
      .alphaDecay(0.015) // slower decay = longer bouncy animation
      .velocityDecay(0.3) // lower = more bouncy/springy
      .on('tick', () => {
        // Sync sim positions back to ReactFlow nodes on every tick.
        // We use setNodes with a functional update to avoid stale closures.
        setNodes((prev) =>
          prev.map((n) => {
            const idx = idMap.get(n.id);
            if (idx === undefined) return n;
            const sn = simNodes[idx];
            // Don't override position for the node being dragged — ReactFlow
            // manages its position during drag.
            if (draggingRef.current === n.id && sn.fx !== undefined) {
              return n;
            }
            return {
              ...n,
              position: { x: sn.x ?? 0, y: sn.y ?? 0 },
            };
          })
        );
      });

    simulationRef.current = sim;

    return () => {
      sim.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes.length, edges.length]);

  // Update highlighted nodes when they change (without restarting sim)
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

  // --- Custom onNodesChange: intercept position changes to sync with d3-force ---
  // When a user drags a node, we fix that node's position in the simulation
  // (set fx/fy), which reheats the sim so connected nodes follow organically.
  const onNodesChangeIntercepted = useCallback<OnNodesChange<Node>>(
    (changes: NodeChange<Node>[]) => {
      changes.forEach((change) => {
        if (change.type !== 'position' || !change.position) return;
        const isDragging = change.dragging === true;

        // Drag started: dragging is true and we weren't already tracking this node
        if (isDragging && draggingRef.current !== change.id) {
          draggingRef.current = change.id;
        }

        if (isDragging) {
          // Fix the node's position in the sim
          const idx = idToIndexRef.current.get(change.id);
          if (idx !== undefined) {
            const sn = simNodesRef.current[idx];
            if (sn) {
              sn.fx = change.position.x;
              sn.fy = change.position.y;
              // Reheat the simulation so neighbors adjust
              if (simulationRef.current) {
                simulationRef.current.alpha(0.3).restart();
              }
            }
          }
        }

        // Drag ended: dragging is false/undefined and we were tracking this node
        if (!isDragging && draggingRef.current === change.id) {
          const idx = idToIndexRef.current.get(change.id);
          if (idx !== undefined) {
            const sn = simNodesRef.current[idx];
            if (sn) {
              sn.fx = undefined;
              sn.fy = undefined;
            }
          }
          draggingRef.current = null;
          // Gentle reheat so the graph settles after drag release
          if (simulationRef.current) {
            simulationRef.current.alpha(0.2).restart();
          }
        }
      });
      onNodesChange(changes);
    },
    [onNodesChange]
  );

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

  // Reheat simulation when user clicks the "re-layout" button
  const reheatSimulation = useCallback(() => {
    if (simulationRef.current) {
      // Unfix all nodes and reheat fully
      simNodesRef.current.forEach((sn) => {
        sn.fx = undefined;
        sn.fy = undefined;
      });
      simulationRef.current.alpha(1).restart();
    }
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
          {/* Reheat / re-layout button */}
          <button
            onClick={reheatSimulation}
            className="flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium transition-colors hover:opacity-80"
            style={{
              backgroundColor: 'var(--card-bg)',
              borderColor: 'var(--pane-border)',
              color: 'var(--muted-text)',
            }}
            title="Re-layout graph (physics re-simulation)"
          >
            <Network className="h-3 w-3" /> Re-layout
          </button>
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
            onNodesChange={onNodesChangeIntercepted}
            onNodeClick={onNodeClick}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            proOptions={{ hideAttribution: true }}
            style={{ backgroundColor: 'var(--app-bg)' }}
            // Enhanced pan/zoom for a fluid feel
            minZoom={0.05}
            maxZoom={4}
            zoomOnScroll
            zoomOnPinch
            panOnScroll={false}
            zoomOnDoubleClick
            panOnDrag
            selectionOnDrag={false}
            // Smooth node dragging
            nodesDraggable
            nodesConnectable={false}
          >
            <Background color="var(--pane-border)" gap={20} />
            <Controls
              showInteractive={false}
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
