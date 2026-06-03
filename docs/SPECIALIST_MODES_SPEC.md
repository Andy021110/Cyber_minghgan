# 专项模式开发规范（/study + /work）

> 版本：2026-06-03  
> 状态：设计阶段，待实现

---

## 第一章：架构总览

### 1.1 设计原则

专项模式的定位在第一章已明确：**外在行为层，不是内心世界层**。

三条不能打破的约束：
1. **KG 只读**：专项模式可以读 KG 理解「明翰是谁」，但不能直接写入
2. **唯一写出口**：观察到的心理模式 → `pending.jsonl` → 审批 → KG
3. **会话独立**：每次进入是全新上下文，历史不继承，不污染主对话

### 1.2 文件结构

```
元宝-明翰/
├── cyber_planner.py          ← 修改：_MODE_MAP 加入 study/work
├── health_coach.py           ← 不动（待后期迁移到 specialist_base）
└── pipelines/
    ├── specialist_base.py    ← 新建：共享对话循环、KG读取、extract_pending
    ├── study_planner.py      ← 新建：学习规划模式（薄壳）
    └── work_planner.py       ← 新建：工作规划模式（薄壳）
```

### 1.3 模块关系

```
cyber_planner.py
    └── /switch study --file xxx
            │
            ▼
    study_planner.run(trigger_context, file_content)
            │
            ├── specialist_base.build_kg_summary()     ← 读 KG（只读）
            ├── specialist_base.generate_suggestion()  ← 本周建议
            ├── specialist_base.conversation_loop()    ← 对话循环
            └── specialist_base.extract_pending()      ← 退出时提取观察
                        │
                        ▼
                pending.jsonl → batch_processor → /review → KG
```

### 1.4 与 health_coach.py 的对比

health_coach.py 已经是一个成熟的专项模式，但它是「独体」设计。新模式抽共享基座的原因：

| 对比项 | health_coach.py | 新架构 |
|--------|----------------|--------|
| KG 读取 | 各自实现 | 共享 `build_kg_summary()` |
| 对话循环 | 各自实现 | 共享 `conversation_loop()` |
| extract_pending | 各自实现 | 共享，提取 prompt 可配置 |
| 本周建议 | 无 | 共享 `generate_suggestion()` |
| 联网 toggle | 无 | 共享 web_search tool 接入 |
| 文件注入 | 无 | 共享 `load_file_content()` |

health_coach.py 后期可以改为调用 specialist_base，但不在本次开发范围内。

### 1.5 config 接口（薄壳只需要提供这些）

```python
MODE_CONFIG = {
    # 基础信息
    "mode_name":     "学习规划",       # 用于界面标题
    "mode_key":      "study",          # /switch 的 key
    "ai_role_name":  "学习规划师",     # AI 的称呼

    # 进入时的 context intake 提示
    "context_prompt": "本次想聊什么方向？（一句话即可，回车跳过建议）",

    # 系统提示词主体（specialist_base 会在外层拼接 KG 摘要和文件内容）
    "system_prompt_body": "...",

    # extract_pending 的提取关注点（注入到提取 prompt）
    "extract_focus": "...",
}
```

---

### 1.6 本章遗留问题（写作中发现）

**问题一：health_coach 要不要同步迁移？**  
不建议现在迁移，等 study/work 跑稳后再统一重构。保持 health_coach 独立运行，避免引入回归风险。

**问题二：specialist_base 放在哪个目录？**  
放 `pipelines/` 和 `health_coach.py` 保持一致（health_coach 在根目录，这里应该也放根目录或者统一放 pipelines）。建议都放根目录，保持和 health_coach.py 同级，因为 `cyber_planner.py` 用 `importlib.import_module` 导入，根目录更简洁。

**→ 决定：specialist_base.py、study_planner.py、work_planner.py 全部放根目录，和 health_coach.py 同级。**

---

## 第二章：specialist_base.py 设计

### 2.1 职责边界

`specialist_base.py` 只负责**可以在所有专项模式间复用的逻辑**，不包含任何领域知识。

