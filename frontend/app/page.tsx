'use client';

import { useState } from 'react';
import { ChatPanel } from '@/components/ChatPanel';
import { GraphPanel } from '@/components/GraphPanel';

export default function Home() {
  const [highlightedNodes, setHighlightedNodes] = useState<string[]>([]);

  return (
    <div className="flex h-screen w-screen overflow-hidden" style={{ backgroundColor: 'var(--app-bg)' }}>
      {/* Sidebar */}
      <aside
        className="flex w-56 flex-col items-center justify-between py-6"
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
        <div className="text-xs opacity-50">Sprint 5</div>
      </aside>

      {/* Main content — chat + graph panels side by side */}
      <main className="flex flex-1 overflow-hidden">
        <div className="flex-1 overflow-hidden border-r" style={{ borderColor: 'var(--pane-border)' }}>
          <ChatPanel onTouchedNodes={setHighlightedNodes} />
        </div>
        <div className="flex-1 overflow-hidden">
          <GraphPanel highlightedNodes={highlightedNodes} />
        </div>
      </main>
    </div>
  );
}
