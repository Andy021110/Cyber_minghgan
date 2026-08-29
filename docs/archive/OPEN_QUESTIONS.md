# 执行 Agent 上报问题日志

> 所有执行 Agent（2/3/4）在工作中遇到 TECH_SPEC 未覆盖、存在歧义、或需要产品决策的问题，按以下模板追加到本文件。  
> Agent 1（架构师 = 用户 + Claude）负责监看并解答，解答后同步更新 TECH_SPEC.md。

---

## 上报模板

```
## Q{编号} [{提交 Agent}] [{日期}]
**问题**：一句话描述不确定的内容
**背景**：为什么会遇到这个问题，在哪个任务中
**我的猜测**：如果必须现在做决定，我会怎么做（可选）
**影响范围**：这个问题影响哪些后续任务
**紧急程度**：高（阻塞当前任务）/ 中（影响后续任务）/ 低（优化项）
**状态**：⏳ 待解答
```

解答后，Agent 1 将状态改为 `✅ 已解答`，并附上结论和 TECH_SPEC 更新位置。

---

## 问题记录

## Q1 [Agent 3] [2026-06-08]
**问题**：`main.js` 使用 `parent: 'game-container'`，但 TECH_SPEC 未说明 Agent 4 的 `index.html` 需要满足哪些 HTML 结构要求。  
**背景**：G1 实现 `main.js` 时，Phaser 配置写了 `parent: 'game-container'`（指定 canvas 挂载点）；同时 Phaser 以 CDN `<script>` 标签引入，必须在 ES Module 之前加载，否则模块执行时 `Phaser` 全局变量尚未就绪。TECH_SPEC 第六章 6.2 只说 `index.html` 归 Agent 4，未列出这两条要求。  
**我的猜测**：Agent 4 在写 `index.html` 时需要：  
  1. `<script src="https://cdn.jsdelivr.net/npm/phaser@3/dist/phaser.min.js"></script>` 放在所有 ES Module 之前  
  2. `<div id="game-container"></div>` 作为 canvas 容器  
  3. `<script type="module" src="game/main.js"></script>` 放在 Phaser script 之后  
**影响范围**：Agent 4 实现 `index.html`；若容器 id 不一致，Phaser 会将 canvas 挂到 `document.body` 而非预期位置，可能导致 z-index 层级错乱。  
**紧急程度**：低（Agent 3 工作已完成，不阻塞当前任务；仅在 Agent 4 开始写 index.html 前需要确认）  
**状态**：⏳ 待解答

---

## Q2 [Agent 3] [2026-06-08]
**问题**：GymScene（以及未来各专项场景）是否需要与 WorldScene 一样实现 EventBus 接收侧（`cyber:panel:opened` → 禁输入，`cyber:panel:closed` → 恢复输入）？  
**背景**：G6 任务明确说「WorldScene.js 中的事件监听逻辑」，我只在 WorldScene 实现了 EventBus 接收侧。但 GymScene 有健康管家 NPC 和两个物件的 INTERACT 触发区——Agent 4 响应这些触发后会开面板并发 `cyber:panel:opened`，GymScene 目前没有监听，玩家在面板打开时仍可自由移动。  
**我的猜测**：每个有 INTERACT 触发区的场景都需要实现相同的 EventBus 接收侧。可以抽取一个 `setupSceneEventBus(scene, player)` 工具函数，WorldScene 和 GymScene 各调用一次。  
**影响范围**：GymScene 的玩家输入控制；未来 OfficeScene / StudyScene（Phase 2）；是否需要新建共享工具函数。  
**紧急程度**：中（GymScene 功能完整性问题，Agent 4 开始接入面板前需要解决）  
**状态**：⏳ 待解答

---