| 函数 | 职责 | 来源 |
|------|------|------|
| `build_kg_summary()` | 读 KG，生成三层目录摘要注入 system prompt | 复制自 health_coach.py |
| `_retrieve()` | KG 字符串检索，只读，命中后更新 access_count | 复制自 health_coach.py |
| `build_system_prompt()` | 拼接 KG 摘要 + 文件内容 + mode 配置的 system_prompt_body | 新写 |
| `extract_pending()` | 对话结束后提取观察，提取 prompt 由 config 注入 | 改写自 health_coach.py |
| `conversation_loop()` | 标准对话循环（streaming + Tool Use + exit 处理）| 改写自 health_coach.py |

---

### 2.2 SPECIALIST_TOOLS（只读 retrieve_memory）

所有专项模式共用同一个只读工具定义，直接复用 health_coach 的 `HEALTH_TOOLS`，改个名字：

```python
SPECIALIST_TOOLS = [
    {
        "name": "retrieve_memory",
        "description": (
            "在明翰的心智图谱（Id/Ego/Superego 三层）中检索相关记忆节点，"
            "了解这个人的行为模式、偏好和心理特征，以提供个性化建议。\n\n"
            "【只读权限】专项模式无权修改图谱内容。\n\n"
            "keyword: 中文关键词。limit: 返回条数上限，默认 5。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
                "limit":   {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
            },
            "required": ["keyword"],
        },
    }
]
```

---

### 2.3 build_system_prompt() 拼接逻辑

```python
def build_system_prompt(config: dict, file_content: str = "") -> str:
    kg_summary    = build_kg_summary()
    file_section  = f"\n\n---\n\n## 本次参考材料\n\n{file_content}" if file_content else ""
    current_time  = _now_str()

    return f"""[当前时间] {current_time}

# 角色：明翰的{config['ai_role_name']}

{config['system_prompt_body']}

## 权限
- ✓ 调用 retrieve_memory 查询明翰的心智图谱（只读）
- ✗ 不能修改心智图谱
- ✗ 不做泛泛而谈的建议，必须结合明翰的具体模式

---

{kg_summary}{file_section}
"""
```

`file_section` 只有在 `--file` 传入内容时才出现。KG 摘要每次进入模式时实时生成，不缓存。

---

### 2.4 extract_pending() 改写点

health_coach 的提取 prompt 写死了「健康教练对话」。specialist_base 的版本改为从 config 注入：

```python
_EXTRACT_SYSTEM_TEMPLATE = """\
你是一个行为观察员，从{mode_name}对话中提取值得记录的用户行为信息。
提取结果会进入待分类池，由下游决定写入心智图谱还是日志——你只负责提取，不负责路由。

【提取倾向：宁多勿少】以下情况均应提取：
{extract_focus}

【不提取】
- 纯粹的任务内容（课程知识、代码逻辑、项目细节）
- 用户对 AI 的客套话、无实质信息的短句

输出严格 JSON 数组（禁止额外文字）：
[{{"content": "提炼后的行为观察", "raw_evidence": "原始对话片段"}}]
无内容时输出 []
"""

def extract_pending(messages, client, config):
    system = _EXTRACT_SYSTEM_TEMPLATE.format(
        mode_name=config["mode_name"],
        extract_focus=config["extract_focus"],
    )
    # ... 后续逻辑与 health_coach 完全相同
```

---

### 2.5 conversation_loop() 关键参数

```python
def conversation_loop(
    config:          dict,
    system_prompt:   str,
    client:          anthropic.Anthropic,
    trigger_context: str = "",
    web_search:      bool = False,   # 第四章详述
) -> list:                           # 返回完整 messages 供 extract_pending 使用
```

内部行为与 health_coach 的 `run()` 主循环完全相同，差异仅在：
- 打印标题用 `config["mode_name"]`
- AI 称呼用 `config["ai_role_name"]`
- 支持 `/web on` / `/web off` 切换 web_search（第四章详述）

---

### 2.6 本章遗留问题

**问题：`_retrieve()` 和 `build_kg_summary()` 会同时存在于 health_coach.py 和 specialist_base.py 两个地方，造成重复。**

