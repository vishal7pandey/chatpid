"""Calculate remaining work cost estimates for OpenAI models."""
from chatpid.context_rag import context_rag
from chatpid.ingest import get_driver
from chatpid.benchmark import BENCHMARK_QUESTIONS

driver = get_driver()

print("=== Graph sizes ===")
for level in ["complete", "process", "conceptual"]:
    with driver.session() as s:
        n = s.run("MATCH (n {level: $l}) RETURN count(n) AS c", l=level).single()["c"]
        r = s.run("MATCH ()-[e {level: $l}]->() RETURN count(e) AS c", l=level).single()["c"]
        ctx = context_rag(driver, level=level, mode="graph")
        print(f"  {level}: {n} nodes, {r} edges, context={len(ctx)} chars (~{len(ctx)//4} tokens)")

print(f"\nBenchmark questions: {len(BENCHMARK_QUESTIONS)}")

# === Cost estimates ===
# OpenAI pricing per 1M tokens
models = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o":      {"input": 2.50, "output": 10.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1":     {"input": 2.00, "output": 8.00},
}

def cost(model, input_tokens, output_tokens):
    p = models[model]
    return (input_tokens / 1_000_000 * p["input"]) + (output_tokens / 1_000_000 * p["output"])

print("\n=== Remaining work items ===")
work = []

# 1. Level comparison (direct benchmark, 3 levels x 19 Qs = 57 Qs)
#    ~2.7K input + ~0.8K output per Q
work.append({
    "name": "SCRUM-360: Level comparison (57 Qs direct)",
    "calls": 57,
    "input_per_call": 2700,
    "output_per_call": 800,
})

# 2. Semantic enrichment (all 3 levels, ~75 nodes x 2 calls = 150 calls)
#    Global: ~2.5K input (node + flowsheet repr) + ~300 output
#    Local: ~1.5K input (node + neighbors) + ~300 output
work.append({
    "name": "SCRUM-361: Semantic enrichment (150 calls)",
    "calls": 150,
    "input_per_call": 2000,
    "output_per_call": 300,
})

# 3. VectorRAG testing (20 queries to eyeball top-k)
work.append({
    "name": "SCRUM-362: VectorRAG top-k testing (20 Qs)",
    "calls": 20,
    "input_per_call": 2700,
    "output_per_call": 800,
})

# 4. Full agent benchmark with all 4 tools (19 Qs, ReAct agent overhead)
#    Agent uses ~10K input + ~2K output per Q (tool calls + reasoning)
work.append({
    "name": "Full agent benchmark, 4 tools (19 Qs)",
    "calls": 19,
    "input_per_call": 10000,
    "output_per_call": 2000,
})

# 5. CypherRAG end-to-end (19 Qs x 2 LLM calls: generate + answer)
work.append({
    "name": "CypherRAG end-to-end (38 calls)",
    "calls": 38,
    "input_per_call": 3500,
    "output_per_call": 500,
})

# 6. PathRAG end-to-end with LLM evaluation (19 Qs)
#    PathRAG traversal + LLM evaluate at each hop: ~5 calls/Q x 19 = 95 calls
work.append({
    "name": "PathRAG with LLM eval (95 calls)",
    "calls": 95,
    "input_per_call": 3000,
    "output_per_call": 200,
})

# 7. Debugging/retries buffer (run everything 2x more)
work.append({
    "name": "Debug/retry buffer (2x re-runs)",
    "calls": 0,  # handled by multiplier below
    "input_per_call": 0,
    "output_per_call": 0,
})

print("\n--- Per-model estimates ---")
for model_name in models:
    subtotal = 0
    print(f"\n  {model_name}:")
    for item in work:
        c = item["calls"] * cost(model_name, item["input_per_call"], item["output_per_call"])
        subtotal += c
        if item["calls"] > 0:
            print(f"    {item['name']}: ${c:.4f}")
    # Add 3x buffer for re-runs, debugging, trying different prompts
    with_buffer = subtotal * 3
    print(f"    Subtotal: ${subtotal:.4f}")
    print(f"    With 3x debug buffer: ${with_buffer:.2f}")

# Recommendation
print("\n=== RECOMMENDATION ===")
print("gpt-4o-mini:  $5  (covers everything with comfortable buffer)")
print("gpt-4o:       $20 (covers everything with comfortable buffer)")
print("gpt-4.1-mini: $10 (covers everything with comfortable buffer)")
print()
print("Best value: gpt-4o-mini at $5. It's the closest to the paper's GPT-5-mini")
print("and more than sufficient for this small P&ID graph.")

driver.close()