## Q3 [Agent 3] [2026-06-08]
**问题**：Phase 2 门洞的「即将开放」提示，应该在 Phaser canvas 层显示，还是通过 EventBus 通知 HTML 层显示？  
**背景**：G5 验收标准说「Phase 2 门洞的 PROXIMITY 触发显示「即将开放」提示，不发送 `cyber:door:approach`」。Agent 3 不能写 HTML 面板，所以我在 TriggerSystem 的 `_showHint()` 里用 `scene.add.text()` 直接在 canvas 上显示一个 1.8 秒临时文字。这能工作，但与「HTML 层负责所有提示 UI」的分层原则有轻微冲突。  
**我的猜测**：这个提示属于「游戏世界内的反馈」（玩家走进了一个封闭门洞），放在 canvas 层更合适，无需 HTML 层参与。若需统一，可以新增一个 `cyber:door:phase2` 事件让 Agent 4 处理。  
**影响范围**：TriggerSystem `_showHint()` 实现；若改为 EventBus 方式则需 Agent 4 新增监听器；需确认是否新增事件名（第四章合同变更需走上报）。  
**紧急程度**：低（当前实现功能正确，仅架构风格问题）  
**状态**：⏳ 待解答

---

## Q4 [Agent 4] [2026-06-08]
**问题**：`POST /api/chat` 的 `npcId` 字段目前未做分发——所有 npcId 均使用赛博明翰的 system prompt 和同一条对话历史。Phase 1 的健康管家 NPC（`npcId: "health_coach"`）触发对话时，应该走哪条后端路径？
**背景**：实现 B7 时，`process_message()` 读取 `_CHAT["system_prompt"]`，该值在 `api/main.py` 启动时被设为赛博明翰人设（`build_system_prompt()`）。项目中已存在 `health_coach.py`，有独立的 `run()` 和专属 system prompt，但它是 CLI 模式，未被封装为 API 函数。TECH_SPEC 5.2 只说"对应后端逻辑：CyberBrainStore 的对话核心"，未说明不同 npcId 是否使用不同逻辑。
**我的猜测**：有两种方案——①Phase 1 仅 `cyber_minghan` 实现真实对话，`health_coach` 也复用同一 `process_message()`（前端用 `contextHint` 注入健康上下文，不换 system prompt）；②按 `npcId` 分发，`health_coach` 走独立的 system prompt 或逻辑。方案①简单但健康管家无法体现专属人设；方案②需要 Agent 4 封装 `health_coach.py` 的对话逻辑，属于新增工作量。
**影响范围**：B7 `/api/chat` 路由、前端 F3 面板调用逻辑、未来 Phase 2 新 NPC 的接入方式。
**紧急程度**：中（Phase 1 GymScene 健身房功能完整性；在 Agent 3 与 Agent 4 联调前需要结论）
**状态**：⏳ 待解答

---

## Q5 [Agent 4] [2026-06-08]
**问题**：API 模式下反刍引擎提取到新特征后，是否应自动写入 KG，还是需要某种授权机制？  
**背景**：实现 B7 `_auto_reflect()` 时，CLI 的 `_reflection_cycle()` 会在终端弹出"是否写入图谱？(Y/N)"由用户确认；但 API 模式下没有终端，我直接调用 `store.create()` 写入，无需任何授权。TECH_SPEC 5.2 只说"每 REFLECT_EVERY 轮触发一次，yield `[REFLECTION_TRIGGERED]`"，未说明 API 模式是否保留用户授权环节。  
**我的猜测**：MVP 单用户场景下自动写入是合理的——游戏面板可以通过已有的"待审批"或"通知"机制在事后告知用户（但目前代码里没有这个通知）。若需严格保留人类授权，可以把反刍结果先写进 awaiting_approval 队列，交前端 Review 面板审批，而不是直接落 KG。  
**影响范围**：`api/routes/chat.py` `_auto_reflect()`；`cyber_planner.py` `process_message()`；前端 Review 面板（F5）是否需要承接反刍结果；KG 数据质量（自动写入可能引入低质量特征节点）。  
**紧急程度**：中（影响 KG 数据质量和用户对图谱的信任感；F5 Review 面板开发前需要结论）  
**状态**：⏳ 待解答

---

