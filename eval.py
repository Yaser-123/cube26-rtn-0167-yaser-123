"""Evaluate the Returns Manager against a held-out, two-labeller set.

Labels live in eval/labels.csv, one row per unit:
  unit_id, org_id, ordered_sku, parts_list, photo_refs (;-separated paths),
  identity_a, completeness_a, condition_a, disposition_a   <- labeller A
  identity_b, completeness_b, condition_b, disposition_b   <- labeller B (independent)
Check labels are PASS / FAIL / UNCERTAIN; dispositions are restock / refurbish /
liquidate / dispose / pending_review.

Gold for a check = the label both labellers agree on. Units where they disagree are
reported as human-ambiguous and excluded from accuracy (but still count toward the
agent's UNCERTAIN rate). If column B is empty, A alone is gold and agreement is n/a.

Usage:
  python eval.py --estimate     # predicted cost, no API calls
  python eval.py                # run it, writes eval/results.json and eval/eval-report.md
  python eval.py --limit 5      # first 5 units only
"""
import argparse
import csv
import json
import statistics
from pathlib import Path
from src.models import ReturnCaptureRequest
from src import agent as agent_module

LABELS = Path("eval/labels.csv")
OUT_DIR = Path("eval")
CHECKS = ("identity", "completeness", "condition")
# Rough per-image input tokens at 1024px, plus prompt and output, for --estimate
EST_TOKENS_PER_IMAGE = 1300
EST_PROMPT_TOKENS = 900
EST_OUTPUT_TOKENS = 700


def load_units(limit=None):
    with LABELS.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["unit_id"].strip()]
    return rows[:limit] if limit else rows


def gold(row, key):
    a = row.get(f"{key}_a", "").strip()
    b = row.get(f"{key}_b", "").strip()
    if not b:
        return a or None
    return a if a == b else None  # None = labellers disagree


def cohen_kappa(pairs):
    pairs = [(a, b) for a, b in pairs if a and b]
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    labels = {x for p in pairs for x in p}
    expected = sum((sum(a == l for a, _ in pairs) / n) * (sum(b == l for _, b in pairs) / n) for l in labels)
    return 1.0 if expected == 1 else round((observed - expected) / (1 - expected), 3)


def estimate(units):
    price_in, price_out = agent_module.PRICING.get(agent_module.MODEL, (0, 0))
    images = sum(min(len(u["photo_refs"].split(";")), agent_module.MAX_IMAGES) for u in units)
    tokens_in = images * EST_TOKENS_PER_IMAGE + len(units) * EST_PROMPT_TOKENS
    tokens_out = len(units) * EST_OUTPUT_TOKENS
    cost = (tokens_in * price_in + tokens_out * price_out) / 1e6
    print(f"{len(units)} units, {images} images on {agent_module.MODEL} (effort {agent_module.EFFORT})")
    print(f"Estimated: ~{tokens_in:,} input + ~{tokens_out:,} output tokens = ~${cost:.2f} "
          f"(re-runs of unchanged units are served from cache for $0)")


def run(units):
    agent = agent_module.ReturnsAgent()
    rows = []
    for u in units:
        req = ReturnCaptureRequest(
            unit_id=u["unit_id"], organization_id=u.get("org_id") or "org_demo_alpha",
            operator_label="op_eval", order_id="ORD-EVAL", ordered_sku=u["ordered_sku"],
            parts_list=u["parts_list"], photo_refs=[p.strip() for p in u["photo_refs"].split(";") if p.strip()],
        )
        record, usage = agent.analyze(req)
        verdicts = {c.check_key: c.verdict for c in record.checks}
        rows.append({"unit": u, "record": record.model_dump(), "verdicts": verdicts,
                     "disposition": record.outcome, "usage": usage})
        tag = "cache" if usage["cached"] else f"${usage['cost_usd']:.4f}"
        print(f"{u['unit_id']}: {record.outcome:15} {verdicts}  [{usage['latency_ms']} ms, {tag}]")
    return rows


