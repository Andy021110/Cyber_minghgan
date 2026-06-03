"""
generate_viz.py
赛博明翰认知图谱可视化生成器
"""

import json
import sys
from pathlib import Path

KG_PATH  = Path(__file__).parent.parent / "yuanbao_cyber_minghan_kg.json"
OUT_PATH = Path(__file__).parent.parent / "docs" / "cyber_minghan_graph.html"


# ══════════════════════════════════════════════════════════════════
#  extract_nodes
# ══════════════════════════════════════════════════════════════════

def extract_nodes(data: dict) -> tuple:
    """
    返回 (vis_nodes, detail_map) 两份数据：
      vis_nodes   — 只含 vis-network 认识的字段
      detail_map  — {id: detail_text}，供右侧面板使用
    """
    vis_nodes  = []
    detail_map = {}
    nid        = 0

    def add(node_dict, detail_text):
        nonlocal nid
        vis_nodes.append(node_dict)
        detail_map[nid] = detail_text
        nid += 1
        return nid - 1   # 返回刚分配的 id

    # ── 根节点 ────────────────────────────────────────────────────
    root_id = add(
        {"id": nid, "label": "Cyber\nMinghan", "group": "root",
         "title": "赛博明翰 · 认知知识图谱中心节点"},
        "赛博明翰（Cyber_Minghan）\n北邮 AI · 港大 CS · INFP · 速通型人格\n\n"
        "本图谱基于弗洛伊德三层动力学结构，对两段完整对话进行批次化认知建模。"
    )

    # ── 三层骨架 + 事件节点 ───────────────────────────────────────
    cm = data.get("nodes", {}).get("Cyber_Minghan", {})
    skeleton_ids = {}

    for layer in ("Id", "Superego", "Ego"):
        items = cm.get(f"{layer}_Dynamics", [])

        skeleton_id = add(
            {"id": nid, "label": f"{layer}\n({len(items)} 条)", "group": layer,
             "title": f"{layer} 层动力学  共 {len(items)} 条事件"},
            f"{layer} 层动力学  共 {len(items)} 条事件\n\n"
            + {"Id":       "快感原则 · 原始冲动 · 本能欲望",
               "Superego": "内化规范 · 道德压力 · 应然焦虑",
               "Ego":      "现实协商 · 防御机制 · 妥协方案"}[layer]
        )
        skeleton_ids[layer] = skeleton_id

        for idx, item in enumerate(items):
            raw = item.get("event_label", f"{layer}事件{idx+1}")
            label = (raw[:12] + "\n" + raw[12:24]) if len(raw) > 12 else raw
            desc     = item.get("description", "")
            evidence = item.get("evidence", "")
            batch_id = item.get("batch_id", "")
            tooltip  = f"[{layer}] {raw}\n批次：{batch_id}\n\n{desc}\n\n原文：{evidence}"
            add(
                {"id": nid, "label": label, "group": layer, "title": tooltip},
                tooltip
            )

    return vis_nodes, detail_map, root_id, skeleton_ids


# ══════════════════════════════════════════════════════════════════
#  extract_edges
# ══════════════════════════════════════════════════════════════════

