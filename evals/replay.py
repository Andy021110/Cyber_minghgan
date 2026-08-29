"""
evals/replay.py — Badcase 回放器

把「写在文档里的失败样本」变成「可执行的回归测试」。

判定语义（重要）：
- open   + 回放失败 → 已知缺陷仍在（正常，提醒去修）
- open   + 回放通过 → 可能已自愈或当初记录不准，提示人工核对
- fixed  + 回放失败 → **回归**，退出码 1（这是本工具存在的核心理由）
- fixed  + 回放通过 → 修复被守住

用法：
    python3 -m evals.replay
    python3 -m evals.replay --only open
    python3 -m evals.replay --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from evals.badcases import load_cases  # noqa: E402
from memory.episodic_store import EpisodicStore  # noqa: E402


def _run_retrieval(case: dict) -> tuple[str, str]:
    """用种子数据构造临时记忆库，回放查询，检查期望。

    reproduce.source:
      - "l0"（默认）→ L0 原文记忆 EpisodicStore
      - "l1"         → L1 动力学 KG CyberBrainStore（可验证可见性等问题）
    reproduce.must_contain     → 结果里**必须**出现的内容
    reproduce.must_not_contain → 结果里**必须不**出现的内容（用于泄漏类缺陷）
    """
    r = case["reproduce"]
    source = r.get("source", "l0")

    with tempfile.TemporaryDirectory(prefix="badcase_") as tmp:
        if source == "l1":
            hits, _ = _query_l1(r, Path(tmp))
        else:
            hits = _query_l0(r, Path(tmp))

        blob = json.dumps(hits, ensure_ascii=False)
        if r.get("must_not_contain"):
            ok = all(x not in blob for x in _as_list(r["must_not_contain"]))
        else:
            ok = all(x in blob for x in _as_list(r["must_contain"]))
        return ("pass" if ok else "fail"), f"命中 {len(hits)} 条"


def _query_l0(r: dict, tmp: Path) -> list[dict]:
    epi = EpisodicStore(tmp / "epi.jsonl")
    for item in r["seed"]:
        epi.append(
            ts=item.get("ts", "2026-01-01"),
            user_text=item.get("user_text", ""),
            assistant_text=item.get("assistant_text", ""),
            source="badcase",
        )
    return epi.search(r["query"], limit=int(r.get("limit", 5)))


def _query_l1(r: dict, tmp: Path) -> tuple[list[dict], Any]:
    """构造临时 KG（基于空模板），灌入种子节点后检索。"""
    import shutil

    from cyber_planner import CyberBrainStore

    kg_path = tmp / "kg.json"
    template = _ROOT / "yuanbao_cyber_minghan_kg_EMPTY.json"
    if not template.exists():
        raise FileNotFoundError(
            f"缺少空 KG 模板 {template}（回放 l1 类 badcase 需要它）"
        )
    shutil.copy2(template, kg_path)
    store = CyberBrainStore(kg_path=kg_path)
    for n in r["seed"]:
        store.create(
            layer=n.get("layer", "Ego"),
            event_label=n["event_label"],
            description=n.get("description", ""),
            evidence=n.get("evidence", ""),
            visibility=n.get("visibility", "private"),
        )
    return store.retrieve(r["query"], limit=int(r.get("limit", 5))), store


def _as_list(value: Any) -> list[str]:
    return value if isinstance(value, list) else [str(value)]


def _tail(stdout: str, width: int = 90) -> str:
    lines = [ln.strip() for ln in (stdout or "").splitlines() if ln.strip()]
    return lines[-1][:width] if lines else ""


def _run_regression_test(spec: str, timeout: int = 300) -> tuple[str, str]:
    """执行 badcase 登记的回归测试。

    为什么必须有这一步：
    一个标为 fixed 却无法自动验证的 badcase，和没修没有区别——
    报表上那句「无回归」只是因为压根没检查。
    只有把 regression_test 真正跑起来，REGRESSION 这个判定才有意义。

    支持两种 node id：
      - 后端 `tests/test_store.py::test_xxx`   → pytest
      - 前端 `frontend/.../X.test.tsx::用例名`  → vitest -t
    自由文本（无法解析）保持 manual，但详情里会说明，提醒补登记为可执行形式。
    """
    spec = (spec or "").strip()
    if not spec:
        return "manual", "未登记 regression_test"

    if re.search(r"\.py(::|$)", spec):
        return _run_pytest(spec, timeout)
    if re.search(r"\.tsx?(::|$)", spec):
        return _run_vitest(spec, timeout)
    return "manual", f"无法自动执行（非标准 node id）：{spec[:60]}"


def _run_pytest(spec: str, timeout: int) -> tuple[str, str]:
    cmd = [
        sys.executable, "-m", "pytest", spec,
        "-q", "--no-header", "-p", "no:cacheprovider",
    ]
    try:
        proc = subprocess.run(
            cmd, cwd=_ROOT, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "fail", f"pytest 超时（>{timeout}s）"
    ok = proc.returncode == 0
    return ("pass" if ok else "fail"), f"pytest rc={proc.returncode} {_tail(proc.stdout)}"


def _run_vitest(spec: str, timeout: int) -> tuple[str, str]:
    path, _, name = spec.partition("::")
    fe = _ROOT / "frontend"
    if not (fe / "node_modules").exists():
        return "manual", "frontend/node_modules 缺失，跳过前端回归"
    cmd = ["npx", "vitest", "run", path, "--reporter=dot"]
    if name:
        cmd += ["-t", name]
    try:
        proc = subprocess.run(
            cmd, cwd=fe, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "fail", f"vitest 超时（>{timeout}s）"
    ok = proc.returncode == 0
    return ("pass" if ok else "fail"), f"vitest rc={proc.returncode} {_tail(proc.stdout)}"


def replay(case: dict) -> tuple[str, str]:
    """返回 (结果, 说明)。结果 ∈ pass / fail / manual。"""
    ctype = case.get("type")
    if ctype == "retrieval":
        try:
            return _run_retrieval(case)
        except Exception as exc:  # 回放本身出错也要暴露，不能静默
            return "fail", f"回放异常：{exc}"
    # 非检索类：优先执行登记的回归测试，否则 fixed 类永远无法验证
    if case.get("regression_test"):
        return _run_regression_test(case["regression_test"])
    return "manual", "需人工或外部条件验证"


def evaluate(cases: list[dict]) -> list[dict]:
    rows = []
    for c in cases:
        result, detail = replay(c)
        status = c.get("status", "open")
        if status == "fixed" and result == "fail":
            verdict = "REGRESSION"
        elif status == "fixed" and result == "pass":
            verdict = "OK"
        elif status == "open" and result == "pass":
            verdict = "RECHECK"   # 记录为未修却能过，需人工核对是否已自愈
        elif status == "open" and result == "fail":
            verdict = "OPEN"
        else:
            verdict = "MANUAL"
        rows.append(
            {
                "id": c.get("id"),
                "type": c.get("type"),
                "status": status,
                "replay": result,
                "verdict": verdict,
                "detail": detail,
                "title": c.get("title", ""),
                "fix_ref": c.get("fix_ref", ""),
                "regression_test": c.get("regression_test", ""),
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Badcase 回放")
    ap.add_argument("--only", choices=["open", "fixed", "all"], default="all")
    ap.add_argument("--path", default=None, help="指定 cases.jsonl（便于做注入实验）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    cases = load_cases(args.path)
    if args.only != "all":
        cases = [c for c in cases if c.get("status") == args.only]

    rows = evaluate(cases)
    regressions = [r for r in rows if r["verdict"] == "REGRESSION"]
    manual = [r for r in rows if r["verdict"] == "MANUAL"]

    if args.json:
        print(json.dumps(
            {
                "rows": rows,
                "auto_verified": len(rows) - len(manual),
                "manual": len(manual),
                "coverage": (len(rows) - len(manual)) / len(rows) if rows else 0.0,
            },
            ensure_ascii=False, indent=2,
        ))
        return 1 if regressions else 0

    print(f"Badcase 回放：{len(rows)} 条")
    print(f"{'ID':<8}{'类型':<10}{'状态':<8}{'回放':<8}{'判定':<12}标题")
    for r in rows:
        print(
            f"{r['id']:<8}{r['type']:<10}{r['status']:<8}"
            f"{r['replay']:<8}{r['verdict']:<12}{r['title']}"
        )

    # 自覆盖率：MANUAL 越多，这套机制的守护能力越弱。
    # 报出来是为了让"没检查"不伪装成"没回归"。
    cov = (len(rows) - len(manual)) / len(rows) * 100 if rows else 0.0
    print(f"\n自动验证 {len(rows) - len(manual)}/{len(rows)}（{cov:.0f}%），"
          f"待人工 {len(manual)} 条")
    if manual:
        for r in manual:
            print(f"  - {r['id']} {r['title']}｜{r['detail']}")

    recheck = [r for r in rows if r["verdict"] == "RECHECK"]
    if recheck:
        print(f"\n[注意] {len(recheck)} 条标记为未修却回放通过，请人工核对：")
        for r in recheck:
            print(f"  - {r['id']} {r['title']}")

    if regressions:
        print(f"\n[回归] {len(regressions)} 条已修复的 badcase 又失败了：")
        for r in regressions:
            print(f"  - {r['id']} {r['title']}（fix_ref: {r['fix_ref'] or '无'}）")
        return 1

    print("\n无回归。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
