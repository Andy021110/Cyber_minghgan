# cyber_planner.py 关键摘录
# 供 WorkBuddy 后端任务使用（B1–B5 I/O 解耦 + B5 process_message 提取）
# 原文件 1556 行，此处只保留需要改动的部分

# ══════════════════════════════════════════════════════
# 1. CyberBrainStore 类结构（不需要改动，了解接口即可）
# ══════════════════════════════════════════════════════

class CyberBrainStore:
    """KG 数据原子化 CRUD 接口。"""

    def __init__(self, kg_path: Path = KG_PATH):
        self._path = kg_path
        self._kg   = json.loads(kg_path.read_text(encoding="utf-8"))

    # 关键公开接口（不修改，只调用）：
    def retrieve(self, keyword: str, limit: int = 10) -> list[dict]: ...
    def create(self, layer, event_label, description, evidence,
               batch_id, importance, source_mode) -> dict: ...
    def update(self, node_uuid: str, **fields) -> dict: ...
    def delete(self, node_uuid: str) -> bool: ...
    # self._kg["nodes"]["Cyber_Minghan"] 包含三个层：
    #   Id_Dynamics / Ego_Dynamics / Superego_Dynamics
    # 每个节点字段：uuid, layer, event_label, description, evidence,
    #   importance(1-10), archived(bool), created_at, last_accessed_at,
    #   access_count, source_mode, batch_id


# ══════════════════════════════════════════════════════
# 2. B2 目标：handle_review() 的 I/O 解耦
#    原函数使用 input() 逐步交互，需要提取纯函数
# ══════════════════════════════════════════════════════

# ── 原函数依赖的 pipeline 导入 ──
from pipelines.decision_log import (
    read_awaiting,          # 返回 status='awaiting' 的条目列表
    resolve_approval,       # resolve_approval(entry_id, decision_str, note)
    update_pending_status,  # update_pending_status(pending_id, status_str)
)
from pipelines.decision_log import read_unconsumed_notifications, consume_notification

# ── 原 handle_review() 的交互流程摘要 ──
# 1. items = read_awaiting()  →  获取待审批队列
# 2. 逐条显示 item 内容（content / raw_evidence / ai_rationale / proposed_route）
# 3. decision = input(...)  →  "y" / "n" / "s" / "q"
# 4. if decision == "n":
#      reason = input(...)  →  拒绝理由
#      resolve_approval(entry_id, "rejected", reason)
# 5. if decision == "y" and route == "kg":
#      imp_raw = input(...)  →  importance 1-10 或回车接受默认
#      desc_raw = input(...)  →  修改描述或回车保留
#      store.create(layer=layer, event_label=content[:40], description=final_desc,
#                   evidence=evidence, batch_id="Review", importance=final_importance,
#                   source_mode=item["source_mode"])
#      resolve_approval(entry_id, "approved_kg", "")
# 6. if decision == "y" and route == "log":
#      _write_health_log_entry({...})
#      resolve_approval(entry_id, "approved_log", "")

# ── item 数据结构（read_awaiting() 返回的每条记录字段）──
# {
#   "id":             str,          # entry_id，传给 resolve_approval
#   "pending_id":     str,          # 传给 update_pending_status
#   "proposed_route": "kg" | "log",
#   "proposed_layer": "Id"|"Ego"|"Superego"|None,
#   "content":        str,
#   "raw_evidence":   str,
#   "ai_rationale":   str,
#   "importance":     int|None,     # AI 建议值
#   "importance_note":str|None,
#   "source_mode":    str,          # "health"|"work"|"study"|"cyber"
# }


# ══════════════════════════════════════════════════════
# 3. B3 目标：handle_kg() 的 I/O 解耦
#    原函数只有 print()，没有 input()，提取较简单
# ══════════════════════════════════════════════════════

# ── handle_kg() 的数据访问模式 ──
# store._kg["nodes"]["Cyber_Minghan"] 包含三层 key：
#   "Id_Dynamics" / "Ego_Dynamics" / "Superego_Dynamics"
# 每层是一个 list[dict]，每个 dict 就是一个节点
# archived 字段为 True 的节点是已归档节点

_LAYER_MAP = {
    "Id":       "Id_Dynamics",
    "Ego":      "Ego_Dynamics",
    "Superego": "Superego_Dynamics",
}
# 节点字段：uuid / layer / event_label / description / evidence /
#           importance / archived / created_at / last_accessed_at /
#           access_count / source_mode