## Q6 [Agent 4] [2026-06-08]
**问题**：`GET /prune/candidates` 应返回全部非归档节点（含 healthy），还是只返回超过老化阈值的候选节点？  
**背景**：CLI `scan_candidates()` 只返回 `staleness >= threshold` 的节点；我实现的 `get_prune_candidates()` 返回全部非归档节点并附 `severity`（critical/warning/healthy）标签。判断依据是前端 Prune 面板需要展示分布全貌，以便用户做对比决策。但这导致 API 响应体可能很大，且和 CLI 行为不一致。  
**我的猜测**：保持全量返回更利于前端可视化（力导向图、健康仪表盘）；若担心数据量，可加 `?severityFilter=critical,warning` 查询参数做过滤。  
**影响范围**：`cyber_planner.get_prune_candidates()` 实现；`api/routes/prune.py`；前端 F7 Prune 面板的数据展示逻辑；响应体大小。  
**紧急程度**：低（当前实现功能可用，仅影响 F7 面板设计决策）  
**状态**：⏳ 待解答

---

## Q7 [Agent 4] [2026-06-08]
**问题**：`api/main.py` CORS 仅允许 `http://localhost:3000` 和 `http://127.0.0.1:3000`，但 TECH_SPEC 提到"允许所有端口"——实际前端开发端口是多少？  
**背景**：TECH_SPEC 描述 CORS 时说"允许所有端口"，我出于安全考虑收紧为只允许 3000 端口。但若 Agent 3 的 Phaser 前端用其他端口启动（如 Vite 默认 5173、http-server 默认 8080），跨域请求会被拒绝，导致前后端联调失败。  
**我的猜测**：本地开发阶段可以临时改为 `allow_origins=["*"]` 或把常见端口都加进去；正式联调前需要 Agent 3 确认前端服务端口。  
**影响范围**：`api/main.py` CORS 配置；Agent 3 前端 `client.js` 的 API_BASE_URL；前后端联调能否正常工作。  
**紧急程度**：高（前后端联调阶段直接阻塞；在 F10 EventBus 集成和 USE_MOCK → false 切换前必须确认）  
**状态**：⏳ 待解答

---

## Q8 [Agent 4] [2026-06-08]
**问题**：`boost_node_importance` 是否应该同时重置 `last_accessed_at`（老化计时归零），还是只更新 importance？  
**背景**：实现 B4 `boost_node_importance()` 时，我参照 CLI `handle_prune()` 的行为（提升重要度时打印"老化计时重置"），在 `store.update()` 中同时传入 `last_accessed_at=now`。TECH_SPEC 对该纯函数的描述只说"更新 importance"，未提及是否附带重置访问时间。这两种行为的语义不同：单纯提升 importance 下次仍可能老化；同时重置计时则相当于"标记为近期激活"，老化计时从头开始。  
**我的猜测**：同时重置更符合"保留节点"的语义——既然决定提升重要度，说明该节点仍有价值，老化计时应归零。但这是一个产品决策，影响 KG 老化模型的准确性。  
**影响范围**：`cyber_planner.boost_node_importance()` 实现；`api/routes/prune.py` `POST /prune/{node_id}/boost`；前端 F7 面板的"保留"操作语义说明。  
**紧急程度**：低（当前行为与 CLI 一致，F7 开发前确认即可）  
**状态**：⏳ 待解答

---

## Q9 [Agent 4] [2026-06-08]
**问题**：`client.js` 的 `chatStream` 函数签名是否需要包含 `npcId` 和可选的 `contextHint` 参数？  
**背景**：TECH_SPEC F2 任务描述中写的是 `chatStream(message, onToken, onDone, onReflection)` 四参数签名，但 `/api/chat` 的请求体要求包含 `npcId`（不同 NPC 需要传不同 id）。同时 F3 明确要求："若触发来源是 `cyber:object:interact`（有 `contextHint` 字段），打开对话框时将 `contextHint` 作为本轮对话的系统提示前缀，连同用户消息一起传给 `client.chatStream()`"——这意味着 `chatStream` 还需要接受 `contextHint`。  
**我的猜测**：将签名扩展为 `chatStream(npcId, message, onToken, onDone, onReflection, contextHint = null)`，其中 `contextHint` 为可选末尾参数。在实现中，若 `contextHint` 存在，则拼接为 `[${contextHint}]\n${message}` 传给后端（因为 `/api/chat` 没有独立的 `contextHint` 字段）。  
**影响范围**：`frontend/client.js` 函数签名；`frontend/panels/dialogue.js`（F3）调用侧；若签名确认，F3 开发直接使用，无需再议。  
**紧急程度**：中（F3 对话框面板开发前需要确认，以避免后续接口变更）  
**状态**：⏳ 待解答