def score(rows):
    report = {"units": len(rows), "checks": {}, "agreement": {}}
    for key in CHECKS + ("disposition",):
        pairs = [(r["unit"].get(f"{key}_a", "").strip(), r["unit"].get(f"{key}_b", "").strip()) for r in rows]
        report["agreement"][key] = cohen_kappa(pairs)

    for key in CHECKS:
        m = {"gold_n": 0, "human_ambiguous": 0, "correct": 0, "FP": 0, "FN": 0,
             "agent_uncertain": 0, "uncertain_when_gold_decided": 0, "errors": []}
        for r in rows:
            g = gold(r["unit"], key)
            pred = r["verdicts"][key]
            if pred == "UNCERTAIN":
                m["agent_uncertain"] += 1
            if g is None:
                m["human_ambiguous"] += 1
                continue
            m["gold_n"] += 1
            if pred == g:
                m["correct"] += 1
            elif pred == "UNCERTAIN":
                m["uncertain_when_gold_decided"] += 1
            else:
                # FP = agent passed something humans failed (the costly direction); FN = the reverse
                if pred == "PASS" and g == "FAIL":
                    m["FP"] += 1
                elif pred == "FAIL" and g == "PASS":
                    m["FN"] += 1
                m["errors"].append({"unit": r["unit"]["unit_id"], "gold": g, "agent": pred})
        decided = m["gold_n"] - m["uncertain_when_gold_decided"]
        m["accuracy"] = round(m["correct"] / m["gold_n"], 3) if m["gold_n"] else None
        m["accuracy_when_decided"] = round((m["correct"]) / decided, 3) if decided else None
        m["uncertain_rate"] = round(m["agent_uncertain"] / len(rows), 3) if rows else None
        report["checks"][key] = m

    disp = {"gold_n": 0, "correct": 0, "confusions": []}
    for r in rows:
        g = gold(r["unit"], "disposition")
        if g is None:
            continue
        disp["gold_n"] += 1
        if r["disposition"] == g:
            disp["correct"] += 1
        else:
            disp["confusions"].append({"unit": r["unit"]["unit_id"], "gold": g, "agent": r["disposition"]})
    disp["accuracy"] = round(disp["correct"] / disp["gold_n"], 3) if disp["gold_n"] else None
    disp["review_rate"] = round(sum(r["disposition"] == "pending_review" for r in rows) / len(rows), 3) if rows else None
    report["disposition"] = disp

    lat = sorted(r["usage"]["latency_ms"] for r in rows if not r["usage"]["cached"]) or [0]
    billed = [r["usage"] for r in rows if not r["usage"]["cached"]]
    report["cost_latency"] = {
        "model": agent_module.MODEL, "effort": agent_module.EFFORT,
        "billed_calls": len(billed), "cache_hits": len(rows) - len(billed),
        "total_cost_usd": round(sum(u["cost_usd"] for u in billed), 4),
        "cost_per_unit_usd": round(sum(u["cost_usd"] for u in billed) / len(billed), 4) if billed else None,
        "avg_input_tokens": round(statistics.mean(u["input_tokens"] for u in billed)) if billed else None,
        "avg_output_tokens": round(statistics.mean(u["output_tokens"] for u in billed)) if billed else None,
        "latency_p50_ms": lat[len(lat) // 2], "latency_p95_ms": lat[min(len(lat) - 1, int(len(lat) * 0.95))],
    }
    return report


def pct(x):
    return "n/a" if x is None else f"{x * 100:.1f}%"


def write_markdown(report, rows):
    cl = report["cost_latency"]
    lines = [
        "# Evaluation report: Returns Manager", "",
        f"Units: **{report['units']}** · model `{cl['model']}` (effort `{cl['effort']}`) · generated by `python eval.py`", "",
        "## Method", "",
        "Each unit was labelled independently by two people (columns `_a` / `_b` in `eval/labels.csv`).",
        "Gold for a check is the label both agree on; units where they disagree are counted as human-ambiguous",
        "and left out of accuracy. FP = agent said PASS where gold is FAIL; FN = agent said FAIL where gold is PASS.",
        "An agent UNCERTAIN on a unit with a decided gold label is neither correct nor an FP/FN; it is counted",
        "separately so it cannot inflate accuracy.", "",
        "## Human agreement (Cohen's kappa)", "",
        "| Check | kappa |", "|---|---|",
        *[f"| {k} | {v if v is not None else 'n/a (single labeller)'} |" for k, v in report["agreement"].items()], "",
        "## Per-check results", "",
        "| Check | Gold n | Accuracy | Accuracy when decided | FP | FN | Agent UNCERTAIN rate | UNCERTAIN on decided gold | Human-ambiguous |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for k, m in report["checks"].items():
        lines.append(f"| {k} | {m['gold_n']} | {pct(m['accuracy'])} | {pct(m['accuracy_when_decided'])} | {m['FP']} | {m['FN']} | "
                     f"{pct(m['uncertain_rate'])} | {m['uncertain_when_gold_decided']} | {m['human_ambiguous']} |")
    d = report["disposition"]
    lines += ["", "## Disposition", "",
              f"Accuracy: **{pct(d['accuracy'])}** on {d['gold_n']} units with agreed gold · pending_review rate: **{pct(d['review_rate'])}**", ""]
    if d["confusions"]:
        lines += ["| Unit | Gold | Agent |", "|---|---|---|", *[f"| {c['unit']} | {c['gold']} | {c['agent']} |" for c in d["confusions"]], ""]
    lines += ["## Cost and latency", "",
              f"- Billed model calls: {cl['billed_calls']} (cache hits: {cl['cache_hits']})",
              f"- Total cost: ${cl['total_cost_usd']} · per unit: ${cl['cost_per_unit_usd']}",
              f"- Avg tokens per call: {cl['avg_input_tokens']} in / {cl['avg_output_tokens']} out",
              f"- Latency p50 {cl['latency_p50_ms']} ms · p95 {cl['latency_p95_ms']} ms (uncached calls)", "",
              "## Every error", "",
              "| Unit | Check | Gold | Agent |", "|---|---|---|---|"]
    for k, m in report["checks"].items():
        lines += [f"| {e['unit']} | {k} | {e['gold']} | {e['agent']} |" for e in m["errors"]]
    lines += ["", "## Failure modes", "", "_Write up the patterns behind the errors above after reviewing them._", ""]
    (OUT_DIR / "eval-report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--estimate", action="store_true", help="print predicted cost and exit")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    units = load_units(args.limit)
    if args.estimate:
        estimate(units)
    else:
        rows = run(units)
        report = score(rows)
        OUT_DIR.mkdir(exist_ok=True)
        (OUT_DIR / "results.json").write_text(json.dumps({"report": report, "rows": rows}, indent=2, default=str), encoding="utf-8")
        write_markdown(report, rows)
        print(json.dumps({k: report[k] for k in ("checks", "disposition", "cost_latency")}, indent=2))
        print("\nWrote eval/results.json and eval/eval-report.md")