# ══════════════════════════════════════════════════════
# 4. B4 目标：handle_prune() 的 I/O 解耦
#    依赖 pipelines/prune.py 的 scan_candidates / distribution_summary
# ══════════════════════════════════════════════════════

# ── prune 相关导入 ──
from pipelines.prune import scan_candidates, distribution_summary
# scan_candidates(kg_path, config) → list[dict]  # 按 staleness 排序的候选节点
# distribution_summary(kg_path, config) → {
#   "above_threshold": int,   # critical
#   "near_threshold": int,    # warning
#   "safe": int,              # healthy
#   "archived": int,
# }
# config = store._kg.get("meta", {}).get("prune_config", {
#   "staleness_threshold": 30,
#   "max_prune_per_session": 5,
# })

# ── 候选节点字段（scan_candidates 返回的每条记录）──
# {
#   "uuid": str,
#   "layer": "Id"|"Ego"|"Superego",
#   "event_label": str,
#   "importance": int,
#   "access_count": int,
#   "source_mode": str,
#   "created_at": str,
#   "_staleness": float,      # 越高越需要处理
#   "_archive_hint": str,     # AI 生成的归档理由
# }

# ── 归档操作 ──
def _archive_node(store, node_uuid: str) -> None:
    """软删除：标记 archived=true，不从 JSON 移除节点。"""
    store.update(node_uuid,
                 archived=True,
                 archived_at=datetime.now(timezone.utc).isoformat(),
                 archive_reason="pruned_stale")

# ── 提升重要度操作 ──
# store.update(node_uuid, importance=new_importance,
#              last_accessed_at=datetime.now(timezone.utc).isoformat())


# ══════════════════════════════════════════════════════
# 5. B5 目标：从 run() 提取 process_message()
#    了解 run() 的 streaming 模式和反刍触发逻辑
# ══════════════════════════════════════════════════════

# ── run() 核心结构（简化）──
# store = CyberBrainStore()          # 单例，维护在内存
# messages: list = []                # 对话历史，维护在内存
# turns = 0
#
# 主循环：
#   user_input = input("你: ")
#   messages.append({"role": "user", "content": user_input})
#   with client.messages.stream(model=MODEL, max_tokens=MAX_TOKENS,
#                               system=system_prompt, tools=CYBER_TOOLS,
#                               messages=messages) as stream:
#       for text_chunk in stream.text_stream:
#           print(text_chunk, end="", flush=True)
#   turns += 1
#   if turns % REFLECT_EVERY == 0:
#       messages = _reflection_cycle(client, store, messages)

# ── REFLECT_EVERY 是触发反刍的轮数间隔（全局常量，文件顶部定义）──

# ── _reflection_cycle() 的触发条件 ──
# 每 REFLECT_EVERY 轮自动触发一次
# 内部会：
#   1. 分析最近对话，提取新特征
#   2. 原 CLI 版会 input() 询问是否写入 KG
#   3. 执行 _safe_truncate(messages) 压缩上下文

# ── process_message() 需要实现的行为 ──
# async def process_message(user_input: str) -> AsyncGenerator[str, None]:
#   1. messages.append({"role": "user", "content": user_input})
#   2. 调用 anthropic SDK streaming，逐个 yield text_chunk
#   3. turns += 1
#   4. if turns % REFLECT_EVERY == 0:
#        feature = _reflect(client, recent_messages)  # 纯 LLM 分析，不做 input()
#        if feature.upper() != "NONE":
#            yield "[REFLECTION_TRIGGERED]"   # 特殊标记，FastAPI 转为 SSE reflection 事件
#            # 不询问用户，由前端面板展示提示，用户通过 /review 界面决定是否写入


# ══════════════════════════════════════════════════════
# 6. decision_log.py 路径现状（B1 目标）
# ══════════════════════════════════════════════════════

# pipelines/decision_log.py 第 33–37 行（硬编码路径，需参数化）：
#
#   LOGS_DIR      = Path(__file__).parent.parent / "decision_logs"
#   PENDING_FILE  = LOGS_DIR / "pending.jsonl"
#   AWAITING_FILE = LOGS_DIR / "awaiting_approval.jsonl"
#   HEALTH_LOG    = LOGS_DIR / "health_log.jsonl"
#   NOTIFY_FILE   = LOGS_DIR / "notifications.jsonl"
#
# 修改目标：所有读写函数加 logs_dir: Path = LOGS_DIR 参数
# 例：def read_awaiting(logs_dir: Path = LOGS_DIR) -> list[dict]:
#         awaiting = logs_dir / "awaiting_approval.jsonl"
#         ...
