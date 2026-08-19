'use client';

import { useEffect, useState } from 'react';
import { listPidFiles, getPidSvgUrl, type PidFile } from '@/lib/api';

interface PidViewerProps {
  onClose?: () => void;
}

export function PidViewer({ onClose }: PidViewerProps) {
  const [files, setFiles] = useState<PidFile[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [svgUrl, setSvgUrl] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [zoom, setZoom] = useState<number>(100);

  useEffect(() => {
    listPidFiles()
      .then((f) => {
        setFiles(f);
        if (f.length > 0 && !selected) {
          setSelected(f[0].filename);
        }
      })
      .catch((e) => setError(`Failed to load file list: ${e}`));
  }, []);

  useEffect(() => {
    if (selected) {
      setError('');
      setLoading(true);
      setSvgUrl(getPidSvgUrl(selected));
    }
  }, [selected]);

  return (
    <div className="flex flex-col h-full bg-white dark:bg-zinc-900 border rounded-lg overflow-hidden" style={{ borderColor: 'var(--pane-border)' }}>
      {/* Header with file selector & zoom controls */}
      <div className="flex items-center gap-3 px-4 py-2 border-b bg-zinc-50 dark:bg-zinc-800" style={{ borderColor: 'var(--pane-border)' }}>
        <span className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">P&amp;ID Diagram:</span>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="text-sm border rounded px-2.5 py-1 bg-white dark:bg-zinc-700 dark:text-zinc-200 outline-none focus:ring-1 focus:ring-blue-500"
        >
          {files.map((f, idx) => (
            <option key={`${f.directory}/${f.filename}-${idx}`} value={f.filename}>
              {f.filename}
            </option>
          ))}
        </select>

        {/* Zoom controls */}
        <div className="flex items-center gap-1.5 ml-auto text-xs">
          <button
            onClick={() => setZoom((z) => Math.max(30, z - 20))}
            className="px-2 py-1 rounded border bg-white dark:bg-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-600 transition-colors"
            title="Zoom Out"
          >
            -
          </button>
          <span className="w-12 text-center text-zinc-600 dark:text-zinc-400 font-mono">{zoom}%</span>
          <button
            onClick={() => setZoom((z) => Math.min(300, z + 20))}
            className="px-2 py-1 rounded border bg-white dark:bg-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-600 transition-colors"
            title="Zoom In"
          >
            +
          </button>
          <button
            onClick={() => setZoom(100)}
            className="px-2 py-1 rounded border bg-white dark:bg-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-600 transition-colors ml-1"
            title="Reset Zoom"
          >
            Reset
          </button>
          {svgUrl && (
            <a
              href={svgUrl}
              download={`${selected.replace(/\.xml$/i, '')}.svg`}
              className="px-2.5 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors ml-2"
              title="Download SVG file"
            >
              Export SVG
            </a>
          )}
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="text-sm text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 ml-2"
          >
            ✕
          </button>
        )}
      </div>

      {/* SVG viewer area */}
      <div className="flex-1 overflow-auto p-4 bg-zinc-100 dark:bg-zinc-950 flex items-center justify-center">
        {error && (
          <div className="text-sm text-red-500 bg-red-50 dark:bg-red-950/50 p-4 rounded border border-red-200 dark:border-red-800">
            {error}
          </div>
        )}
        {loading && !error && (
          <div className="absolute text-sm text-zinc-500 bg-white/80 dark:bg-zinc-900/80 px-3 py-1.5 rounded-full shadow-sm">
            Rendering P&amp;ID diagram...
          </div>
        )}
        {svgUrl && (
          <div style={{ transform: `scale(${zoom / 100})`, transformOrigin: 'center center', transition: 'transform 0.15s ease-out' }}>
            <img
              src={svgUrl}
              alt={`P&ID: ${selected}`}
              className="max-w-none shadow-md rounded bg-white"
              onLoad={() => setLoading(false)}
              onError={() => {
                setLoading(false);
                setError('Failed to render SVG diagram for ' + selected);
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