短期接受这个重复，等 health_coach 迁移时一并清理。不提前抽公共模块，避免引入导入链问题。

---

## 第三章：本周建议功能

### 3.1 交互流程

```
进入 /study 或 /work 后：

═══════════════════════════════════════════════════
  学习规划模式  （输入 exit 退出；/web on 开启联网）
═══════════════════════════════════════════════════
  [OK] KG 已加载 · 130 条活跃节点

  本次主题（一句话描述，回车跳过建议直接对话）：
  > 我想系统学一下 React
                        ↓ AI 独立调用，不占对话历史
  ──────────────────────────────────────────
  本周建议（基于你的认知画像）

  [1] 从 useState 的心智模型切入，不要从 JSX 语法开始
      → 你倾向速通，先抓住「状态驱动视图」这一个核心
        比通读文档节省 60% 时间
  [2] 第一周只看官方教程的前 3 节，刻意跳过「高级 Hook」
      → 根据你的完成任务后过度自责模式，设小里程碑
        比设大目标更能维持动力
  ──────────────────────────────────────────
  回车继续对话，或直接输入你的问题：
  >
```

用户输入主题后 → AI 调用（独立，不进 messages 历史）→ 展示建议 → 等待继续

---

### 3.2 「跳过」机制

| 用户行为 | 系统行为 |
|----------|----------|
| 直接回车（不输入主题）| 跳过建议，直接进入对话，提示「直接开始对话」 |
| 输入主题 | 生成建议后等用户回车或直接输入问题 |
| 输入主题后直接回车 | 建议已展示，继续对话 |

关键设计：**建议的 AI 调用独立，不写入 messages 列表**。这样建议内容不会污染后续对话上下文，也不会增加 token 消耗。

---

### 3.3 建议生成的 Prompt

```python
_SUGGESTION_SYSTEM = """\
你是明翰的{mode_name}，根据他的认知画像和本次主题，给出 2-3 条具体的本周建议。

要求：
- 每条建议必须引用 KG 中的具体模式（不能泛泛而谈）
- 建议要可执行，有具体的行动颗粒度
- 不超过 3 条，每条 2-3 行
- 格式：[序号] 建议标题 \n → 引用的 KG 模式 + 行动理由

如果主题太模糊无法给出有价值的建议，输出「需要更多信息：[具体问什么]」
"""

def generate_suggestion(topic: str, config: dict, client, web_search: bool = False) -> str:
    kg_summary = build_kg_summary()
    user_msg = f"本次主题：{topic}\n\n{kg_summary}"
    tools = _get_tools(web_search)          # 第四章详述
    resp = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=_SUGGESTION_SYSTEM.format(mode_name=config["mode_name"]),
        tools=tools,
        messages=[{"role": "user", "content": user_msg}],
    )
    return resp.content[0].text.strip()
```

`max_tokens=600` 足够输出 2-3 条建议，不过多消耗。

---

### 3.4 进入流程伪代码

```python
def run(trigger_context="", file_content=""):
    # 1. 初始化
    system_prompt = build_system_prompt(config, file_content)

    # 2. Context intake
    print("本次主题（回车跳过建议）：")
    topic = input("> ").strip()

    # 3. 本周建议（可跳过）
    if topic:
        print("\n  [生成本周建议...]\n")
        suggestion = generate_suggestion(topic, config, client, web_search=False)
        print(_format_suggestion_box(suggestion))
        input("  回车继续对话：")   # 等用户确认再进对话

    # 4. 标准对话循环
    messages = conversation_loop(config, system_prompt, client, trigger_context)

    # 5. 退出时提取 pending
    extract_and_write_pending(messages, client, config)
```

---

### 3.5 本章遗留问题

**问题：topic 输入和建议展示之间的等待**

`input("回车继续对话：")` 在 CLI 里是阻塞等待，可以接受。但 UI 里这变成「建议卡片 + 继续按钮」，需要 UI 层处理这个中断。**记录下来，UI 开发时注意。**

**问题：建议是否应该写入某处存档？**

目前设计是一次性展示，不存档。如果用户以后想回看「上次 /study 的建议」，需要另外设计。现在先不做，等有明确需求再加。

