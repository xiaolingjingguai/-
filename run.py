# -*- coding: utf-8 -*-
"""
命令行入口（调试阶段）：
  python run.py 报告文件 [类别 III] [river|lake|groundwater] [选项...]
  水体：river 河流、lake 湖库（GB 3838-2002）；groundwater 地下水（GB/T 14848-2017）
  选项：drink（集中式饮用水源地，启用表2/表3）  tnref（河流总氮参照所选类别评价）
示例：python run.py samples/样例_山涧水_模拟原件.docx III river tnref
其他要素：
  python run.py 报告 air [1|2] [transition|final]     环境空气（GB 3095—2026）
  python run.py 报告 noise [0|1|2|3|4a|4b]           声环境（GB 3096-2008）
  python run.py 报告 soil [build1|build2|paddy|other|orchard]  土壤（GB 36600 / GB 15618）
  python run.py 报告 sediment [1|2|3]                  海洋沉积物（GB 18668-2002）
  python run.py 报告 biota [1|2|3]                     海洋生物质量（GB 18421-2001）
"""
import os
import sys
from parser import read_report
from judge import evaluate, summarize
from export import to_excel, to_word, gw_to_excel, gw_to_word

def run_other(path, kind, args):
    import pipeline
    if kind == "air":
        p = dict(level=int(args[0]) if args else 2, phase=args[1] if len(args) > 1 else "transition")
    elif kind == "noise":
        p = dict(noise_cls=args[0] if args else "2")
    elif kind in ("sediment", "biota"):
        p = dict(marine_cls=int(args[0]) if args else 1)
    else:
        p = dict(land=args[0] if args else "build2")
    records, warnings = pipeline.load(path, kind)
    for w in warnings:
        print("【提示】", w)
    res = pipeline.assess(records, kind, **p)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0] + {"air": "_环境空气", "noise": "_声环境", "soil": "_土壤",
                                                     "sediment": "_海洋沉积物", "biota": "_海洋生物质量"}[kind]
    pipeline.export_excel(os.path.join(out, f"{stem}_判定结果.xlsx"), res, kind, **p)
    pipeline.export_word(os.path.join(out, f"{stem}_判定结果.docx"), res, kind, **p)
    for r in res["summary"]:
        print(*r.values(), sep=" | ")


if __name__ == "__main__":
    path = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] in ("air", "noise", "soil", "sediment", "biota"):
        run_other(path, sys.argv[2], sys.argv[3:])
        sys.exit(0)
    target = sys.argv[2] if len(sys.argv) > 2 else "III"
    body = sys.argv[3] if len(sys.argv) > 3 else "river"
    opts = sys.argv[4:]
    drink, tn_ref = "drink" in opts, "tnref" in opts
    gw = body == "groundwater"
    records, warnings = read_report(path, "groundwater" if gw else "surface")
    for w in warnings:
        print("【提示】", w)
    if gw:
        import gw_judge
        detail = gw_judge.evaluate(records, target)
    else:
        detail = evaluate(records, target, body, drink, tn_ref)
    for d, r in zip(detail, records):     # 测定温度等识别附注并入备注
        if r.get("src_note"):
            d["note"] = "；".join(x for x in (d["note"], r["src_note"]) if x)
    summary = gw_judge.summarize(detail) if gw else summarize(detail)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0] + ("_地下水" if gw else "_地表水")
    if gw:
        ov = gw_judge.overall(detail)
        stats = gw_judge.statistics(detail)
        gw_to_excel(os.path.join(out, f"{stem}_判定结果.xlsx"), summary, detail, ov, target, stats)
        gw_to_word(os.path.join(out, f"{stem}_判定结果.docx"), summary, ov, target, stats)
        for o in ov:
            print("【综合】", o["station"], o["date"], o["cls"], o["worst_items"], o["nd_items"], sep=" | ")
    else:
        to_excel(os.path.join(out, f"{stem}_判定结果.xlsx"), summary, detail, target, body)
        to_word(os.path.join(out, f"{stem}_判定结果.docx"), summary, target, body)
    for r in summary:
        print(r["station"], r["item"], r["range"], r["limit"], r["max_index"], r["max_exceed"],
              r["cls"], r["result"], r["note"], sep=" | ")
