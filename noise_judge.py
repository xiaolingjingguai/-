# -*- coding: utf-8 -*-
"""
声环境质量现状判定（GB 3096-2008）

1. 昼间、夜间等效声级分别与所选声环境功能区类别的表 1 限值比较，Leq ≤ 限值为达标（第 5.1 条）。
2. 超标量 ΔL = Leq - 限值，单位 dB(A)（声级不计算超标倍数）。
3. 夜间突发噪声最大声级 Lmax：超过夜间限值的幅度不得高于 15 dB(A)（第 5.4 条），即 Lmax ≤ 夜间限值 + 15。
4. 引用《工业企业厂界环境噪声排放标准》（GB 12348-2008）的厂界噪声表：按 GB 12348-2008 表1 所选功能区限值判定
   （4a、4b 类对应厂界 4 类），夜间最大声级按偶发噪声 +15 dB(A)（名称注明"频发"的 +10 dB(A)）。
"""
import re
from collections import OrderedDict

from judge import parse_value, fmt_num, DASH
from gb3096_limits import TABLE1, CLASS_CN, NIGHT_LMAX_MARGIN, STANDARD_INFO
from gb13271_gb12348_limits import BOUNDARY, BOUNDARY_CN, FREQUENT_MARGIN, SPORADIC_MARGIN


def _num(text):
    m = re.search(r"([\d.]+)", str(text or ""))
    return float(m.group(1)) if m else None


def judge_one(rec, cls="2"):
    out = dict(rec)
    out.update(period=rec["item"], limit_text=DASH, over=DASH, result="", note="", value_disp=rec["value"],
               basis=f"{STANDARD_INFO['code']} {CLASS_CN[cls]}")
    notes = []
    pv = parse_value(rec["value"])
    if not pv["ok"] or pv["nd"]:
        out["result"] = "数值无法识别"
        return out
    v = pv["value"]
    out["value_disp"] = fmt_num(v)
    boundary = "12348" in (rec.get("table_std") or "")
    item = rec["item"]
    if boundary:                 # 报告中的厂界噪声表：按 GB 12348-2008 表1 判定（4a/4b 类对应 4 类）
        bcls = "4" if cls.startswith("4") else cls
        day, night = BOUNDARY[bcls]
        out["basis"] = f"GB 12348-2008 {BOUNDARY_CN[bcls]}"
        if re.search(r"Lmax|突发|最大", item, re.I):
            m = FREQUENT_MARGIN if "频发" in item else SPORADIC_MARGIN
            limit = night + m
            notes.append(f"厂界夜间{'频发' if m == FREQUENT_MARGIN else '偶发'}噪声最大声级超过限值的幅度不得高于 {m} dB(A)（GB 12348-2008 第4.1.{2 if m == FREQUENT_MARGIN else 3}条）")
        elif "夜" in item:
            limit = night
        elif "昼" in item:
            limit = day
        else:
            out["result"] = "未注明昼间/夜间"
            out["note"] = "请在核对表\"监测项目\"中填写昼间或夜间"
            return out
        notes.append("厂界噪声按 GB 12348-2008 表1 判定（厂界外声环境功能区按左侧所选类别），也可在\"排放标准—GB 12348-2008\"页判定")
        rl = _num(rec.get("report_limit"))
        if rl is not None and rl != limit and not re.search(r"Lmax|最大", item, re.I):
            notes.append(f"报告所列限值 {rec['report_limit']} 与所选类别限值 {limit} dB(A) 不一致，请核对功能区类别")
    else:
        day, night = TABLE1[cls]
        if "Lmax" in item or "突发" in item:
            limit = night + NIGHT_LMAX_MARGIN
            notes.append(f"夜间突发噪声最大声级不得超过夜间限值 15 dB(A)（第5.4条）")
        elif "夜" in item:
            limit = night
        elif "昼" in item:
            limit = day
        else:
            out["result"] = "未注明昼间/夜间"
            out["note"] = "请在核对表\"监测项目\"中填写昼间或夜间"
            return out
        rl = _num(rec.get("report_limit"))
        if rl is not None and rl != limit and "Lmax" not in item:
            notes.append(f"报告所列限值 {rec['report_limit']} 与所选 {CLASS_CN[cls]} 限值 {limit} dB(A) 不一致，请核对功能区类别")
    out["limit_text"] = fmt_num(limit)
    if v > limit:
        out["result"] = "超标"
        out["over"] = fmt_num(round(v - limit, 1))
    else:
        out["result"] = "达标"
    out["note"] = "；".join(notes)
    return out


def evaluate(records, cls="2"):
    return [judge_one(r, cls) for r in records]


def summarize(results):
    """逐点次列出（声环境监测数据量小，环评报告通常逐点逐时段列表）"""
    st_order = list(OrderedDict.fromkeys(r["station"] for r in results))
    rows = []
    for r in sorted(results, key=lambda r: (st_order.index(r["station"]), r.get("date", ""), "夜" in r["item"])):
        rows.append(OrderedDict(
            station=r["station"], date=r.get("date", ""), period=r["item"], time=r.get("time", ""),
            value=r["value_disp"], limit=r["limit_text"], over=r["over"], basis=r["basis"],
            result=r["result"], note="；".join(x for x in (r["note"], r.get("src_note", "")) if x)))
    return rows