---

## 第四章：联网功能设计

### 4.1 设计原则

联网不自动触发，完全由用户主动开启，和元宝/Gemini 的联网开关一致。CLI 里用命令切换，前端 UI 用 toggle 按钮。

---

### 4.2 Anthropic 原生 web_search 工具

Anthropic 直连 API（非 AWS Bedrock）支持原生 web_search 工具，工具类型标识为 `web_search_20250305`。接入方式和现有 Tool Use 完全相同，不需要外部搜索 API key：

```python
WEB_SEARCH_TOOL = {"type": "web_search_20250305"}

def _get_tools(web_search: bool = False) -> list:
    tools = list(SPECIALIST_TOOLS)   # retrieve_memory（只读 KG）
    if web_search:
        tools.append(WEB_SEARCH_TOOL)
    return tools
```

> ⚠️ **注意**：`web_search_20250305` 仅支持 Anthropic 直连 API，不支持通过 AWS Bedrock 调用。本系统使用直连 API，不受影响。实现前建议在 Anthropic 文档确认当前最新工具版本号。

> **重要：server-side tool 不需要客户端 dispatch**  
> `retrieve_memory` 是客户端工具（client-side），AI 返回 `tool_use` block 后，`conversation_loop` 需要执行本地函数并把 `tool_result` 发回 API，再发起下一轮调用。  
> `web_search_20250305` 是 **server-side tool**，搜索由 Anthropic 基础设施在服务端完成，结果直接注入模型上下文，客户端不会收到需要处理的 `tool_use` block，也**不需要**写任何 tool_result 回送逻辑。`conversation_loop` 的 tool dispatch 只处理 `retrieve_memory` 即可，无需为 web_search 添加分支。

---

### 4.3 CLI 切换方式

在专项模式对话中，用户可以随时输入命令切换：

```
你: /web on
  [联网已开启] 下一条回复将使用实时搜索

你: /web off
  [联网已关闭]
```

`conversation_loop()` 内部处理这两个命令，不传入 messages，不发给 AI：

```python
# conversation_loop 内部
if user_input.lower() == "/web on":
    web_search = True
    print(f"  {_GREEN}[联网已开启]{_RESET}")
    continue
if user_input.lower() == "/web off":
    web_search = False
    print(f"  {_GRAY}[联网已关闭]{_RESET}")
    continue
```

`web_search` 是 loop 内的局部变量，每次 AI 调用时动态传入 `_get_tools(web_search)`。

---

### 4.4 前端 toggle 传递方式

前端 UI 的联网开关本质上是控制 `web_search` 这个布尔值：

```python
# 前端启动专项模式时传入
study_planner.run(
    trigger_context=...,
    file_content=...,
    web_search=True   # 来自前端 toggle 的初始状态
)
```

前端每次发消息时也可以附带这个状态（如果允许用户在对话中间切换 toggle），`conversation_loop` 接受外部的 `web_search` 参数更新即可。

---

### 4.5 联网对 token 消耗的影响

web_search 每次触发会额外消耗搜索结果 token（通常 1000-3000 token/次），且计费方式与普通 token 相同。

**控制策略**：
- 联网默认关闭，用户手动开启
- AI 调用时不强制要求每次都搜索；由模型自行判断何时触发
- 建议生成（`generate_suggestion`）时如果开联网，搜索一次行业趋势即可，不需要每轮搜索

---

### 4.6 本章遗留问题

**问题：联网 + 本周建议的组合**

如果用户进入模式时联网是关闭的，建议基于 KG 生成。进入对话后开启联网，后续对话可以搜索实时信息。这个流程没问题。

但如果用户想「开联网后重新生成建议」，目前设计不支持（建议只在进入时生成一次）。**暂不支持，如有需求再加。**

**问题：web_search 工具版本号管理**

`web_search_20250305` 是版本化的，Anthropic 可能会更新版本号。建议把工具标识定义为常量放在文件顶部，方便以后修改：

```python
WEB_SEARCH_TOOL_VERSION = "web_search_20250305"
```

---

