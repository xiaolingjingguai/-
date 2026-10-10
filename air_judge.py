# -*- coding: utf-8 -*-
"""
环境空气质量现状判定（GB 3095—2026）

计算方法：
1. 逐个监测值与对应平均时间的浓度限值比较，C ≤ C0 为达标。
2. 占标率 P = C / C0 × 100%；超标倍数 = (C - C0) / C0（仅超标时计算）。
   HJ 2.2-2018 对补充监测数据评价的具体条款号，因项目资料中无该导则原文，信息不足，请复核。
3. 未检出（"＜DL""DL L""ND"）：检出限 ≤ C0 判达标，占标率记"—"；检出限 > C0 无法判定。
4. 限值阶段：GB 3095—2026 第 4.4 条，2026-03-01 至 2030-12-31 执行表 1"过渡阶段浓度限值"，
   2031-01-01 起执行表 1"浓度限值"；表 2 项目按第 4.5 条由国家或省级确定实施方式。
5. 标准库未收录的项目（如氨、硫化氢、非甲烷总烃）：采用监测报告所列标准限值，并在备注中注明，须人工复核其依据。
"""
import re
from collections import OrderedDict

from judge import parse_value, fmt_num, fmt_limit, _norm, DASH
from gb3095_limits import TABLE1, TABLE2, PERIOD_CN, STANDARD_INFO, UG, MG

LEVEL_CN = {1: "一级", 2: "二级"}
PHASE_CN = {"transition": "过渡阶段浓度限值", "final": "浓度限值"}

_PERIOD_WORDS = r"(1小时平均|小时平均|小时均值|小时值|一次值|日最大8小时平均|8小时平均|8小时|日均值|日平均|24小时平均|年均值|年平均|季平均)"

_INDEX = {}
for _tb, _rows in (("表1", TABLE1), ("表2", TABLE2)):
    for _r in _rows:
        for _a in [_r["name"]] + _r["aliases"]:
            _INDEX.setdefault(_norm(_a), (_tb, _r))


def strip_period(name):
    return re.sub(_PERIOD_WORDS, "", str(name)).strip(" （）()")


def match_item(name):
    key = _norm(strip_period(name))
    if key in _INDEX:
        return _INDEX[key]
    key2 = re.sub(r"以.{1,6}计$", "", key)
    if key2 in _INDEX:
        return _INDEX[key2]
    # 报告中未收录项目（氨、硫化氢、非甲烷总烃等）仍需读取，返回占位
    if re.search(r"氨|硫化氢|非甲烷总烃|总挥发性有机物|TVOC|甲醛|苯|甲苯|二甲苯|氯化氢|硫酸雾|氟化物|臭气|颗粒物|VOCs|甲醇|乙酸|丙酮",
                 str(name), re.I):
        return "其他", None
    return None, None


def _air_known(name):
    """parser 用：库外项目也视为可识别，但第二项为 None"""
    return match_item(name)


def unit_factor(unit, std_unit):
    u = (unit or "").replace("^", "").replace("³", "3").replace("µ", "μ").replace("ug", "μg").lower()
    s = std_unit.replace("³", "3").lower()
    if not u or u == s:
        return 1.0
    if u.startswith("mg/m3") and s.startswith("μg/m3"):
        return 1000.0
    if u.startswith("μg/m3") and s.startswith("mg/m3"):
        return 0.001
    return None


PERIOD_KEYS = {"1h": "1h", "8h": "8h", "24h": "24h", "year": "year", "season": "season"}
_PERIOD_PARSE = [("8h", r"8"), ("1h", r"小时|1h|时均|一次"), ("24h", r"日|24"), ("year", r"年"), ("season", r"季")]


def norm_period(text):
    t = str(text or "").strip()
    if t in PERIOD_KEYS:
        return t
    for k, v in PERIOD_CN.items():
        if t == v:
            return k
    for k, pat in _PERIOD_PARSE:
        if re.search(pat, t):
            return k
    return ""


def _parse_report_limit(text):
    m = re.search(r"([\d.]+)", str(text or ""))
    return float(m.group(1)) if m else None


