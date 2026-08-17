'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Loader2, Wrench, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { askQuestion, type AskResponse } from '@/lib/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  tools?: AskResponse['tools_used'];
  latency?: number;
  graphNodes?: string[];
  error?: boolean;
}

const TOOL_COLORS: Record<string, string> = {
  ContextRAG: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  VectorRAG: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  PathRAG: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
  CypherRAG: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
};

const DEFAULT_QUESTIONS = [
  'What is the cylinder length of tank T4750?',
  'Trace the flow path from tank T4750 to pump P4712.',
  'List all valves in the P&ID along with their specifications.',
  'Analyze the flowsheet and give recommendations regarding process safety.',
];

interface ChatPanelProps {
  onTouchedNodes?: (nodes: string[]) => void;
  demoQuestions?: string[];
}

export function ChatPanel({ onTouchedNodes, demoQuestions }: ChatPanelProps) {
  const suggested = demoQuestions || DEFAULT_QUESTIONS;
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const send = useCallback(async (question: string) => {
    if (!question.trim() || loading) return;
    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content: question };
    setMessages((m) => [...m, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await askQuestion(question);
      setMessages((m) => [
        ...m,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: res.answer,
          tools: res.tools_used,
          latency: res.latency_seconds,
          graphNodes: res.graph_node_ids,
        },
      ]);
      onTouchedNodes?.(res.graph_node_ids);
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `Error: ${err instanceof Error ? err.message : 'Failed to get response'}`,
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [loading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    send(input);
  };

  return (
    <div className="flex h-full flex-col" style={{ backgroundColor: 'var(--pane-bg)' }}>
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: 'var(--pane-border)' }}>
        <h2 className="text-sm font-semibold" style={{ color: 'var(--primary-text)' }}>
          ChatP&amp;ID
        </h2>
        <span className="text-xs" style={{ color: 'var(--muted-text)' }}>
          GraphRAG Agent
        </span>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center space-y-4">
            <p className="text-sm" style={{ color: 'var(--muted-text)' }}>
              Ask a question about the P&amp;ID. The agent picks from 4 GraphRAG tools:
            </p>
            <div className="flex flex-wrap gap-2 justify-center">
              {Object.keys(TOOL_COLORS).map((tool) => (
                <span key={tool} className={cn('rounded-full px-3 py-1 text-xs font-medium', TOOL_COLORS[tool])}>
                  {tool}
                </span>
              ))}
            </div>
            <div className="space-y-2 w-full max-w-md">
              {suggested.map((q, i) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="block w-full rounded-lg border px-3 py-2 text-left text-xs transition hover:opacity-80"
                  style={{
                    borderColor: 'var(--pane-border)',
                    color: 'var(--secondary-text)',
                    backgroundColor: 'var(--hover-bg)',
                  }}
                >
                  <span className="font-semibold mr-1.5" style={{ color: 'var(--brand-primary)' }}>{i + 1}.</span>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn('flex animate-fadeIn', msg.role === 'user' ? 'justify-end' : 'justify-start')}
          >
            <div
              className={cn('max-w-[85%] rounded-lg px-3 py-2 text-sm', msg.error && 'border')}
              style={{
                backgroundColor: msg.role === 'user' ? 'var(--brand-primary)' : 'var(--card-bg)',
                color: msg.role === 'user' ? 'var(--inverse-text)' : 'var(--primary-text)',
                borderColor: msg.error ? 'var(--status-error)' : 'var(--card-border)',
                border: msg.role === 'user' ? 'none' : '1px solid var(--card-border)',
              }}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>

              {/* Tool badges */}
              {msg.tools && msg.tools.length > 0 && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {msg.tools.map((tool, i) => (
                    <span
                      key={i}
                      className={cn(
                        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
                        TOOL_COLORS[tool.name] || 'bg-gray-100 text-gray-700'
                      )}
                    >
                      <Wrench className="h-3 w-3" />
                      {tool.name}
                    </span>
                  ))}
                  {msg.latency && (
                    <span className="inline-flex items-center gap-1 text-xs" style={{ color: 'var(--muted-text)' }}>
                      <Clock className="h-3 w-3" />
                      {msg.latency}s
                    </span>
                  )}
                </div>
              )}

              {/* Touched nodes */}
              {msg.graphNodes && msg.graphNodes.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {msg.graphNodes.slice(0, 8).map((tag) => (
                    <span
                      key={tag}
                      className="rounded px-1.5 py-0.5 text-xs font-mono"
                      style={{ backgroundColor: 'var(--badge-tool-bg)', color: 'var(--badge-tool-text)' }}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div
              className="rounded-lg px-3 py-2 text-sm"
              style={{ backgroundColor: 'var(--card-bg)', border: '1px solid var(--card-border)' }}
            >
              <Loader2 className="h-4 w-4 animate-spin" style={{ color: 'var(--muted-text)' }} />
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t px-4 py-3" style={{ borderColor: 'var(--pane-border)' }}>
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about the P&ID..."
            disabled={loading}
            className="flex-1 rounded-lg border px-3 py-2 text-sm outline-none transition disabled:opacity-50"
            style={{
              borderColor: 'var(--input-border)',
              backgroundColor: 'var(--pane-bg)',
              color: 'var(--primary-text)',
            }}
            onFocus={(e) => (e.target.style.borderColor = 'var(--input-border-focus)')}
            onBlur={(e) => (e.target.style.borderColor = 'var(--input-border)')}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-lg px-3 py-2 transition disabled:opacity-50"
            style={{ backgroundColor: 'var(--brand-primary)', color: 'var(--inverse-text)' }}
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
