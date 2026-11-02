"""
BrainyAi Intent Knowledge Base Evaluation & Benchmarking Suite
Evaluates 100+ natural language queries against ground truth labels.
Calculates:
- Primary Intent Accuracy
- Secondary Intent Recall
- Workflow Routing Accuracy
- Search Tool False Positive Rate
- Search Tool False Negative Rate
- Latency Distribution (Average, p50, p95, p99)
- Language breakdown (English, Hinglish, Hindi, Gujarati)
"""

import os
import sys
import time
import yaml
from typing import Dict, Any, List

# Configure UTF-8 encoding for Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure repository root is on Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ai_routing.intent import intent_resolver, UserIntentRequest
from ai_routing.workflow_router import workflow_router


def run_evaluation(dataset_path: str = None) -> Dict[str, Any]:
    if dataset_path is None:
        dataset_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "intent_examples.yaml")

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    examples: List[Dict[str, Any]] = data.get("examples", [])
    total_count = len(examples)

    correct_primary = 0
    correct_workflow = 0
    secondary_matches = 0
    secondary_expected_total = 0

    tool_false_positives = 0
    tool_false_negatives = 0
    tool_search_checks = 0

    latencies_ms = []
    by_language: Dict[str, Dict[str, int]] = {}

    mismatches = []

    # Warmup
    intent_resolver.resolve(UserIntentRequest(query="Warmup"))

    for item in examples:
        query = item.get("query", "")
        exp_primary = item.get("expected_primary_intent")
        exp_secondaries = item.get("expected_secondary_intents", [])
        exp_workflow = item.get("expected_workflow")
        exp_search = item.get("expected_search", False)
        lang = item.get("language", "en")
        has_doc = item.get("document_present", False)

        doc_ctx = {"doc_id": "test-doc-1", "pdf_text": "Sample text..."} if has_doc else None

        messages = None
        if item.get("context_required"):
            lower_q = query.lower()
            if "optimize" in lower_q:
                messages = [
                    {"role": "user", "content": "Write Python function"},
                    {"role": "assistant", "content": "def func(): pass"}
                ]
            elif "result" in lower_q:
                messages = [
                    {"role": "user", "content": "Find latest AI coding benchmarks"},
                    {"role": "assistant", "content": "LIVE WEB RESEARCH FINDINGS:\n[1] Benchmark A (https://a.com)\n[2] Benchmark B (https://b.com)"}
                ]
            else:
                messages = [
                    {"role": "user", "content": "Explain neural networks"},
                    {"role": "assistant", "content": "Neural networks are computational models..."}
                ]

        req = UserIntentRequest(
            query=query,
            messages=messages,
            document_context=doc_ctx
        )

        t0 = time.perf_counter()
        res = intent_resolver.resolve(req)
        decision = workflow_router.route(
            content=query,
            messages=messages,
            document_context=doc_ctx
        )
        t1 = time.perf_counter()
        dur_ms = (t1 - t0) * 1000.0
        latencies_ms.append(dur_ms)

        # Track per-language counts
        lang_stats = by_language.setdefault(lang, {"total": 0, "correct_primary": 0, "correct_workflow": 0})
        lang_stats["total"] += 1

        # Check primary intent
        primary_ok = (res.primary_intent == exp_primary)
        if primary_ok:
            correct_primary += 1
            lang_stats["correct_primary"] += 1

        # Check workflow
        workflow_ok = (decision.workflow == exp_workflow)
        if workflow_ok:
            correct_workflow += 1
            lang_stats["correct_workflow"] += 1

        # Check secondary intents
        if exp_secondaries:
            secondary_expected_total += len(exp_secondaries)
            for s in exp_secondaries:
                if s in res.secondary_intents:
                    secondary_matches += 1

        # Check search tool invocation
        tool_search_checks += 1
        if not exp_search and decision.search_required:
            tool_false_positives += 1
        elif exp_search and not decision.search_required:
            tool_false_negatives += 1

        if not primary_ok or not workflow_ok:
            mismatches.append({
                "query": query,
                "expected_primary": exp_primary,
                "actual_primary": res.primary_intent,
                "expected_workflow": exp_workflow,
                "actual_workflow": decision.workflow,
                "confidence": res.confidence
            })

    latencies_sorted = sorted(latencies_ms)
    p50 = latencies_sorted[int(0.50 * len(latencies_sorted))]
    p95 = latencies_sorted[int(0.95 * len(latencies_sorted))]
    p99 = latencies_sorted[int(0.99 * len(latencies_sorted))]
    avg_latency = sum(latencies_ms) / len(latencies_ms)

    primary_acc = (correct_primary / total_count) * 100.0
    workflow_acc = (correct_workflow / total_count) * 100.0
    secondary_recall = (secondary_matches / secondary_expected_total * 100.0) if secondary_expected_total > 0 else 100.0
    fp_rate = (tool_false_positives / tool_search_checks) * 100.0
    fn_rate = (tool_false_negatives / tool_search_checks) * 100.0

    report = {
        "total_queries": total_count,
        "primary_intent_accuracy": round(primary_acc, 2),
        "workflow_routing_accuracy": round(workflow_acc, 2),
        "secondary_intent_recall": round(secondary_recall, 2),
        "search_tool_false_positive_rate": round(fp_rate, 2),
        "search_tool_false_negative_rate": round(fn_rate, 2),
        "avg_latency_ms": round(avg_latency, 3),
        "p50_latency_ms": round(p50, 3),
        "p95_latency_ms": round(p95, 3),
        "p99_latency_ms": round(p99, 3),
        "by_language": by_language,
        "mismatches_count": len(mismatches),
        "mismatches": mismatches
    }

    return report


if __name__ == "__main__":
    report = run_evaluation()
    print("=" * 70)
    print("BRAINY INTENT UNDERSTANDING & AI ROUTING EVALUATION REPORT")
    print("=" * 70)
    print(f"Total Evaluated Queries:         {report['total_queries']}")
    print(f"Primary Intent Accuracy:         {report['primary_intent_accuracy']}%")
    print(f"Workflow Routing Accuracy:       {report['workflow_routing_accuracy']}%")
    print(f"Secondary Intent Recall:         {report['secondary_intent_recall']}%")
    print(f"Search False Positive Rate:      {report['search_tool_false_positive_rate']}%")
    print(f"Search False Negative Rate:      {report['search_tool_false_negative_rate']}%")
    print(f"Latency (Avg / p50 / p95 / p99): {report['avg_latency_ms']}ms / {report['p50_latency_ms']}ms / {report['p95_latency_ms']}ms / {report['p99_latency_ms']}ms")
    print("-" * 70)
    print("LANGUAGE BREAKDOWN:")
    for lang, st in report["by_language"].items():
        p_acc = (st['correct_primary'] / st['total']) * 100.0
        w_acc = (st['correct_workflow'] / st['total']) * 100.0
        print(f"  [{lang.upper()}]: Total: {st['total']} | Primary Acc: {p_acc:.1f}% | Workflow Acc: {w_acc:.1f}%")
    print("=" * 70)
    if report["mismatches"]:
        print(f"MISMATCHES ({len(report['mismatches'])}):")
        for m in report["mismatches"][:10]:
            print(f"  Query: {m['query']}")
            print(f"    Expected: Intent={m['expected_primary']}, WF={m['expected_workflow']}")
            print(f"    Actual:   Intent={m['actual_primary']}, WF={m['actual_workflow']}")
    print("=" * 70)
