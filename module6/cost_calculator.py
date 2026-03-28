#!/usr/bin/env python3
"""Cost Calculator — Module 6.

Reads eval harness JSON output and calculates actual dollar costs per scenario,
per configuration, with tool definition overhead analysis.

Usage:
    python cost_calculator.py comparison_data.json
    python cost_calculator.py /path/to/eval_results.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ── Pricing per 1M tokens ────────────────────────────────────────────────────

PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6":   {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-6": {"input":  3.00, "output": 15.00},
    "claude-haiku-4-5":  {"input":  0.80, "output":  4.00},
    "gpt-4.1":           {"input":  2.00, "output":  8.00},
    "gpt-4.1-mini":      {"input":  0.40, "output":  1.60},
    "qwen-2.5-1.5b":     {"input":  0.00, "output":  0.00},
}

# Map config prefixes to pricing keys
CONFIG_MODEL_MAP: dict[str, str] = {
    "opus":  "claude-opus-4-6",
    "qwen":  "qwen-2.5-1.5b",
}


def cost_for_tokens(model: str, input_tok: int, output_tok: int) -> float:
    p = PRICING.get(model, {"input": 3.0, "output": 15.0})
    return (input_tok * p["input"] + output_tok * p["output"]) / 1_000_000


def infer_model(config_key: str) -> str:
    for prefix, model in CONFIG_MODEL_MAP.items():
        if prefix in config_key.lower():
            return model
    return "claude-sonnet-4-6"


def infer_io_tokens(case: dict) -> tuple[int, int]:
    """Extract or estimate input/output tokens from a case."""
    m = case.get("metrics", {})
    input_tok = m.get("input_tokens", 0)
    output_tok = m.get("output_tokens", 0)
    if input_tok and output_tok:
        return input_tok, output_tok
    # Fallback: estimate 70/30 split
    total = m.get("total_tokens", 0)
    return int(total * 0.7), int(total * 0.3)


# ── Display helpers ──────────────────────────────────────────────────────────

SEP = "=" * 78
THIN = "-" * 78


def print_header(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def print_case_table(config: str, model: str, cases: list[dict]) -> None:
    print(f"\n  {'Scenario':<28} {'Turns':>5} {'In Tok':>8} {'Out Tok':>8} {'Cost':>8}")
    print(f"  {THIN[:28]} {THIN[:5]} {THIN[:8]} {THIN[:8]} {THIN[:8]}")

    total_cost = 0.0
    total_in = 0
    total_out = 0

    for c in cases:
        eid = c.get("eval_id", "?")
        m = c.get("metrics", {})
        turns = m.get("turn_count", 0)
        in_tok, out_tok = infer_io_tokens(c)
        cost = cost_for_tokens(model, in_tok, out_tok)
        total_cost += cost
        total_in += in_tok
        total_out += out_tok

        label = eid[:28]
        print(f"  {label:<28} {turns:>5} {in_tok:>8,} {out_tok:>8,} ${cost:>6.4f}")

    print(f"  {THIN[:28]} {THIN[:5]} {THIN[:8]} {THIN[:8]} {THIN[:8]}")
    print(f"  {'TOTAL':<28} {'':>5} {total_in:>8,} {total_out:>8,} ${total_cost:>6.4f}")
    avg = total_cost / max(len(cases), 1)
    print(f"  {'AVG PER CASE':<28} {'':>5} {'':>8} {'':>8} ${avg:>6.4f}")


def print_config_comparison(data: dict) -> None:
    print_header("Configuration Cost Comparison")
    print(f"\n  {'Config':<25} {'Cases':>5} {'Avg Tok':>9} {'Avg Cost':>10} {'Total':>10}")
    print(f"  {THIN[:25]} {THIN[:5]} {THIN[:9]} {THIN[:10]} {THIN[:10]}")

    for config_key, config_data in data.items():
        if config_key.startswith("_"):
            continue
        model = infer_model(config_key)
        cases = config_data.get("cases", [])
        if not cases:
            continue

        total_cost = 0.0
        total_tok = 0
        for c in cases:
            in_tok, out_tok = infer_io_tokens(c)
            total_cost += cost_for_tokens(model, in_tok, out_tok)
            total_tok += in_tok + out_tok

        n = len(cases)
        avg_tok = total_tok // n
        avg_cost = total_cost / n

        print(f"  {config_key:<25} {n:>5} {avg_tok:>8,} ${avg_cost:>9.4f} ${total_cost:>9.4f}")


def print_tool_overhead(data: dict) -> None:
    desc_cmp = data.get("_tool_description_comparison")
    dyn_cmp = data.get("_dynamic_toolset_comparison")

    if not desc_cmp and not dyn_cmp:
        return

    print_header("Tool Definition Overhead Analysis")

    if desc_cmp:
        v = desc_cmp["verbose_descriptions"]["total_tokens"]
        l = desc_cmp["lean_descriptions"]["total_tokens"]
        save = desc_cmp["savings_per_message"]
        save5 = desc_cmp["savings_over_5_turns"]

        print(f"\n  Tool Description Impact (6 tools):")
        print(f"    Verbose descriptions:  {v:>6,} tokens/message")
        print(f"    Lean descriptions:     {l:>6,} tokens/message")
        print(f"    Savings per message:   {save:>6,} tokens ({save/v*100:.0f}% reduction)")
        print(f"    Over 5-turn convo:     {save5:>6,} tokens saved")

        for model_name, pricing in [("claude-sonnet-4-6", PRICING["claude-sonnet-4-6"]),
                                     ("claude-opus-4-6", PRICING["claude-opus-4-6"])]:
            dollar = save5 * pricing["input"] / 1_000_000
            print(f"    = ${dollar:.4f} saved per conversation ({model_name})")

    if dyn_cmp:
        full = dyn_cmp["over_5_turns_full"]
        dyn = dyn_cmp["over_5_turns_dynamic"]
        pct = dyn_cmp["reduction_percent"]

        print(f"\n  Dynamic Tool Set Impact:")
        print(f"    Full set (10 tools):   {full:>6,} tokens over 5 turns")
        print(f"    Dynamic (3 tools):     {dyn:>6,} tokens over 5 turns")
        print(f"    Reduction:             {pct}%")

        for model_name, pricing in [("claude-sonnet-4-6", PRICING["claude-sonnet-4-6"]),
                                     ("claude-opus-4-6", PRICING["claude-opus-4-6"])]:
            dollar = (full - dyn) * pricing["input"] / 1_000_000
            print(f"    = ${dollar:.4f} saved per conversation ({model_name})")


def print_logical_vs_meta(data: dict) -> None:
    """Compare logical vs meta tools for the same model."""
    pairs = [("opus+logical", "opus+meta"), ("qwen+logical", "qwen+meta")]

    found_any = False
    for log_key, meta_key in pairs:
        if log_key not in data or meta_key not in data:
            continue
        found_any = True

        if not found_any:
            return

    print_header("Logical vs Meta-Tools: Same Task, Different Cost")

    for log_key, meta_key in pairs:
        if log_key not in data or meta_key not in data:
            continue

        model = infer_model(log_key)
        model_label = log_key.split("+")[0].capitalize()
        log_cases = {c["eval_id"]: c for c in data[log_key].get("cases", [])}
        meta_cases = {c["eval_id"]: c for c in data[meta_key].get("cases", [])}

        # Only compare positive cases
        shared = [eid for eid in log_cases if eid in meta_cases and not eid.startswith("neg_")]

        print(f"\n  Model: {model_label} ({model})")
        print(f"  {'Scenario':<25} {'Log Tok':>8} {'Log $':>8} {'Meta Tok':>9} {'Meta $':>8} {'Ratio':>6}")
        print(f"  {THIN[:25]} {THIN[:8]} {THIN[:8]} {THIN[:9]} {THIN[:8]} {THIN[:6]}")

        for eid in shared:
            lc = log_cases[eid]
            mc = meta_cases[eid]
            l_in, l_out = infer_io_tokens(lc)
            m_in, m_out = infer_io_tokens(mc)
            l_cost = cost_for_tokens(model, l_in, l_out)
            m_cost = cost_for_tokens(model, m_in, m_out)
            l_total = l_in + l_out
            m_total = m_in + m_out
            ratio = m_total / max(l_total, 1)

            print(f"  {eid[:25]:<25} {l_total:>8,} ${l_cost:>6.4f} {m_total:>9,} ${m_cost:>6.4f} {ratio:>5.1f}x")


def print_pricing_reference() -> None:
    print_header("Pricing Reference (per 1M tokens)")
    print(f"\n  {'Model':<25} {'Input':>10} {'Output':>10}")
    print(f"  {THIN[:25]} {THIN[:10]} {THIN[:10]}")
    for model, prices in PRICING.items():
        print(f"  {model:<25} ${prices['input']:>8.2f} ${prices['output']:>8.2f}")
    print(f"\n  Prices as of March 2026. Check provider docs for current rates.")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <eval_results.json>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Error: {path} not found")
        sys.exit(1)

    with open(path) as f:
        data = json.load(f)

    print_pricing_reference()

    # Per-config detail tables
    for config_key, config_data in data.items():
        if config_key.startswith("_"):
            continue
        model = infer_model(config_key)
        cases = config_data.get("cases", [])
        if not cases:
            continue
        print_header(f"Detail: {config_key}  (model: {model})")
        print_case_table(config_key, model, cases)

    print_config_comparison(data)
    print_logical_vs_meta(data)
    print_tool_overhead(data)

    print(f"\n{SEP}")
    print("  Done.")
    print(SEP)


if __name__ == "__main__":
    main()
