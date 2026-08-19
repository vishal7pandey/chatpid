'use client';

import { useState } from 'react';
import { ChatPanel } from '@/components/ChatPanel';
import { GraphPanel } from '@/components/GraphPanel';
import { PidViewer } from '@/components/PidViewer';

// Scripted demo walkthrough — 4 questions chosen to hit different GraphRAG tools.
// Each question has a description of which tool it should trigger and why.
const DEMO_QUESTIONS = [
  {
    question: 'What is the cylinder length of tank T4750?',
    description: 'Precise attribute lookup → CypherRAG',
  },
  {
    question: 'Trace the flow path from tank T4750 to pump P4712.',
    description: 'Multi-hop path tracing → PathRAG',
  },
  {
    question: 'List all valves in the P&ID along with their specifications.',
    description: 'List by type → CypherRAG',
  },
  {
    question: 'Analyze the flowsheet and give recommendations regarding process safety.',
    description: 'Broad analysis → ContextRAG',
  },
];

type RightPanelView = 'graph' | 'pid';

export default function Home() {
  const [highlightedNodes, setHighlightedNodes] = useState<string[]>([]);
  const [rightPanel, setRightPanel] = useState<RightPanelView>('graph');

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden" style={{ backgroundColor: 'var(--app-bg)' }}>
      {/* Slim top header bar */}
      <header
        className="flex h-12 flex-shrink-0 items-center gap-3 px-4"
        style={{ backgroundColor: 'var(--sidebar-bg)', color: 'var(--sidebar-text)', borderBottom: '1px solid var(--pane-border)' }}
      >
        <div
          className="flex h-7 w-7 items-center justify-center rounded-md text-sm font-bold"
          style={{ backgroundColor: 'var(--brand-primary)', color: 'var(--inverse-text)' }}
        >
          P&amp;ID
        </div>
        <span className="text-sm font-semibold">ChatP&amp;ID</span>
        <span className="text-xs opacity-50">GraphRAG Demo</span>

        {/* Right panel view toggle */}
        <div className="ml-auto flex items-center gap-1 text-xs">
          <button
            onClick={() => setRightPanel('graph')}
            className="px-2 py-1 rounded font-medium transition-colors"
            style={{
              backgroundColor: rightPanel === 'graph' ? 'var(--brand-primary)' : 'transparent',
              color: rightPanel === 'graph' ? 'var(--inverse-text)' : 'var(--sidebar-text)',
            }}
          >
            Graph
          </button>
          <button
            onClick={() => setRightPanel('pid')}
            className="px-2 py-1 rounded font-medium transition-colors"
            style={{
              backgroundColor: rightPanel === 'pid' ? 'var(--brand-primary)' : 'transparent',
              color: rightPanel === 'pid' ? 'var(--inverse-text)' : 'var(--sidebar-text)',
            }}
          >
            P&amp;ID Diagram
          </button>
        </div>
      </header>

      {/* Main content — chat + right panel side by side */}
      <main className="flex flex-1 overflow-hidden">
        <div className="flex-1 overflow-hidden border-r" style={{ borderColor: 'var(--pane-border)' }}>
          <ChatPanel onTouchedNodes={setHighlightedNodes} demoQuestions={DEMO_QUESTIONS.map((q) => q.question)} />
        </div>
        <div className="flex-1 overflow-hidden">
          {rightPanel === 'graph' ? (
            <GraphPanel highlightedNodes={highlightedNodes} />
          ) : (
            <PidViewer />
          )}
        </div>
      </main>
    </div>
  );
}
