"""
evals/health.py — 开发工作流自身的健康度

为什么需要它：
我们可以证明某个**功能**好不好（Recall@5 之类），
但拿什么证明「开发这个功能的方式」本身高效？
这里给出四个可观测指标，答案必须来自数据而不是感觉。

指标与读法：
  1. 回放覆盖率    = 非 MANUAL 的 badcase / 全部
                   低 = 「无回归」里混着大量「没检查」，是自欺
  2. 修复留存率    = fixed 且回放通过的 / 全部 fixed
                   低于 100% 就是正在发生的回归，必须立刻处理
  3. 预登记率      = 登记了 baseline 的实验 / 全部
                   低 = 有大量「跑完才补假设」的伪实验
  4. 实验采纳率    = adopt / 已结题
                   过高（接近 1）反而可疑：说明只做安全实验，没在证伪

用法：
    python3 -m evals.health
    python3 -m evals.health --json
"""

from __future__ import annotations

import argparse
import json

from evals import badcases, replay
from experiments import ledger


def collect() -> dict:
    cases = badcases.load_cases()
    rows = replay.evaluate(cases)

    fixed = [r for r in rows if r["status"] == "fixed"]
    open_ = [r for r in rows if r["status"] == "open"]
    manual = [r for r in rows if r["replay"] == "manual"]
    regressions = [r for r in rows if r["verdict"] == "REGRESSION"]
    kept = [r for r in fixed if r["replay"] == "pass"]

    exp_rows = ledger.load()
    exp_stats = ledger.stats()

    pct = lambda a, b: round(a / b, 3) if b else 0.0  # noqa: E731

    return {
        "badcase": {
            "total": len(rows),
            "open": len(open_),
            "fixed": len(fixed),
            "manual": len(manual),
            "coverage": pct(len(rows) - len(manual), len(rows)),
            "retention": pct(len(kept), len(fixed)),
            "regressions": [r["id"] for r in regressions],
        },
        "experiment": {
            "total": exp_stats["total"],
            "running": exp_stats["running"],
            "done": exp_stats["done"],
            "adopted": exp_stats["adopted"],
            "rejected": exp_stats["rejected"],
            "adoption_rate": exp_stats["adoption_rate"],
            "pre_registered": pct(exp_stats["with_baseline"], exp_stats["total"]),
        },
    }


def diagnose(m: dict) -> list[str]:
    """把数字翻译成该不该担心——指标不解读等于没测。"""
    tips = []
    b, e = m["badcase"], m["experiment"]

    if b["regressions"]:
        tips.append(f"[严重] 发生回归：{', '.join(b['regressions'])}（已修的又坏了）")
    if b["fixed"] and b["retention"] < 1.0:
        tips.append(f"[严重] 修复留存率 {b['retention']:.0%}，有已修缺陷没被守住")
    if b["total"] and b["coverage"] < 0.5:
        tips.append(
            f"[警告] 回放覆盖率仅 {b['coverage']:.0%}："
            f"{b['manual']} 条无法自动验证，「无回归」可能只是没检查"
        )
    if e["total"] and e["pre_registered"] < 1.0:
        tips.append(
            f"[警告] 预登记率 {e['pre_registered']:.0%}："
            "存在先跑后补假设的实验，其结论不可信"
        )
    if e["done"] >= 5 and e["adoption_rate"] > 0.9:
        tips.append(
            f"[提示] 实验采纳率 {e['adoption_rate']:.0%} 偏高："
            "若长期如此，说明只做安全实验，没有真正尝试证伪"
        )
    if not tips:
        tips.append("各项指标正常。")
    return tips


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="开发工作流健康度")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    m = collect()
    if args.json:
        print(json.dumps({**m, "diagnosis": diagnose(m)}, ensure_ascii=False, indent=2))
        return 1 if m["badcase"]["regressions"] else 0

    b, e = m["badcase"], m["experiment"]
    print("Badcase")
    print(f"  总数 {b['total']}（未修 {b['open']} / 已修 {b['fixed']}）")
    print(f"  回放覆盖率   {b['coverage']:.0%}   待人工 {b['manual']} 条")
    print(f"  修复留存率   {b['retention']:.0%}   "
          f"（fixed 中回放通过数 {b['fixed'] - len(b['regressions'])}/{b['fixed']}）")
    print("实验台账")
    print(f"  总数 {e['total']}（进行中 {e['running']} / 已结题 {e['done']}）")
    print(f"  预登记率     {e['pre_registered']:.0%}   （登记了基线的比例）")
    print(f"  采纳率       {e['adoption_rate']:.0%}   "
          f"（采纳 {e['adopted']} / 否决 {e['rejected']}）")
    print("\n诊断")
    for t in diagnose(m):
        print(f"  {t}")
    return 1 if b["regressions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