def extract_edges(data: dict, vis_nodes: list,
                  root_id: int, skeleton_ids: dict) -> list:
    """
    A. 结构边：根→骨架→事件（按 id 顺序推断父子关系）
    B. 互动边：interactions 三元组 → 虚线有向边
    """
    edges = []
    eid   = 0

    # ── A. 结构边 ─────────────────────────────────────────────────
    # 根 → 骨架
    for layer, skel_id in skeleton_ids.items():
        edges.append({"id": eid, "from": root_id, "to": skel_id,
                       "arrows": "to", "width": 2,
                       "color": {"color": "#30363d", "highlight": "#58a6ff"},
                       "smooth": {"type": "dynamic"}})
        eid += 1

    # 骨架 → 事件
    skel_id_set  = set(skeleton_ids.values())
    current_skel = None
    for n in vis_nodes:
        nid = n["id"]
        if nid in skel_id_set:
            current_skel = nid
            continue
        if current_skel is not None and n.get("group") in skeleton_ids:
            edges.append({"id": eid, "from": current_skel, "to": nid,
                           "arrows": "to", "width": 1,
                           "color": {"color": "#21262d", "highlight": "#58a6ff"},
                           "smooth": {"type": "dynamic"}})
            eid += 1

    # ── B. 互动边 ─────────────────────────────────────────────────
    # 按 batch_id 收集各层第一个/最后一个事件节点
    batch_nodes: dict = {}
    for n in vis_nodes:
        if n["id"] in skel_id_set or n["id"] == root_id:
            continue
        # 找批次：从 title 里取 "批次：BatchX"
        batch_tag = ""
        title = n.get("title", "")
        if "批次：" in title:
            batch_tag = title.split("批次：")[1].split("\n")[0].strip()
        key = (batch_tag, n.get("group", ""))
        batch_nodes.setdefault(key, []).append(n["id"])

    for inter in data.get("interactions", []):
        event      = inter.get("event", "")
        trigger    = inter.get("trigger", "")
        resolution = inter.get("resolution", "")
        batch_id   = inter.get("batch_id", "")
        tooltip    = f"互动：{event}\n批次：{batch_id}\n\n触发：{trigger}\n\n结果：{resolution}"

        # from = 该批次 Ego 层首个节点；to = Id 层首个节点
        from_id = next(
            (batch_nodes.get((batch_id, l), [None])[0]
             for l in ("Ego", "Superego", "Id") if batch_nodes.get((batch_id, l))),
            root_id
        )
        to_id = next(
            (batch_nodes.get((batch_id, l), [None])[-1]
             for l in ("Id", "Superego", "Ego") if batch_nodes.get((batch_id, l))),
            root_id
        )
        if from_id == to_id:
            to_id = skeleton_ids.get("Id", root_id)

        edges.append({
            "id": eid, "from": from_id, "to": to_id,
            "arrows": "to",
            "label": (event[:10] + "…") if len(event) > 10 else event,
            "title": tooltip,
            "color": {"color": "#58a6ff", "highlight": "#79c0ff"},
            "width": 2, "dashes": True,
            "smooth": {"type": "curvedCW", "roundness": 0.3},
            "font":  {"color": "#8b949e", "size": 10, "align": "middle"},
        })
        eid += 1

    return edges


# ══════════════════════════════════════════════════════════════════
#  get_html_template
#  占位符（用 .replace() 注入，不用 .format()）：
#    {NODES_JSON}   {EDGES_JSON}   {DETAIL_MAP_JSON}
#    {NODE_COUNT}   {EDGE_COUNT}
# ══════════════════════════════════════════════════════════════════

def get_html_template() -> str:
    return r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>赛博明翰 · 认知知识图谱</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.9/dist/vis-network.min.js" crossorigin="anonymous"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.9/dist/dist/vis-network.min.css" crossorigin="anonymous"/>
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:"PingFang SC","Noto Sans SC","Microsoft YaHei",sans-serif;
         background:#0d1117;color:#e6edf3;height:100vh;
         display:flex;flex-direction:column;overflow:hidden}
    #hdr{padding:10px 20px;background:#161b22;border-bottom:1px solid #30363d;
         display:flex;align-items:center;gap:14px;flex-shrink:0}
    #hdr h1{font-size:15px;font-weight:600}
    .sub{font-size:11px;color:#8b949e;margin-top:2px}
    #leg{display:flex;gap:14px;margin-left:auto;font-size:11px;align-items:center}
    .li{display:flex;align-items:center;gap:4px}
    .dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
    #main{display:flex;flex:1;overflow:hidden}
    #net{flex:1;background:#0d1117}
    #panel{width:280px;background:#161b22;border-left:1px solid #30363d;
           padding:14px 12px;overflow-y:auto;flex-shrink:0;
           display:flex;flex-direction:column;gap:8px}
    #panel h2{font-size:12px;color:#58a6ff;border-bottom:1px solid #30363d;padding-bottom:5px}
    #pbody{font-size:11px;line-height:1.8;color:#c9d1d9;white-space:pre-wrap}
    #fbar{padding:6px 18px;background:#161b22;border-top:1px solid #30363d;
          display:flex;gap:8px;align-items:center;flex-shrink:0}
    #fbar label{color:#8b949e;font-size:11px}
    #fbar button{padding:2px 10px;border-radius:4px;border:1px solid #30363d;
                 background:#21262d;color:#e6edf3;cursor:pointer;font-size:11px;
                 transition:background .15s}
    #fbar button:hover{background:#30363d}
    #fbar button.on{background:#1f6feb;border-color:#1f6feb}
  </style>
