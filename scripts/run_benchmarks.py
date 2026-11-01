#!/usr/bin/env python3
"""
BrainyAi - Empirical Benchmark & Performance Measurement Suite
Generates verifiable, reproducible performance metrics without fabricating data.
"""

import os
import sys
import time
import json
import statistics
import urllib.request
import ssl
from datetime import datetime, timezone

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def benchmark_local_maths():
    """Measures deterministic local mathematics engine latency across 100 runs."""
    from ai_routing.maths import solve_locally
    queries = [
        "solve 2*x + 5 = 15",
        "derivative of x^3 + 4*x^2 - 7*x + 2",
        "limit (sin(x))/x as x -> 0",
        "15 * (4 + 6) / 2",
        "molar mass of H2SO4"
    ]
    latencies_ms = []
    # Warm up
    for q in queries:
        solve_locally(q)
        
    for _ in range(20):
        for q in queries:
            t0 = time.perf_counter()
            res = solve_locally(q)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000)
            
    latencies_ms.sort()
    return {
        "operations_tested": len(latencies_ms),
        "min_ms": round(min(latencies_ms), 3),
        "max_ms": round(max(latencies_ms), 3),
        "mean_ms": round(statistics.mean(latencies_ms), 3),
        "p50_ms": round(statistics.median(latencies_ms), 3),
        "p95_ms": round(latencies_ms[int(len(latencies_ms) * 0.95)], 3)
    }

def benchmark_code_sandbox():
    """Measures isolated subprocess execution latency across 5 runs."""
    from ai_routing.code_sandbox import execute_code_safely
    latencies_ms = []
    code = "import math\nprint(math.sqrt(144) * 10)"
    # Warm up
    execute_code_safely(code)
    
    for _ in range(5):
        t0 = time.perf_counter()
        res = execute_code_safely(code)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000)
        
    latencies_ms.sort()
    return {
        "runs": len(latencies_ms),
        "min_ms": round(min(latencies_ms), 2),
        "max_ms": round(max(latencies_ms), 2),
        "mean_ms": round(statistics.mean(latencies_ms), 2),
        "p50_ms": round(statistics.median(latencies_ms), 2)
    }

def benchmark_static_assets():
    """Audits the actual out/ static export directory from Next.js build."""
    out_dir = os.path.join(PROJECT_ROOT, "out")
    if not os.path.exists(out_dir):
        return {"status": "out_directory_not_found"}
        
    file_count = 0
    total_bytes = 0
    by_extension = {}
    
    for root, dirs, files in os.walk(out_dir):
        for f in files:
            file_count += 1
            ext = os.path.splitext(f)[1].lower() or "no_ext"
            p = os.path.join(root, f)
            sz = os.path.getsize(p)
            total_bytes += sz
            by_extension[ext] = by_extension.get(ext, [0, 0])
            by_extension[ext][0] += 1
            by_extension[ext][1] += sz
            
    return {
        "total_files": file_count,
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "by_extension": {
            k: {"count": v[0], "size_kb": round(v[1] / 1024, 2)}
            for k, v in sorted(by_extension.items())
        }
    }

def benchmark_cloudflare_edge():
    """Measures live HTTP latency to Cloudflare Workers static deployment."""
    url = "https://brainyai.cenai.workers.dev/"
    ctx = ssl.create_default_context()
    latencies_ms = []
    cf_rays = []
    
    for i in range(5):
        req = urllib.request.Request(url, headers={"User-Agent": "BrainyBenchmark/1.0"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                _ = resp.read()
                t1 = time.perf_counter()
                latencies_ms.append((t1 - t0) * 1000)
                cf_ray = resp.headers.get("CF-RAY", "")
                if cf_ray:
                    cf_rays.append(cf_ray.split("-")[-1] if "-" in cf_ray else cf_ray)
        except Exception as exc:
            pass
            
    if not latencies_ms:
        return {"status": "unreachable"}
        
    latencies_ms.sort()
    return {
        "samples": len(latencies_ms),
        "min_ms": round(min(latencies_ms), 1),
        "max_ms": round(max(latencies_ms), 1),
        "mean_ms": round(statistics.mean(latencies_ms), 1),
        "p50_ms": round(statistics.median(latencies_ms), 1),
        "edge_pop_colos": list(set(cf_rays))
    }

def main():
    print("=" * 80)
    print(f"BRAINY PRODUCTION PERFORMANCE BENCHMARK (RUN AT {datetime.now(timezone.utc).isoformat()})")
    print("=" * 80)
    
    print("\n1. Measuring Local Mathematics Engine...")
    math_results = benchmark_local_maths()
    print(f"   Evaluations: {math_results['operations_tested']}")
    print(f"   P50 Latency: {math_results['p50_ms']} ms | P95 Latency: {math_results['p95_ms']} ms | Mean: {math_results['mean_ms']} ms")
    
    print("\n2. Measuring Isolated Code Sandbox Helper...")
    sandbox_results = benchmark_code_sandbox()
    print(f"   Subprocess Runs: {sandbox_results['runs']}")
    print(f"   P50 Latency: {sandbox_results['p50_ms']} ms | Range: {sandbox_results['min_ms']} - {sandbox_results['max_ms']} ms")
    
    print("\n3. Measuring Next.js Static Export Distribution (out/)...")
    static_results = benchmark_static_assets()
    print(f"   Total Assets: {static_results['total_files']} files ({static_results['total_mb']} MB)")
    for ext, info in static_results.get("by_extension", {}).items():
        print(f"     {ext:<8s}: {info['count']:3d} files ({info['size_kb']:8.1f} KB)")
        
    print("\n4. Measuring Live Cloudflare Workers Edge Response Latency...")
    edge_results = benchmark_cloudflare_edge()
    print(f"   Samples: {edge_results['samples']}")
    print(f"   P50 Latency: {edge_results['p50_ms']} ms | Range: {edge_results['min_ms']} - {edge_results['max_ms']} ms")
    print(f"   Edge Colos: {edge_results.get('edge_pop_colos')}")
    
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "local_maths": math_results,
        "code_sandbox": sandbox_results,
        "static_assets": static_results,
        "cloudflare_edge": edge_results
    }
    
    out_json = os.path.join(PROJECT_ROOT, "benchmark_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved raw sanitized benchmark metrics to: {out_json}")
    print("=" * 80)

if __name__ == "__main__":
    main()
