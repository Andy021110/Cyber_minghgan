"""
api/deps.py — 依赖注入（Phase 3 API 工程化）

把图实例从路由里解耦：生产走 build_default_graph，测试用 set_graph 注入假图。
"""

from __future__ import annotations

from typing import Any

_graph: Any = None


def get_graph() -> Any:
    """返回图单例；未初始化时才构建（避免 import 时就连 API）。"""
    global _graph
    if _graph is None:
        from agent.runner import build_default_graph

        _graph = build_default_graph()
    return _graph


def set_graph(graph: Any) -> None:
    """测试注入口。"""
    global _graph
    _graph = graph