---

## Q10 [Agent 4] [2026-06-08]
**问题**：对话框面板有两处行为未在 TECH_SPEC 中明确，需要产品确认：①`contextHint` 是否只注入首条消息；②重新打开面板是否清空历史消息。  
**背景**：F3 实现中做出了以下两个判断：  
①`contextHint`（来自物件交互）在用户发送第一条消息后即清空（`_state.contextHint = null`），之后的消息不再携带。TECH_SPEC 2.3 说"将 contextHint 作为本轮对话的系统提示前缀"，"前缀"暗示只需一次，但不够明确。  
②每次 `_open()` 时清空消息区（`_messages.innerHTML = ''`），即每次打开对话框都是全新对话，不保留上次的聊天记录。服务器端 `_CHAT["messages"]` 在 `DELETE /api/chat/history` 前是持续的，所以前端不清空历史也能保持上下文，但视觉上会显示很长的历史列表。  
**我的猜测**：①contextHint 只注入一次更符合"上下文提示"的语义，避免每条消息都带上重复前缀。②清空消息区是合理的 UX——每次打开像开启新话题，配合 `DELETE /api/chat/history` 可以让服务器端也清空。但若希望玩家能看到上一次的对话记录，则不应清空。  
**影响范围**：`panels/dialogue.js` `_open()` 和 `_send()` 行为；是否需要在 `_open()` 时同时调用 `clearChatHistory()`。  
**紧急程度**：低（当前实现功能完整，联调前确认即可）  
**状态**：⏳ 待解答

---

## Q11 [Agent 4] [2026-06-08]
**问题**：`/kg` 和 `/prune` 面板缺少触发入口——TECH_SPEC 第四章 EventBus 事件表中没有任何事件会触发这两个面板打开，它们应该如何被用户访问？  
**背景**：实现 F6（kg.js）和 F7（prune.js）时发现，TECH_SPEC 第四章的 Phaser→HTML 事件清单里没有 `cyber:kg:open` 或 `cyber:prune:open` 事件；第二章场景实体表里也没有对应的可交互物件。CLI 中用户通过 `/kg` 和 `/prune` 文本指令访问，但 Web UI 没有对应的入口。目前临时用 `window.openKgPanel()` 和 `window.openPrunePanel()` 作为开发快捷键，正式版需要确定触发方式。  
**我的猜测**：有三种方案：①在 HUD 顶部栏添加两个图标按钮（KG 图谱 / 老化管理），始终可见；②在 WorldScene 增加两个可交互物件（如"数据终端"），走 `cyber:object:interact` 事件；③在对话面板内增加快捷入口按钮。方案①最直观，符合 Web UI 习惯；方案②更"游戏化"，和现有架构一致；方案③最简单但不够显眼。  
**影响范围**：`index.html` HUD HTML 结构（若方案①）；`roomConfig.js` 和 Tilemap（若方案②）；需要新增 EventBus 事件名（若方案②，须更新 TECH_SPEC 第四章）。  
**紧急程度**：中（F10 联调前需要确定，否则 KG 和 Prune 面板无法被正常用户访问）  
**状态**：⏳ 待解答

---