## 第五章：文件与内容注入

### 5.1 两种输入方式

| 方式 | 使用场景 | 实现 |
|------|----------|------|
| `/switch study --file path/to/doc.md` | 进入前已知要分析哪个文件 | 解析 `--file` 参数，读取后注入 system prompt |
| 对话中直接粘贴 | 随时补充材料，内容较短 | 无需改动，直接进 messages |

大多数情况下，粘贴文本就够用了。`--file` 主要针对「进入前就知道要看哪个文件」的场景（比如 `/switch study --file ~/syllabus.pdf`）。

---

### 5.2 --file 参数解析

`/switch study --file ~/Downloads/react_book_ch1.md` 这条命令需要在 `cyber_planner.py` 里解析：

```python
# cyber_planner.py 主循环中
if user_input.lower().startswith("/switch "):
    parts = user_input[8:].strip().split("--file")
    mode = parts[0].strip().lower()         # "study"
    file_path = parts[1].strip() if len(parts) > 1 else ""
    file_content = _load_file_content(file_path) if file_path else ""
    switched = handle_switch(mode, messages, file_content=file_content)
```

`handle_switch` 再把 `file_content` 传给 `study_planner.run()`。

---

### 5.3 文件加载函数

```python
def _load_file_content(path_str: str) -> str:
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        print(f"  [警告] 文件不存在：{path}")
        return ""

    suffix = path.suffix.lower()

    if suffix in (".txt", ".md"):
        text = path.read_text(encoding="utf-8")

    elif suffix == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                pages = pdf.pages[:30]           # 最多 30 页
                text = "\n".join(p.extract_text() or "" for p in pages)
        except ImportError:
            print("  [警告] 需要安装 pdfplumber：pip install pdfplumber")
            return ""

    else:
        print(f"  [警告] 不支持的文件格式：{suffix}（支持 .txt .md .pdf）")
        return ""

    # 截断
    MAX_CHARS = 8000
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
        print(f"  [提示] 文件较长，已截取前 {MAX_CHARS} 字符")

    return text.strip()
```

**截断阈值 8000 字符**的理由：约 2000 token，加上 KG 摘要（约 500 token）和 system prompt 本体（约 300 token），总 system prompt 控制在 3000 token 以内，不影响对话轮次的 token 预算。

---

### 5.4 支持格式与限制

| 格式 | 支持 | 备注 |
|------|------|------|
| `.txt` | ✓ | 直接读取 |
| `.md` | ✓ | 直接读取 |
| `.pdf` | ✓（文字型）| 需要 `pdfplumber`，图片型 PDF 无法提取文字 |
| `.epub` | ✗ | 暂不支持 |
| `.docx` | ✗ | 暂不支持 |
| URL | ✗ | 暂不支持，后续可用 web_search 替代 |

`pdfplumber` 是可选依赖，不影响核心功能。如果未安装，提示用户安装，不崩溃。

---

### 5.5 本章遗留问题

**问题：PDF 超过 30 页时提示策略**

目前是静默截断 + 提示。更好的方案是让用户自己选「读第几页到第几页」，但这增加了复杂度。先用截断，等有明确痛点再改。

**问题：前端文件上传的对应关系**

CLI 的 `--file path` 在前端变成「文件上传组件」，上传后内容作为 `file_content` 参数传入。前端不需要改后端逻辑，只需在调用 `run()` 时传入文件内容字符串即可。这是前端和后端的接口约定，**记录到第七章修改点里**。

---

## 第六章：study_planner 与 work_planner 具体设计

### 6.1 study_planner.py

**System Prompt Body**：

```
你是赛博明翰的学习规划师，不是通用学习 AI。
你了解这个人的认知习惯和行为模式，制定的计划必须贴合他的真实性格。

## 你的核心能力
- 把复杂的学习目标拆解成与明翰认知风格匹配的具体步骤
- 识别哪些内容对他来说「高价值」，帮他跳过低价值部分
- 在他容易卡住或逃避的节点提前设计缓冲机制
- 结合当前材料（如有）给出具体的「从哪里开始」建议

## 说话风格
直接、具体，引用明翰的 KG 模式时说清楚是哪层哪个节点。
不说「你可以尝试」，说「建议你这周做 X，因为你有 Y 模式」。
```

