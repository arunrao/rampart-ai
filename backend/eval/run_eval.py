"""
Run the prompt-injection evaluation corpus and enforce CI gates.

    python eval/run_eval.py                       # full run, writes eval/results/<ts>.json + .md
    python eval/run_eval.py --gates               # exit 1 if any gate in eval/gates.json fails
    python eval/run_eval.py --baseline eval/baseline.json --gates
    python eval/run_eval.py --model deepset/deberta-v3-base-injection --tag alt
    python eval/run_eval.py --regex-only          # fast smoke run without the classifier
    python eval/run_eval.py --save-baseline       # promote this run to eval/baseline.json

Reports, per profile:
  - BLOCK and FLAG-or-above false-positive rate per benign category and per
    length bucket (1k / 5k / 20k / 100k)
  - recall per attack family at FLAG+ and at BLOCK
  - AUROC (score vs label), 10-bin calibration curve
  - p50 / p95 latency per length bucket
Known-gap families are reported but never gate.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.attacks import Case, generate, load_benign  # noqa: E402

RESULTS_DIR = Path(__file__).parent / "results"
GATES_PATH = Path(__file__).parent / "gates.json"
KNOWN_GAPS_PATH = Path(__file__).parent / "known_gaps.json"

LENGTH_BUCKETS = [("<=1k", 1_000), ("<=5k", 5_000), ("<=20k", 20_000), ("<=100k", 100_000)]
RANK = {"allow": 0, "monitor": 1, "unavailable": 2, "flag": 3, "block": 4}

# Natural profile for each benign category; attacks are always third-party documents.
CATEGORY_PROFILE = {
    "benign_technical": "code_docs",
    "benign_imperative": "code_docs",
    "benign_about_ai": "user_brief",
}


def bucket_for(n: int) -> str:
    for name, lim in LENGTH_BUCKETS:
        if n <= lim:
            return name
    return ">100k"


def pct(a: float, b: float) -> Optional[float]:
    return None if b == 0 else a / b


def percentile(xs: List[float], q: float) -> Optional[float]:
    if not xs:
        return None
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, int(round(q * (len(xs) - 1)))))
    return xs[k]


def auroc(scores: List[float], labels: List[int]) -> Optional[float]:
    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg:
        return None
    # rank-sum (Mann-Whitney) with tie handling
    ranked = sorted((s, l) for s, l in zip(scores, labels))
    ranks = [0.0] * len(ranked)
    i = 0
    while i < len(ranked):
        j = i
        while j + 1 < len(ranked) and ranked[j + 1][0] == ranked[i][0]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[k] = r
        i = j + 1
    rank_pos = sum(r for r, (_, l) in zip(ranks, ranked) if l == 1)
    return (rank_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def calibration(scores: List[float], labels: List[int], bins: int = 10) -> List[Dict]:
    out = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [(s, l) for s, l in zip(scores, labels) if lo <= s < hi or (b == bins - 1 and s == 1.0)]
        if sel:
            out.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(sel),
                        "mean_score": statistics.mean(s for s, _ in sel),
                        "positive_rate": statistics.mean(l for _, l in sel)})
    return out


# ---------------------------------------------------------------------------

def build_detector(model: Optional[str], regex_only: bool):
    from models.prompt_injection_detector import (
        DeBERTaPromptInjectionDetector, HybridPromptInjectionDetector, PromptInjectionDetector,
    )

    if regex_only:
        return PromptInjectionDetector(), "regex-only"
    h = HybridPromptInjectionDetector(use_onnx=False)
    if model:
        os.environ.setdefault("RAMPART_ALLOW_UNPINNED_MODELS", "1")
        h.deberta_detector = DeBERTaPromptInjectionDetector(model_name=model, use_onnx=False)
    assert h.deberta_detector is not None and h.deberta_detector.available, "classifier failed to load"
    return h, h.deberta_detector.model_version


def run(detector, cases: List[Case], profiles: List[str], limit: Optional[int]) -> List[Dict]:
    rows: List[Dict] = []
    if limit:
        cases = cases[:limit]
    total = len(cases) * len(profiles)
    done = 0
    for case in cases:
        for profile in profiles:
            t0 = time.perf_counter()
            r = detector.detect(case.text, profile=profile)
            dt = (time.perf_counter() - t0) * 1000
            rows.append({
                **case.to_dict(), "profile": profile, "verdict": r["verdict"], "score": float(r["score"]),
                "deberta": float(r["detection_details"]["deberta"]["confidence"]),
                "degraded": bool(r["degraded"]), "chunks_total": r["chunks"]["total"],
                "chunks_flagged": r["chunks"]["flagged"], "reasons": sorted({x["code"] for x in r["reasons"]}),
                "latency_ms": dt, "bucket": bucket_for(len(case.text)),
            })
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{total}", file=sys.stderr)
    return rows


def summarize(rows: List[Dict]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"n_rows": len(rows), "per_profile": {}}
    by_profile = defaultdict(list)
    for r in rows:
        by_profile[r["profile"]].append(r)

    for profile, prows in by_profile.items():
        benign = [r for r in prows if r["label"] == 0]
        attacks = [r for r in prows if r["label"] == 1]
        s: Dict[str, Any] = {}

        # FPR per category / bucket
        fpr: Dict[str, Dict] = {}
        for key in ("category", "bucket"):
            groups = defaultdict(list)
            for r in benign:
                groups[r[key]].append(r)
            for g, rs in sorted(groups.items()):
                fpr[f"{key}:{g}"] = {
                    "n": len(rs),
                    "block_fpr": pct(sum(r["verdict"] == "block" for r in rs), len(rs)),
                    "flag_plus_fpr": pct(sum(RANK[r["verdict"]] >= RANK["flag"] for r in rs), len(rs)),
                    "unavailable": sum(r["verdict"] == "unavailable" for r in rs),
                }
        s["false_positive_rates"] = fpr

        # recall per family
        rec: Dict[str, Dict] = {}
        fam = defaultdict(list)
        for r in attacks:
            fam[r["family"]].append(r)
        for f, rs in sorted(fam.items()):
            rec[f] = {
                "n": len(rs), "known_gap": all(r["known_gap"] for r in rs),
                "recall_flag_plus": pct(sum(RANK[r["verdict"]] >= RANK["flag"] for r in rs), len(rs)),
                "recall_block": pct(sum(r["verdict"] == "block" for r in rs), len(rs)),
            }
        gating = [r for r in attacks if not r["known_gap"]]
        rec["_all_gating"] = {
            "n": len(gating),
            "recall_flag_plus": pct(sum(RANK[r["verdict"]] >= RANK["flag"] for r in gating), len(gating)),
            "recall_block": pct(sum(r["verdict"] == "block" for r in gating), len(gating)),
        }
        s["recall"] = rec

        scored = [r for r in prows if not r["known_gap"]]
        s["auroc"] = auroc([r["score"] for r in scored], [r["label"] for r in scored])
        s["auroc_deberta_only"] = auroc([r["deberta"] for r in scored], [r["label"] for r in scored])
        s["calibration"] = calibration([r["score"] for r in scored], [r["label"] for r in scored])

        lat: Dict[str, Dict] = {}
        bb = defaultdict(list)
        for r in prows:
            bb[r["bucket"]].append(r["latency_ms"])
        for b, xs in sorted(bb.items(), key=lambda kv: [n for n, _ in LENGTH_BUCKETS + [(">100k", 0)]].index(kv[0])):
            lat[b] = {"n": len(xs), "p50_ms": percentile(xs, 0.5), "p95_ms": percentile(xs, 0.95)}
        s["latency"] = lat
        s["degraded_rows"] = sum(r["degraded"] for r in prows)
        out["per_profile"][profile] = s
    return out


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

def _get(d: Dict, path: str):
    cur: Any = d
    for part in path.split("/"):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def check_gates(summary: Dict, gates: Dict, baseline: Optional[Dict]) -> List[str]:
    failures: List[str] = []
    for g in gates["gates"]:
        val = _get(summary, g["metric"])
        if val is None:
            failures.append(f"{g['metric']}: metric missing")
            continue
        if "max" in g and val > g["max"]:
            failures.append(f"{g['metric']}={val:.4f} exceeds max {g['max']}")
        if "min" in g and val < g["min"]:
            failures.append(f"{g['metric']}={val:.4f} below min {g['min']}")
    if baseline:
        tol = gates.get("regression_tolerance", 0.0)
        for g in gates["gates"]:
            cur, prev = _get(summary, g["metric"]), _get(baseline, g["metric"])
            if cur is None or prev is None:
                continue
            if "max" in g and cur > prev + tol:
                failures.append(f"regression {g['metric']}: {prev:.4f} -> {cur:.4f}")
            if "min" in g and cur < prev - tol:
                failures.append(f"regression {g['metric']}: {prev:.4f} -> {cur:.4f}")
    return failures


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _f(v: Optional[float], pct_: bool = True) -> str:
    if v is None:
        return "-"
    return f"{v * 100:.1f}%" if pct_ else f"{v:.3f}"


def to_markdown(summary: Dict, meta: Dict, failures: List[str]) -> str:
    lines = [f"# Injection eval — {meta['model_version']} / policy {meta['policy_version']}", "",
             f"run: {meta['timestamp']}  rows: {summary['n_rows']}  tag: {meta.get('tag') or '-'}", ""]
    if failures:
        lines += ["## GATE FAILURES", ""] + [f"- {f}" for f in failures] + [""]
    else:
        lines += ["All gates passed.", ""]
    for profile, s in summary["per_profile"].items():
        lines += [f"## profile: {profile}", "", f"AUROC {_f(s['auroc'], False)} (classifier alone {_f(s['auroc_deberta_only'], False)}); degraded rows {s['degraded_rows']}", "",
                  "| benign group | n | BLOCK FPR | FLAG+ FPR |", "|---|---|---|---|"]
        for k, v in s["false_positive_rates"].items():
            lines.append(f"| {k} | {v['n']} | {_f(v['block_fpr'])} | {_f(v['flag_plus_fpr'])} |")
        lines += ["", "| attack family | n | recall FLAG+ | recall BLOCK | known gap |", "|---|---|---|---|---|"]
        for k, v in s["recall"].items():
            lines.append(f"| {k} | {v['n']} | {_f(v['recall_flag_plus'])} | {_f(v['recall_block'])} | {'yes' if v.get('known_gap') else ''} |")
        lines += ["", "| length | n | p50 ms | p95 ms |", "|---|---|---|---|"]
        for k, v in s["latency"].items():
            lines.append(f"| {k} | {v['n']} | {v['p50_ms']:.0f} | {v['p95_ms']:.0f} |")
        lines += ["", "| score bin | n | mean score | positive rate |", "|---|---|---|---|"]
        for c in s["calibration"]:
            lines.append(f"| {c['bin']} | {c['n']} | {c['mean_score']:.2f} | {_f(c['positive_rate'])} |")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="alternative HF classifier to compare")
    ap.add_argument("--regex-only", action="store_true")
    ap.add_argument("--profiles", default="natural,third_party_document",
                    help="comma list; 'natural' = per-category profile")
    ap.add_argument("--limit", type=int, help="limit cases (smoke)")
    ap.add_argument("--benign-limit", type=int, help="limit benign docs per category")
    ap.add_argument("--gates", action="store_true", help="exit 1 on gate failure")
    ap.add_argument("--baseline", default=str(Path(__file__).parent / "baseline.json"))
    ap.add_argument("--save-baseline", action="store_true")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    from models.injection_policy import POLICY_VERSION

    detector, model_version = build_detector(args.model, args.regex_only)

    benign_docs = []
    for cat in ("benign_technical", "benign_about_ai", "benign_imperative"):
        benign_docs += load_benign(cat, args.benign_limit)
    benign_cases = [Case(d["id"], d["kind"], d["text"], 0, d["category"]) for d in benign_docs]
    attack_cases = generate()
    print(f"benign={len(benign_cases)} attacks={len(attack_cases)} model={model_version}", file=sys.stderr)

    want_profiles = args.profiles.split(",")
    rows: List[Dict] = []
    for prof in want_profiles:
        if prof == "natural":
            # each benign category under the profile a caller would realistically pick;
            # attacks always arrive as third-party documents
            new: List[Dict] = []
            for cat, cat_prof in CATEGORY_PROFILE.items():
                new += run(detector, [c for c in benign_cases if c.category == cat], [cat_prof], args.limit)
            new += run(detector, attack_cases, ["third_party_document"], args.limit)
            for r in new:
                r["profile_used"], r["profile"] = r["profile"], "natural"
        else:
            new = run(detector, benign_cases + attack_cases, [prof], args.limit)
            for r in new:
                r["profile_used"] = prof
        rows += new

    summary = summarize(rows)
    gates = json.loads(GATES_PATH.read_text()) if GATES_PATH.exists() else {"gates": []}
    baseline = None
    if args.baseline and Path(args.baseline).exists():
        baseline = json.loads(Path(args.baseline).read_text()).get("summary")
    failures = check_gates(summary, gates, baseline)

    meta = {"timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z", "model_version": model_version,
            "policy_version": POLICY_VERSION, "tag": args.tag, "regex_only": args.regex_only,
            "n_benign": len(benign_cases), "n_attacks": len(attack_cases)}
    RESULTS_DIR.mkdir(exist_ok=True)
    stem = RESULTS_DIR / (meta["timestamp"].replace(":", "") + (f"_{args.tag}" if args.tag else ""))
    payload = {"meta": meta, "summary": summary, "gate_failures": failures, "rows": rows}
    stem.with_suffix(".json").write_text(json.dumps(payload, indent=1, default=str))
    md = to_markdown(summary, meta, failures)
    stem.with_suffix(".md").write_text(md)
    print(md)
    print(f"\nwrote {stem}.json / .md", file=sys.stderr)

    if args.save_baseline:
        Path(args.baseline).write_text(json.dumps({"meta": meta, "summary": summary}, indent=1, default=str))
        print(f"baseline saved to {args.baseline}", file=sys.stderr)

    if args.gates and failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
