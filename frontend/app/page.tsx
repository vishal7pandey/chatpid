export default function Home() {
  return (
    <div className="flex h-screen w-screen items-center justify-center overflow-hidden">
      <div className="text-center">
        <h1 className="text-3xl font-bold" style={{ color: 'var(--primary-text)' }}>
          ChatP&amp;ID
        </h1>
        <p className="mt-2 text-muted">
          GraphRAG for Piping &amp; Instrumentation Diagrams
        </p>
      </div>
    </div>
  );
}