**extract_focus（注入 _EXTRACT_SYSTEM_TEMPLATE）**：

```
- 用户描述了对某个知识点的态度（觉得难/觉得有趣/想跳过）
- 用户表现出学习节奏偏好（喜欢一口气学完 / 喜欢分段）
- 用户描述了遇到卡点时的反应（放弃、查资料、找人问）
- 用户对「值不值得学」的判断倾向
- 用户在规划讨论中表现出的完美主义或完成主义倾向
```

**入口**：

```python
STUDY_CONFIG = {
    "mode_name":      "学习规划",
    "mode_key":       "study",
    "ai_role_name":   "学习规划师",
    "context_prompt": "本次想学什么？（一句话描述，回车跳过建议）",
    "system_prompt_body": _STUDY_SYSTEM_BODY,
    "extract_focus":  _STUDY_EXTRACT_FOCUS,
}

def run(trigger_context: str = "", file_content: str = "", web_search: bool = False):
    from specialist_base import run as base_run
    base_run(STUDY_CONFIG, trigger_context, file_content, web_search)
```

---

### 6.2 work_planner.py

**System Prompt Body**：

```
你是赛博明翰的工作规划助手，不是通用项目管理 AI。
你了解他在压力下的行为模式，帮他做出他真正能执行的计划，而不是理论上完美的计划。

## 你的核心能力
- 帮他梳理本周任务优先级，考虑他的实际精力分布
- 识别他容易拖延的任务类型，提前设计触发机制
- 在他描述工作困境时，从 KG 中找到相关模式并给出针对性策略
- 识别当前工作中可能需要补充的技能点

## 说话风格
直接、务实，不给执行成本极高的建议。
引用 KG 模式时说清楚来源。不做道德评判（不说「你应该更自律」）。
```

**extract_focus**：

```
- 用户描述了任务拖延的触发场景（什么情况下开始拖）
- 用户表现出对某类工作的回避倾向
- 用户描述了高效工作时的状态或条件
- 用户对截止日期压力的反应模式
- 用户提到的工作中反复出现的摩擦点（总是卡在哪一步）
```

**入口**：与 study_planner 结构完全相同，替换 config 即可。

---

### 6.3 两个模式的差异汇总

| 维度 | /study | /work |
|------|--------|-------|
| 核心问题 | 怎么学 + 学什么顺序 | 怎么做 + 做什么优先 |
| context_prompt | 想学什么 | 本周在做什么 |
| AI 侧重 | 知识拆解、学习路径 | 任务优先级、执行摩擦 |
| 提取关注 | 学习偏好、知识态度 | 拖延模式、工作习惯 |
| 文件用途 | 课程大纲、技术文档 | 项目需求、任务清单 |

---

### 6.4 本章遗留问题

**问题：两个模式的 system prompt 是否需要访问对应的「协议文件」？**

health_coach 有 `bio_baseline_final.md`（58 条 SOP 规则）。/study 和 /work 暂时没有对应的协议文件，完全靠 KG + LLM 知识。等使用一段时间积累了足够的领域规则，再考虑是否蒸馏成协议文件（走 hitl_review.py 流程）。**当前：不做，留接口（`protocol_path` 字段在 config 里留空即可）。**

**问题：/work 的「技能缺口发现」需要了解当前工作内容**

这个信息只在当前对话里存在，不在 KG 里。所以技能推荐的质量完全依赖用户在 context intake 里说了多少。如果用户只说「我在做一个 web 项目」，建议会很泛。如果说「我在用 React 做一个带权限管理的后台，卡在路由守卫这里了」，建议会非常精准。这是设计的固有限制，用 context_prompt 的措辞引导用户多说一些。

---

## 第七章：cyber_planner.py 修改点

### 7.1 _MODE_MAP 新增两个入口

```python
# cyber_planner.py 顶部，当前：
_MODE_MAP = {
    "health": "health_coach",
}

# 修改后：
_MODE_MAP = {
    "health": "health_coach",
    "study":  "study_planner",
    "work":   "work_planner",
}
```

