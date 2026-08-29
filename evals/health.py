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
import re
import subprocess
from pathlib import Path

from evals import badcases, replay
from experiments import ledger

_ROOT = Path(__file__).resolve().parent.parent

# 只有改动核心代码路径才算「需要走流程」；改文档/注释/测试不算
_CORE_PREFIXES = ("cyber_planner.py", "memory/", "agent/", "api/", "pipelines/")
_REF_RE = re.compile(r"\b(EXP-\d{3}|BC-\d{3})\b")


def commit_linkage(n: int = 30) -> dict:
    """最近 N 个提交里，改动核心代码的有多少关联了实验或 badcase。

    为什么必须有这个指标：
    台账和 badcase 只能约束「登记过的东西」。**如果改动时压根不登记，
    整套机制管不着**——这是回溯唯一的盲区，也是最容易被糊弄过去的地方。
    量化出来，才谈得上「到底有没有在用」，而不是嘴上说有。
    """
    try:
        out = subprocess.run(
            ["git", "log", f"-{n}", "--format=__C__%s", "--name-only"],
            cwd=_ROOT, capture_output=True, text=True, timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {"scanned": 0, "core": 0, "linked": 0, "rate": 0.0, "unlinked": []}

    core, linked, unlinked = 0, 0, []
    for block in out.split("__C__")[1:]:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        subject, files = lines[0], lines[1:]
        if not any(f.startswith(_CORE_PREFIXES) for f in files):
            continue                      # 改文档/注释/测试不算
        core += 1
        if _REF_RE.search(subject):
            linked += 1
        else:
            unlinked.append(subject[:52])

    return {
        "scanned": len(out.split("__C__")) - 1,
        "core": core,
        "linked": linked,
        "rate": round(linked / core, 3) if core else 0.0,
        "unlinked": unlinked[:5],
    }


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
        "process": commit_linkage(),
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
    p = m["process"]
    if p["core"] >= 3 and p["rate"] < 0.5:
        tips.append(
            f"[警告] 实验关联率 {p['rate']:.0%}：{p['core'] - p['linked']} 个核心改动"
            "没关联实验或 badcase——这些改动事后无从回溯（机制管不住"
            "「压根不登记」，这是最大的漏洞，只能靠这个指标盯着）"
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
    p = m["process"]
    print("流程（最近 30 个提交）")
    print(f"  核心改动     {p['core']} 个，关联实验/badcase {p['linked']} 个")
    print(f"  实验关联率   {p['rate']:.0%}   "
          "（低 = 有改动绕过了流程，事后无法回溯）")
    if p["unlinked"]:
        print("    未关联的改动：")
        for s in p["unlinked"]:
            print(f"      - {s}")
    print("\n诊断")
    for t in diagnose(m):
        print(f"  {t}")
    return 1 if b["regressions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
