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
      setSvgUrl(getPidSvgUrl(selected));
    }
  }, [selected]);

  return (
    <div className="flex flex-col h-full bg-white dark:bg-zinc-900 border rounded-lg overflow-hidden">
      {/* Header with file selector */}
      <div className="flex items-center gap-3 px-4 py-2 border-b bg-zinc-50 dark:bg-zinc-800">
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">P&ID Diagram</span>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="text-sm border rounded px-2 py-1 bg-white dark:bg-zinc-700 dark:text-zinc-200"
        >
          {files.map((f, idx) => (
            <option key={`${f.directory}/${f.filename}-${idx}`} value={f.filename}>
              {f.filename}
            </option>
          ))}
        </select>
        {onClose && (
          <button
            onClick={onClose}
            className="ml-auto text-sm text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
          >
            ✕
          </button>
        )}
      </div>

      {/* SVG viewer */}
      <div className="flex-1 overflow-auto p-4">
        {error && (
          <div className="text-sm text-red-500">{error}</div>
        )}
        {svgUrl && (
          <img
            src={svgUrl}
            alt={`P&ID: ${selected}`}
            className="max-w-full h-auto"
            onLoad={() => setLoading(false)}
            onLoadStart={() => setLoading(true)}
          />
        )}
        {loading && (
          <div className="text-sm text-zinc-500">Rendering P&ID diagram...</div>
        )}
      </div>
    </div>
  );
}