这一行改动让 `/switch study` 和 `/switch work` 自动生效，`importlib.import_module` 会加载对应模块。

---

### 7.2 handle_switch() 签名扩展

当前 `handle_switch(mode, messages)` 不支持传递 `file_content` 和 `web_search`。需要扩展：

```python
# 当前签名：
def handle_switch(mode: str, messages: list) -> bool:

# 修改后：
def handle_switch(mode: str, messages: list,
                  file_content: str = "",
                  web_search: bool = False) -> bool:
```

内部调用 `module.run()` 时把这两个参数传进去：

```python
# 当前：
module.run(trigger_context=trigger_context)

# 修改后：
module.run(
    trigger_context=trigger_context,
    file_content=file_content,
    web_search=web_search,
)
```

health_coach.run() 的签名也需要加上这两个参数（加默认值，不影响现有调用）：

```python
# health_coach.py
def run(trigger_context: str = "",
        file_content: str = "",     # 新增，暂不使用
        web_search: bool = False):  # 新增，暂不使用
```

---

### 7.3 主循环 /switch 命令解析扩展

当前主循环只解析模式名：

```python
# 当前：
if user_input.lower().startswith("/switch "):
    mode = user_input[8:].strip().lower()
    switched = handle_switch(mode, messages)
```

修改为支持 `--file` 参数：

```python
if user_input.lower().startswith("/switch "):
    raw = user_input[8:].strip()
    file_content = ""
    if "--file" in raw:
        parts = raw.split("--file", 1)
        mode = parts[0].strip().lower()
        file_content = _load_file_content(parts[1].strip())
    else:
        mode = raw.lower()
    switched = handle_switch(mode, messages, file_content=file_content)
    if switched:
        break
    continue
```

`_load_file_content()` 定义在 `cyber_planner.py`（或可以 import 自 `specialist_base.py`）。

---

### 7.4 前端接口约定（供 UI 开发参考）

前端调用专项模式时，不经过 `/switch` 命令解析，而是直接调用 `run()`：

```python
import study_planner
study_planner.run(
    trigger_context="来自主对话的上下文摘要",
    file_content="用户上传的文件内容（字符串）",
    web_search=True,   # 来自前端 toggle 状态
)
```

`file_content` 由前端文件上传组件处理后传入，格式统一为 UTF-8 字符串，长度建议前端侧也做 8000 字符的截断提示。

---

### 7.5 改动影响评估

| 文件 | 改动类型 | 回归风险 |
|------|----------|----------|
| `cyber_planner.py` | `_MODE_MAP` 加两行，`handle_switch` 加参数 | 低，现有 health 路径不受影响 |
| `health_coach.py` | `run()` 加两个默认参数 | 极低，完全向后兼容 |
| 新建 `specialist_base.py` | 全新文件 | 无 |
| 新建 `study_planner.py` | 全新文件 | 无 |
| 新建 `work_planner.py` | 全新文件 | 无 |

---

### 7.6 本章遗留问题

**问题：`_load_file_content` 放哪里？**

选项 A：放 `cyber_planner.py`（调用方），解析逻辑集中  
选项 B：放 `specialist_base.py`（使用方），随基座一起分发

**→ 决定：选项 A，`_load_file_content` 放 `cyber_planner.py`。**

原因：`specialist_base.py` 需要 import `CyberBrainStore`（定义在 `cyber_planner.py`）；如果 `cyber_planner.py` 同时 import `specialist_base`，会形成循环依赖，Python 启动时报错。选项 A 把文件加载放在调用侧（`cyber_planner.py`），不产生任何新的 import 关系，是最简洁的解法。

`cyber_planner.py` 只负责解析 `--file` 参数字符串并加载内容，将结果字符串传入 `run()`；`specialist_base.py` 只接收 `file_content: str`，不关心文件从哪里来。

---

## 第八章：验收测试设计

### 8.1 自动化测试（pipelines/test_specialist_modes.py）

**T1 — specialist_base.build_system_prompt()**

