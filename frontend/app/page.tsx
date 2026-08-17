'use client';

import { useState } from 'react';
import { Play, Square } from 'lucide-react';
import { ChatPanel } from '@/components/ChatPanel';
import { GraphPanel } from '@/components/GraphPanel';

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

export default function Home() {
  const [highlightedNodes, setHighlightedNodes] = useState<string[]>([]);
  const [demoRunning, setDemoRunning] = useState(false);

  // The demo is driven by the ChatPanel via a ref-like pattern.
  // We use a simple approach: a "demo trigger" counter that, when incremented,
  // tells the ChatPanel to run the next demo question.
  // For simplicity, we just pass the demo questions as suggested questions.

  return (
    <div className="flex h-screen w-screen overflow-hidden" style={{ backgroundColor: 'var(--app-bg)' }}>
      {/* Sidebar */}
      <aside
        className="flex w-56 flex-col py-6"
        style={{ backgroundColor: 'var(--sidebar-bg)', color: 'var(--sidebar-text)' }}
      >
        <div className="flex flex-col items-center gap-2">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg text-lg font-bold"
            style={{ backgroundColor: 'var(--brand-primary)', color: 'var(--inverse-text)' }}
          >
            P&amp;ID
          </div>
          <span className="text-sm font-semibold">ChatP&amp;ID</span>
          <span className="text-xs opacity-60">GraphRAG Demo</span>
        </div>

        {/* Demo walkthrough */}
        <div className="mt-8 flex flex-col gap-3 px-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider opacity-60">Demo Walkthrough</h3>
          {DEMO_QUESTIONS.map((q, i) => (
            <div key={i} className="space-y-1">
              <div className="flex items-start gap-2">
                <span
                  className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold"
                  style={{ backgroundColor: 'var(--brand-primary)', color: 'var(--inverse-text)' }}
                >
                  {i + 1}
                </span>
                <div>
                  <p className="text-xs font-medium leading-snug">{q.question}</p>
                  <p className="text-xs opacity-50">{q.description}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-auto px-4 text-xs opacity-50">Sprint 5</div>
      </aside>

      {/* Main content — chat + graph panels side by side */}
      <main className="flex flex-1 overflow-hidden">
        <div className="flex-1 overflow-hidden border-r" style={{ borderColor: 'var(--pane-border)' }}>
          <ChatPanel onTouchedNodes={setHighlightedNodes} demoQuestions={DEMO_QUESTIONS.map((q) => q.question)} />
        </div>
        <div className="flex-1 overflow-hidden">
          <GraphPanel highlightedNodes={highlightedNodes} />
        </div>
      </main>
    </div>
  );
}