def judge_one(rec, level=2, phase="transition"):
    tb, row = match_item(rec["item"])
    period = norm_period(rec.get("period"))
    out = dict(rec)
    out.update(std_name=row["name"] if row else strip_period(rec["item"]), table=tb or DASH,
               period=period, period_cn=PERIOD_CN.get(period, "未注明"), limit_text=DASH, ratio=DASH,
               exceed_times=DASH, result="", note="", value_disp=rec["value"], unit_disp=rec.get("unit", ""))
    notes = []
    pv = parse_value(rec["value"])
    if not pv["ok"]:
        out["result"] = "数值无法识别"
        return out
    # ---- 确定限值
    limit = std_unit = None
    if row:
        std_unit = row["unit"]
        if not period:
            out["result"] = "未注明平均时间"
            out["note"] = "请在核对表中填写平均时间（1小时平均/日平均/日最大8小时平均）"
            return out
        lim = row["limits"].get(period)
        if lim is None:
            out["result"] = "该平均时间无限值"
            return out
        limit = lim[phase][level - 1]
        out["limit_text"] = fmt_limit(limit)
        if tb == "表2":
            notes.append("表2其他项目，按 GB 3095—2026 第4.5条由国家或省级确定实施方式")
    else:
        rl = _parse_report_limit(rec.get("report_limit"))
        if rl is None:
            out["result"] = "标准库未收录，报告未列限值"
            out["note"] = "请在核对表\"报告标准值\"中填写限值及依据"
            return out
        limit, std_unit = rl, (rec.get("unit") or "").replace("^3", "³").replace("m3", "m³")
        out["limit_text"] = fmt_limit(limit)
        src = rec.get("table_std") or "报告未注明依据"
        notes.append(f"限值取自监测报告（报告引用：{src}），请复核")
    f = unit_factor(rec.get("unit"), std_unit) if row else 1.0
    if f is None:
        out["result"] = "单位无法换算"
        out["note"] = f"报告单位 {rec.get('unit')}，标准单位 {std_unit}"
        return out
    out["unit_disp"] = std_unit
    if pv["nd"]:
        dl = (pv["dl"] or 0) * f
        out["value_disp"] = f"＜{fmt_num(dl)}" if pv["dl"] else "未检出"
        if pv["dl"] is None or dl <= limit:
            out["result"] = "达标"
            notes.append("未检出")
        else:
            out["result"] = "检出限高于标准限值，无法判定"
    else:
        c = pv["value"] * f
        out["value_disp"] = fmt_num(c)
        p = c / limit
        out["ratio"] = round(p * 100, 1)
        if c > limit:
            out["result"] = "超标"
            out["exceed_times"] = round((c - limit) / limit, 2)
        else:
            out["result"] = "达标"
    # ---- 报告自带限值与标准库不一致时提示
    if row and rec.get("report_limit"):
        rl = _parse_report_limit(rec["report_limit"])
        rf = unit_factor(rec.get("unit"), std_unit)
        if rl is not None and rf and abs(rl * rf - limit) > 1e-9:
            old = "；报告引用 GB 3095—2012，该标准已于 2026-03-01 废止" if "3095-2012" in (rec.get("table_std") or "") else ""
            notes.append(f"报告所列限值 {rec['report_limit']} {(rec.get('unit') or '').replace('^3', '³')} 与 {STANDARD_INFO['code']}"
                         f"{LEVEL_CN[level]}{PHASE_CN[phase]} {fmt_limit(limit)} {std_unit} 不一致{old}")
    out["note"] = "；".join(dict.fromkeys(n for n in notes if n))
    return out


def infer_periods(records):
    """未注明平均时间的：同点位、同日期、同项目有多个值的按 1 小时平均，只有 1 个值的按日平均（均标注为推定）"""
    cnt = {}
    for r in records:
        cnt[(r["station"], r["date"], strip_period(r["item"]))] = cnt.get((r["station"], r["date"], strip_period(r["item"])), 0) + 1
    out = []
    for r in records:
        r = dict(r)
        if not norm_period(r.get("period")):
            n = cnt[(r["station"], r["date"], strip_period(r["item"]))]
            r["period"] = "1h" if n > 1 else "24h"
            r["src_note"] = "；".join(x for x in (r.get("src_note"), "平均时间为推定（同日多值按1小时平均，单值按日平均），请核对") if x)
        out.append(r)
    return out


def evaluate(records, level=2, phase="transition"):
    return [judge_one(r, level, phase) for r in records]


def summarize(results):
    """按 点位 × 项目 × 平均时间 汇总"""
    groups = OrderedDict()
    st_order = list(OrderedDict.fromkeys(r["station"] for r in results))
    for r in sorted(results, key=lambda r: st_order.index(r["station"])):
        groups.setdefault((r["station"], r["std_name"], r["period"]), []).append(r)
    rows = []
    for (st, item, per), rs in groups.items():
        judged = [r for r in rs if r["result"] in ("达标", "超标")]
        nums, nds = [], []
        for r in rs:
            pv = parse_value(str(r["value_disp"]).replace("＜", "<"))
            if pv["ok"] and not pv["nd"]:
                nums.append((pv["value"], r["value_disp"]))
            elif pv["nd"]:
                nds.append((pv["dl"] or 0, r["value_disp"]))
        if nums:
            lo = min(nds)[1] if nds else min(nums)[1]
            hi = max(nums)[1]
            rng = lo if lo == hi else f"{lo}～{hi}"
        elif nds:
            rng = max(nds)[1] if len({x[1] for x in nds}) == 1 else f"{min(nds)[1]}～{max(nds)[1]}"
        else:
            rng = str(rs[0]["value_disp"])
        ratios = [r["ratio"] for r in rs if isinstance(r["ratio"], (int, float))]
        ext = [r["exceed_times"] for r in rs if isinstance(r["exceed_times"], (int, float))]
        n_ex = sum(1 for r in judged if r["result"] == "超标")
        if judged:
            res, rate = ("超标" if n_ex else "达标"), f"{n_ex / len(judged) * 100:.1f}"
        else:
            res, rate = rs[0]["result"], DASH
        notes = list(OrderedDict.fromkeys(n for r in rs for n in (r["note"] + "；" + (r.get("src_note") or "")).split("；") if n))
        rows.append(OrderedDict(
            station=st, item=item, period=PERIOD_CN.get(per, "未注明"), unit=rs[0]["unit_disp"], n=len(rs), range=rng,
            limit=rs[0]["limit_text"], max_ratio=max(ratios) if ratios else DASH, exceed_rate=rate,
            max_exceed=max(ext) if ext else DASH, result=res, note="；".join(notes)))
    return rows