```python
config = STUDY_CONFIG
prompt = build_system_prompt(config, file_content="测试材料内容")
assert "学习规划师" in prompt
assert "明翰心智图谱" in prompt
assert "测试材料内容" in prompt
assert "retrieve_memory" in prompt
```

**T2 — extract_pending() 提取学习模式**

mock 一段包含「遇到难点就想放弃」的对话，验证提取结果含该观察，且 `raw_evidence` 非空。

**T3 — _load_file_content() 文件加载**

- `.txt` 文件正常加载
- 不存在的路径返回 `""` 并打印警告，不报错
- 超过 8000 字符的文件被截断，打印提示

**T4 — _get_tools() toggle 逻辑**

```python
tools_off = _get_tools(web_search=False)
tools_on  = _get_tools(web_search=True)
assert len(tools_on) == len(tools_off) + 1
assert any("web_search" in str(t) for t in tools_on)
```

---

### 8.2 手动验收测试

**M1 — /switch study 基本流程**

```
python3 cyber_planner.py
> /switch study
（确认 Y）
本次主题: 我想学习 React Hooks
（观察：生成本周建议，内容引用了 KG 模式）
（继续对话 2 轮）
exit → Y
（观察：打印「正在提取观察记录...」，写入 N 条）
```

验证点：
- 进入时打印「学习规划模式」标题
- 本周建议出现，内容具体（不泛泛而谈）
- 退出后 pending.jsonl 有新条目，source_mode = "study"

**M2 — 跳过本周建议**

进入后直接回车不输入主题 → 验证：跳过建议，直接进入对话

**M3 — --file 注入**

```
> /switch study --file ~/Desktop/某课程大纲.md
```
验证：AI 的建议引用了文件中的内容

**M4 — /web on 联网切换**

进入 /study 后：
```
你: /web on
（观察：打印「联网已开启」）
你: React 最近有什么新进展？
（观察：AI 回复包含实时信息）
你: /web off
```

**M5 — /switch work 独立验证**

与 M1 类似，验证 work_planner 的 context_prompt 是「本周在做什么」，提取内容包含工作行为观察。

**M6 — extract_pending → batch_processor → /review 全链路**

进入 /study 对话，讨论「我总是把简单任务推到最后做」→ 退出 → `python3 pipelines/batch_processor.py` → `/review` 里出现这条观察，路由到 KG。

---

### 8.3 验收通过标准

| 测试 | 通过条件 |
|------|----------|
| T1-T4 | 自动化全部通过 |
| M1 | 建议内容引用至少 1 个 KG 节点 |
| M2 | 跳过后无 AI 调用延迟，直接对话 |
| M3 | AI 回复明确引用文件内容 |
| M4 | 联网后能回答「最新动态」类问题 |
| M5 | work 模式的提取内容路由正确 |
| M6 | 全链路跑通，新节点出现在 /kg 里 |

---

### 8.4 开发顺序建议

1. `specialist_base.py` → 跑通 T1-T4
2. `study_planner.py` 最小版本（只有 config + run 入口）→ M1、M2
3. `cyber_planner.py` 修改（_MODE_MAP + handle_switch）
4. `--file` 参数解析 + `_load_file_content` → M3
5. 联网 toggle → M4
6. `work_planner.py`（复用 study 的结构）→ M5
7. 全链路测试 → M6

每一步都可以独立验收，不需要等到全部完成。

---

## 附录：跨章节遗留问题汇总

| 来源 | 问题 | 建议处理时机 |
|------|------|-------------|
| 第三章 | 本周建议不存档，用户无法回看 | 有需求再加 |
| 第三章 | 联网开启后无法重新生成建议 | 有需求再加 |
| 第四章 | web_search 工具版本号需定期核查 | 实现前核查一次 |
| 第五章 | PDF 超出 30 页的截断策略可改进 | 有痛点再改 |
| 第六章 | study/work 暂无协议文件（SOP 规则）| 积累数据后用 hitl_review.py 蒸馏 |
| 第七章 | `_load_file_content` 定义在 specialist_base，cyber_planner import 时注意路径 | 实现时确认 |