</head>
<body>
  <div id="hdr">
    <div>
      <h1>赛博明翰 · 认知知识图谱</h1>
      <div class="sub">Freudian Psychodynamic KG &nbsp;·&nbsp; {NODE_COUNT} 节点 &nbsp;·&nbsp; {EDGE_COUNT} 边</div>
    </div>
    <div id="leg">
      <div class="li"><div class="dot" style="background:#e05c5c"></div>Id</div>
      <div class="li"><div class="dot" style="background:#f0a500"></div>Superego</div>
      <div class="li"><div class="dot" style="background:#3fb950"></div>Ego</div>
      <div class="li"><div class="dot" style="background:#1f6feb"></div>核心</div>
    </div>
  </div>

  <div id="main">
    <div id="net"></div>
    <div id="panel">
      <h2>节点详情</h2>
      <div id="pbody">点击任意节点查看详情。</div>
    </div>
  </div>

  <div id="fbar">
    <label>显示层：</label>
    <button class="on" data-layer="all">全部</button>
    <button data-layer="Id">Id</button>
    <button data-layer="Superego">Superego</button>
    <button data-layer="Ego">Ego</button>
  </div>

  <script>
    var detailMap = {DETAIL_MAP_JSON};
    var nodes = new vis.DataSet({NODES_JSON});
    var edges = new vis.DataSet({EDGES_JSON});

    var options = {
      groups: {
        root:     {shape:"star",   size:44, color:{background:"#1f6feb",border:"#58a6ff"},
                   font:{color:"#fff",size:14,bold:true}},
        Id:       {shape:"ellipse",size:20, color:{background:"#e05c5c",border:"#8b2a2a",
                   highlight:{background:"#ff7f7f",border:"#e05c5c"}},
                   font:{color:"#fff",size:11}},
        Superego: {shape:"ellipse",size:20, color:{background:"#f0a500",border:"#7a5200",
                   highlight:{background:"#ffc53d",border:"#f0a500"}},
                   font:{color:"#fff",size:11}},
        Ego:      {shape:"ellipse",size:20, color:{background:"#3fb950",border:"#1a5c2a",
                   highlight:{background:"#5cd46a",border:"#3fb950"}},
                   font:{color:"#fff",size:11}}
      },
      physics:{
        enabled:true,
        solver:"barnesHut",
        barnesHut:{
          gravitationalConstant:-2000,
          centralGravity:0.3,
          springLength:95,
          springConstant:0.04,
          damping:0.09,
          avoidOverlap:0.15
        },
        stabilization:{iterations:300,fit:true}
      },
      interaction:{
        hover:true,
        tooltipDelay:200,
        navigationButtons:true,
        keyboard:true
      },
      edges:{
        smooth:{type:"dynamic"}
      }
    };

    var net = new vis.Network(document.getElementById("net"),
                              {nodes:nodes, edges:edges}, options);

    net.on("click", function(p){
      if(!p.nodes.length) return;
      var txt = detailMap[p.nodes[0]] || "";
      document.getElementById("pbody").textContent = txt;
    });

    document.querySelectorAll("#fbar button").forEach(function(btn){
      btn.addEventListener("click", function(){
        document.querySelectorAll("#fbar button")
                .forEach(function(b){b.classList.remove("on");});
        btn.classList.add("on");
        var layer = btn.dataset.layer;
        nodes.update(nodes.get().map(function(n){
          return {id:n.id, hidden:(layer!=="all" && n.group!==layer)};
        }));
        edges.update(edges.get().map(function(e){
          var fn = nodes.get(e.from), tn = nodes.get(e.to);
          var show = (layer==="all") ||
                     (fn && fn.group===layer) ||
                     (tn && tn.group===layer);
          return {id:e.id, hidden:!show};
        }));
      });
    });
  </script>
</body>
</html>
"""


# ══════════════════════════════════════════════════════════════════
#  main
# ══════════════════════════════════════════════════════════════════

def main():
    try:
        data = json.loads(KG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"[ERROR] 找不到：{KG_PATH}", file=sys.stderr); sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 解析失败：{e}", file=sys.stderr); sys.exit(1)

    vis_nodes, detail_map, root_id, skeleton_ids = extract_nodes(data)
    edges = extract_edges(data, vis_nodes, root_id, skeleton_ids)

    print(f"[OK] 节点 {len(vis_nodes)} 个，边 {len(edges)} 条")

    html = (
        get_html_template()
        .replace("{NODES_JSON}",      json.dumps(vis_nodes,  ensure_ascii=False))
        .replace("{EDGES_JSON}",      json.dumps(edges,      ensure_ascii=False))
        .replace("{DETAIL_MAP_JSON}", json.dumps(detail_map, ensure_ascii=False))
        .replace("{NODE_COUNT}",      str(len(vis_nodes)))
        .replace("{EDGE_COUNT}",      str(len(edges)))
    )

    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"[OK] 已写入：{OUT_PATH}  ({len(html.encode())/1024:.1f} KB)")


if __name__ == "__main__":
    main()
