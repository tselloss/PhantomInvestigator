# Runbook: Memory leak / OOM

## Symptoms
- process_resident_memory_bytes climbing steadily without plateau
- Latency degrades late (GC pressure), then restarts/OOM kills
- No error spike initially — this one is sneaky

## Diagnosis steps
1. process_resident_memory_bytes — steady climb since when?
2. Correlate the climb's start with deploys
3. Look for unbounded caches/lists in the diff

## Fix
Restart to stabilize, then fix eviction. Add memory growth alert.