## Q12 [Agent 4] [2026-06-08]
**问题**：从任务板点击某条目打开审批面板时，是从该条目开始处理，还是始终从队列第一条开始？  
**背景**：F5 review.js 实现时，`_openFromTaskboard(startItem)` 接收了被点击的条目，但审批逻辑始终从 `getReviewItems()` 返回的队列第一条开始（`_state.idx = 0`），忽略了 startItem 的位置。原因：若从中间条目开始，剩余条目的顺序会产生歧义（前面的条目是否需要处理？）；始终从第一条开始更简单且与 CLI `/review` 行为一致。  
**我的猜测**：从第一条开始处理更符合"审批队列"的完整性语义。但若用户点击某条目是因为特别关注它，从队列头开始可能让用户困惑（需要先处理其他条目才能到达目标条目）。可以考虑：保留从第一条开始的逻辑，但在面板顶部提示"当前队列共 N 条，从第一条开始"。  
**影响范围**：`panels/review.js` `_openFromTaskboard()` 行为；用户体验。  
**紧急程度**：低（当前实现功能完整，优化可延后）  
**状态**：⏳ 待解答

---

## Q13 [Agent 4] [2026-06-08]
**问题**：F7 Prune 面板的"跳过"操作只从本次会话的本地列表移除候选，不调用任何 API——这是否符合产品预期？  
**背景**：实现 `prune.js` 时，`_onSkip()` 只调用 `_removeCandidate(idx)` 从 `_state.candidates` 移除，不向后端发任何请求。理由是"跳过"语义是"本次不处理"，下次打开 Prune 面板时重新从 API 获取，该节点仍会出现在列表中。对比 CLI `/prune` 的跳过行为（直接在列表里向下翻，不写文件），两者语义一致。但也存在另一种理解：跳过应该有 TTL，例如 7 天内跳过的节点不再提醒（需要后端记录跳过时间戳）。  
**我的猜测**：当前"无状态跳过"实现足够简单，MVP 阶段合理。若需要带 TTL 的跳过，需要在 `prune.py` 或 `CyberBrainStore` 增加 `skipped_until` 字段，属于较大改动。  
**影响范围**：`frontend/panels/prune.js` `_onSkip()` 行为；`api/routes/prune.py`（若需新增 skip endpoint）；`CyberBrainStore` 数据模型（若需 `skipped_until` 字段）。  
**紧急程度**：低（当前实现功能完整，与 CLI 行为一致；可延后至 F10 联调时确认）  
**状态**：⏳ 待解答

---

## Q14 [Agent 4] [2026-06-08]
**问题**：`test_similar_nodes.py` 场景3 存在测试隔离缺陷，导致 CI 会随 KG 内容增长而持续失败——是修复测试，还是接受这个已知失败？  
**背景**：场景3 测试"无关观察（学线性代数）应返回空列表"，但 `find_similar_nodes()` 把真实生产 KG 的所有活跃节点都传给 LLM 做语义判断。生产 KG 中存在节点"探索性本能激活"（描述：以「Hello, world」作为开场，呈现典型的好奇驱力/epistemic drive），LLM 合理地认为"学线性代数"与"探索性本能激活"语义重叠，导致返回非空列表，测试断言失败。测试本身没有创建隔离的临时 KG，而是直接使用 `CyberBrainStore()`（加载生产文件）。该节点大概率是在测试编写后才写入 KG 的，属于 KG 增长导致的测试脆性。  
**我的猜测**：修复方式是让测试使用临时 KG 文件（`tmp_path` + 空 KG 或只含测试节点的 KG），而非直接读生产文件。但这需要重构 `CyberBrainStore` 支持传入自定义路径，或在测试中 monkey-patch `KG_PATH`。另一种轻量方案：接受该场景为"已知的 LLM 行为差异"，在测试里加 `[KNOWN_FLAKY]` 注释并跳过断言。  
**影响范围**：`pipelines/test_similar_nodes.py` 场景3；若修复则涉及 `CyberBrainStore` 初始化接口；不影响任何生产代码。  
**紧急程度**：低（生产功能正常，仅测试套件有一条红；KG 节点语义覆盖越宽，未来类似失败会越多）  
**状态**：⏳ 待解答
