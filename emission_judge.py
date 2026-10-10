# -*- coding: utf-8 -*-
"""
污染源排放监测数据达标判定

kind：
  wastewater 废水（GB 8978-1996 表1、表4）
  stack      有组织废气（GB 16297-1996 表2 新污染源 / GB 13271-2014 锅炉）
  fugitive   无组织废气（GB 16297-1996 表2 无组织排放监控浓度限值）
  boiler     锅炉废气（GB 13271-2014）
  odor_stack 恶臭有组织排放（GB 14554-93 表2）
  odor_fence 恶臭厂界（GB 14554-93 表1）
  bnoise     厂界噪声（GB 12348-2008 表1）

判定口径：
1. 单个监测值（每一次采样）与标准限值比较，监测值 ≤ 限值为达标；超标倍数 =(C-C0)/C0。
2. 未检出（检出限+L、＜检出限、ND）：检出限 ≤ 限值的判为达标；"不得检出"项目检出即超标。
3. 限值库未收录的项目（如 GB 8978 未列的总磷、GB 16297 未列的臭气浓度、氨、硫化氢等），按监测报告所列限值判定，
   并注明"信息不足，须复核执行标准"；本软件不编造限值。
4. 行业排放标准优先于综合排放标准（GB 16297 第1.2.1条"不交叉执行"）；福建省地方排放标准（DB35）严于国家标准的
   应优先执行，本软件未录入 DB35 标准，判定前须核实适用标准。
"""
import re
from collections import OrderedDict

from judge import parse_value, fmt_num, DASH, _norm
import gb8978_limits as W
import gb16297_limits as A
import gb13271_gb12348_limits as BN
import gb14554_limits as O

WASTEWATER, STACK, FUGITIVE, BOILER, BNOISE = "wastewater", "stack", "fugitive", "boiler", "bnoise"
ODOR_STACK, ODOR_FENCE = "odor_stack", "odor_fence"
EMISSION = (WASTEWATER, STACK, FUGITIVE, BOILER, ODOR_STACK, ODOR_FENCE, BNOISE)
GAS = (STACK, BOILER, ODOR_STACK)   # 有组织废气：GB 16297-1996 表2 / GB 13271-2014 / GB 14554-93 表2
ODOR = (ODOR_STACK, ODOR_FENCE)
METRIC_CN = OrderedDict(conc="实测浓度", conc_ref="折算浓度", rate="排放速率", black="烟气黑度", odor="臭气浓度")
OK, EXCEED, NA = "达标", "超标", "不评价"
INSUFF = "按报告限值（信息不足）"
UPWIND_RE = re.compile(r"上风向|参照点|对照点|背景点")


# ------------------------------------------------------------------ 名称识别
def _index(rows, extra=None):
    idx = {}
    for r in rows:
        for a in [r["name"]] + r.get("aliases", []):
            idx[_norm(a)] = r
    return idx


_W1 = _index(W.TABLE1)
_W4 = _index(W.TABLE4)
_A2 = _index(A.TABLE2)
_O = _index(O.ITEMS)
_BOILER_NAMES = {"颗粒物": ["颗粒物", "烟尘", "粉尘"], "二氧化硫": ["二氧化硫", "SO2", "SO₂"],
                 "氮氧化物": ["氮氧化物", "NOx", "NOX", "氮氧化物(以NO2计)"], "汞及其化合物": ["汞及其化合物", "汞"],
                 "烟气黑度": ["烟气黑度", "林格曼黑度", "林格曼烟气黑度", "黑度"]}
_BOILER = {_norm(a): k for k, v in _BOILER_NAMES.items() for a in v}


def _cands(name):
    n = str(name or "")
    out = [n, re.sub(r"[（(][^()（）]*[)）]", "", n)]
    out.append(re.sub(r"(实测|折算|基准|排放)?(浓度|速率)|最高允许|排放量|\s", "", out[-1]))
    return [_norm(x) for x in dict.fromkeys(out) if x]


def _lookup(idx, name):
    for c in _cands(name):
        if c in idx:
            return idx[c]
    return None


def match_ww(name):
    r = _lookup(_W1, name)
    if r:
        return r["name"], "表1"
    r = _lookup(_W4, name)
    if r:
        return r["name"], "表4"
    return None, None


def match_air(name):
    r = _lookup(_A2, name)
    if r:
        return r["name"], "表2"
    b = None
    for c in _cands(name):
        b = b or _BOILER.get(c)
    return (b, "锅炉") if b else (None, None)


def match_odor(name):
    r = _lookup(_O, name)
    return (r["name"], "GB 14554") if r else (None, None)


def odor_only(name):
    """GB 14554-93 所列、GB 16297-1996 表2 未列的项目（臭气浓度、氨、硫化氢等），在 GB 14554 页判定"""
    return _lookup(_O, name) is not None and _lookup(_A2, name) is None


def matcher(kind):
    """供 parser 判断"是否为标准项目"：返回 (名称或None, 表号或None)"""
    if kind == WASTEWATER:
        return match_ww
    if kind in ODOR:
        return lambda n: match_odor(n) if match_odor(n)[0] else match_air(n)
    if kind in (STACK, FUGITIVE, BOILER):
        return lambda n: match_air(n) if match_air(n)[0] else match_odor(n)
    return lambda n: (None, None)


# ------------------------------------------------------------------ 通用
def _num(text):
    m = re.search(r"(\d+(?:\.\d+)?)", str(text or ""))
    return float(m.group(1)) if m else None


def _report_limit(rec):
    """报告所列限值中的数值（取首个；"6~9"返回区间）"""
    t = str(rec.get("report_limit") or "").replace("～", "~").replace("-", "~")
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*~\s*(\d+(?:\.\d+)?)", t)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    return _num(t)


def _flt(x):
    try:
        return float(str(x).strip())
    except (TypeError, ValueError):
        return None


def _compare(out, v, nd, dl, limit, lo=None):
    """单值与上限（或区间）比较，写入 result / exceed_times"""
    if lo is not None:                     # 区间（pH）
        if nd or v is None:
            out["result"] = "数值无法识别"
            return
        out["result"] = OK if lo <= v <= limit else EXCEED
        return
    if nd:
        if dl is not None and dl > limit:
            out["result"] = "检出限高于限值，无法判定"
        else:
            out["result"] = OK
            out["note_add"] = "未检出"
        return
    out["result"] = OK if v <= limit else EXCEED
    if v > limit and limit > 0:
        out["exceed_times"] = fmt_num(round((v - limit) / limit, 3))


def _base(rec):
    out = dict(rec)
    out.update(std_name=DASH, limit_text=DASH, exceed_times=DASH, result="", note="", basis="",
               value_disp=rec.get("value", ""))
    return out


def _value(rec, out, factor=1.0):
    pv = parse_value(rec.get("value"))
    if not pv["ok"]:
        out["result"] = "数值无法识别"
        return None
    v = pv["value"] * factor if pv["value"] is not None else None
    dl = pv["dl"] * factor if pv["dl"] is not None else None
    if v is not None:
        out["value_disp"] = fmt_num(v)
        out["_v"] = v
    return dict(v=v, nd=pv["nd"], dl=dl)


def _fallback(rec, out, notes, what="本软件限值库未收录该项目"):
    lim = _report_limit(rec)
    out["basis"] = "报告所列限值"
    if lim is None:
        out["result"] = "未收录，报告未列限值"
        notes.append(f"{what}，报告亦未列限值，须确定执行标准（信息不足）")
        return
    val = _value(rec, out)
    if val is None:
        return
    if isinstance(lim, tuple):
        out["limit_text"] = f"{fmt_num(lim[0])}~{fmt_num(lim[1])}"
        _compare(out, val["v"], val["nd"], val["dl"], lim[1], lim[0])
    else:
        out["limit_text"] = fmt_num(lim)
        _compare(out, val["v"], val["nd"], val["dl"], lim)
    notes.append(f"{what}，按报告所列限值判定，须复核执行标准（信息不足）")


def _finish(out, notes):
    if out.pop("note_add", None):
        notes.insert(0, "未检出")
    out["note"] = "；".join(dict.fromkeys(n for n in notes if n))
    return out


# ------------------------------------------------------------------ 废水
def ww_limit(name, grade=1, industry="other", lowf=False):
    """返回 dict(std_name, table, limit, scope, unit, special) 或 None"""
    r = _lookup(_W1, name)
    if r:
        return dict(std_name=r["name"], table="表1", limit=r["limit"], scope="第一类污染物",
                    unit=r.get("unit", "mg/L"), special=False)
    r = _lookup(_W4, name)
    if not r:
        return None
    keys = {industry} | ({"lowf"} if lowf else set())
    row = next((x for x in r["rows"] if x[1] and x[1] & keys), None) \
        or next((x for x in r["rows"] if x[1] is None), None)
    if row is None:
        return dict(std_name=r["name"], table="表4", limit=None, scope="；".join(x[0] for x in r["rows"]),
                    unit=r.get("unit", "mg/L"), special=r.get("special", False), not_applicable=True)
    return dict(std_name=r["name"], table="表4", limit=row[1 + grade], scope=row[0], unit=r.get("unit", "mg/L"),
                special=r.get("special", False))


def _ww_factor(unit, std_unit):
    u = _norm(unit or "")
    s = _norm(std_unit)
    if not u or u == s or "无量纲" in u or u in ("倍", "度"):
        return 1.0, ""
    if s == "mg/l" and u in ("μg/l", "ug/l", "µg/l"):
        return 0.001, "μg/L 已换算为 mg/L"
    if s == "个/l" and u in ("mpn/l", "cfu/l"):
        return 1.0, f"{unit} 按 个/L 等同处理，请复核"
    if s == "个/l" and u in ("mpn/100ml", "个/100ml", "cfu/100ml"):
        return 10.0, f"{unit} 已换算为 个/L（×10）"
    return None, f"单位 {unit} 与标准单位 {std_unit} 不一致，无法换算"


def judge_ww(rec, grade=1, industry="other", lowf=False):
    out = _base(rec)
    notes = []
    lib = ww_limit(rec.get("item"), grade, industry, lowf)
    if lib is None:
        _fallback(rec, out, notes, "GB 8978-1996 未列该项目")
        return _finish(out, notes)
    out["std_name"] = lib["std_name"]
    out["basis"] = f"GB 8978-1996 {lib['table']}" + ("" if lib["table"] == "表1" else f" {W.GRADE_CN[grade]}")
    if lib["table"] == "表1":
        notes.append("第一类污染物，应在车间或车间处理设施排放口采样（第4.2.1.1条）")
    if lib.get("not_applicable"):
        out["result"] = NA
        notes.append(f"表4该项目仅适用于：{lib['scope']}，与所选行业不符；如须评价请核实执行标准")
        return _finish(out, notes)
    if lib["special"]:
        out["limit_text"] = str(lib["limit"])
        _fallback(rec, out, notes, "总余氯为接触消毒后的余量要求（非单纯上限）")
        out["limit_text"] = f"{lib['limit']}（{lib['scope']}）"
        notes.append("表4注：**加氯消毒后须进行脱氯处理")
        return _finish(out, notes)
    lim = lib["limit"]
    if lim is None:
        out["result"] = NA
        notes.append(f"表4{W.GRADE_CN[grade]}对该项目不作规定（原表为“—”）")
        return _finish(out, notes)
    if lib["scope"] not in ("一切排污单位", "第一类污染物"):
        notes.append(f"适用范围：{lib['scope']}")
    f, fnote = _ww_factor(rec.get("unit"), lib["unit"])
    if fnote:
        notes.append(fnote)
    if f is None:
        out["result"] = "单位无法换算"
        return _finish(out, notes)
    val = _value(rec, out, f)
    if val is None:
        return _finish(out, notes)
    if lim == W.ND:
        out["limit_text"] = W.ND
        out["result"] = OK if val["nd"] else EXCEED
        return _finish(out, notes)
    if isinstance(lim, str) and "~" in lim:
        lo, hi = (float(x) for x in lim.split("~"))
        out["limit_text"] = lim
        _compare(out, val["v"], val["nd"], val["dl"], hi, lo)
        return _finish(out, notes)
    out["limit_text"] = fmt_num(lim)
    _compare(out, val["v"], val["nd"], val["dl"], lim)
    rl = _report_limit(rec)
    if isinstance(rl, float) and abs(rl - lim) > 1e-9:
        notes.append(f"报告所列限值 {rec['report_limit']} 与所选标准限值 {fmt_num(lim)} 不一致，请核对级别与行业")
    return _finish(out, notes)


# ------------------------------------------------------------------ 有组织废气
def metric_of(text, unit=""):
    t = f"{text or ''} {unit or ''}"
    if re.search(r"速率|kg/h|g/h", t, re.I):
        return "rate"
    if re.search(r"黑度|林格曼", t):
        return "black"
    if re.search(r"折算|基准", t):
        return "conc_ref"
    return "conc"


def _sub(item, subs_sel):
    i = (subs_sel or {}).get(item["name"])
    if i is None or i >= len(item["subs"]):
        i = len(item["subs"]) - 1
    return item["subs"][i]


def _air_factor(unit, std_unit):
    u = (unit or "").replace("^", "").replace("³", "3").replace("µ", "μ").replace("ug", "μg").replace(" ", "").lower()
    s = std_unit.replace("³", "3").lower()
    if not u or u == s:
        return 1.0
    if u.startswith("mg/m3") and s.startswith("μg/m3"):
        return 1000.0
    if u.startswith("μg/m3") and s.startswith("mg/m3"):
        return 0.001
    if u == "g/h" and s == "kg/h":
        return 0.001
    return None


def stack_rate_limit(item, sub, h, grade, bldg_ok=True):
    """返回 (速率限值, 说明列表)"""
    q, how = A.rate_limit(sub["rates"], h, grade)
    notes = [f"排气筒 {fmt_num(h)} m，{how}"]
    if h < 15 and not item["min_h"]:
        q *= 0.5
        notes.append("新污染源排气筒低于 15 m，按外推结果再严格 50%（第7.4条）")
    if item["min_h"] and h < item["min_h"]:
        notes.append(f"排放{item['name']}的排气筒不得低于 {item['min_h']} m（表2注）")
    if not bldg_ok:
        q *= 0.5
        notes.append("排气筒未高出周围 200 m 半径范围建筑 5 m 以上，速率严格 50%（第7.1条）")
    return q, notes


STD_MODES = [("auto", "按报告自动识别（锅炉→GB 13271，其余→GB 16297）"), ("16297", "全部按 GB 16297-1996 表2"),
             ("13271", "全部按 GB 13271-2014（锅炉）")]


def stack_std(rec, mode="auto"):
    """有组织废气执行标准：锅炉（点位名称含"锅炉"或表内引用 GB 13271）按 GB 13271，其余按 GB 16297"""
    if mode != "auto":
        return mode
    t = f"{rec.get('station', '')} {rec.get('table_std', '')}"
    return "13271" if re.search(r"锅炉|13271", t) else "16297"


def boiler_fuel(rec, default="coal"):
    t = str(rec.get("station", ""))
    if re.search(r"燃气|天然气|液化气|LNG|LPG|沼气", t, re.I):
        return "gas"
    if re.search(r"燃油|柴油|重油|轻油", t):
        return "oil"
    if re.search(r"燃煤|生物质|煤", t):
        return "coal"
    return default


def judge_stack(rec, std="16297", grade=2, subs=None, height=None, bldg_ok=True, fuel="coal", btable=2,
                has_ref=False):
    out = _base(rec)
    notes = []
    metric = rec.get("metric") or metric_of(rec.get("metric_cn"), rec.get("unit"))
    out["metric"] = metric
    out["metric_cn"] = METRIC_CN.get(metric, metric)
    name = rec.get("item")
    if std == "13271":
        return _judge_boiler(rec, out, notes, metric, fuel, btable, has_ref)
    item = _lookup(_A2, name)
    if metric == "black":
        out["std_name"] = "烟气黑度"
        out["basis"] = "GB 16297-1996 第7.6条"
        out["limit_text"] = "林格曼1级"
        v = _num(rec.get("value"))
        out["result"] = DASH if v is None else (OK if v <= 1 else EXCEED)
        notes.append("第7.6条仅针对工业生产尾气确需燃烧排放的情形")
        return _finish(out, notes)
    if item is None:
        _fallback(rec, out, notes, "GB 16297-1996 表2未列该项目")
        return _finish(out, notes)
    sub = _sub(item, subs)
    out["std_name"] = item["name"]
    out["basis"] = f"GB 16297-1996 表2 {A.GRADE_CN[grade]}"
    if sub["scope"]:
        notes.append(f"适用情形：{sub['scope']}")
    if metric == "rate":
        h = _flt(rec.get("height")) or height
        if not h:
            out["result"] = "缺少排气筒高度"
            notes.append("请在核对表“排气筒高度”列或左侧参数中填写排气筒高度")
            return _finish(out, notes)
        q, hn = stack_rate_limit(item, sub, h, grade, bldg_ok)
        notes += hn
        f = _air_factor(rec.get("unit") or "kg/h", "kg/h")
        if f is None:
            out["result"] = "单位无法换算"
            notes.append(f"排放速率单位 {rec.get('unit')} 无法换算为 kg/h")
            return _finish(out, notes)
        val = _value(rec, out, f)
        if val is None:
            return _finish(out, notes)
        out["limit_text"] = fmt_num(float(f"{q:.3g}"))
        _compare(out, val["v"], val["nd"], val["dl"], float(f"{q:.3g}"))
        return _finish(out, notes)
    if metric == "conc_ref":
        notes.append("GB 16297-1996 以实测浓度判定，报告列的是折算浓度，请核对")
    f = _air_factor(rec.get("unit") or "mg/m3", "mg/m3")
    if f is None:
        out["result"] = "单位无法换算"
        return _finish(out, notes)
    val = _value(rec, out, f)
    if val is None:
        return _finish(out, notes)
    out["limit_text"] = fmt_num(sub["conc"])
    if item.get("conc_note"):
        notes.append(f"原表限值：{item['conc_note']}")
    _compare(out, val["v"], val["nd"], val["dl"], sub["conc"])
    return _finish(out, notes)


def _judge_boiler(rec, out, notes, metric, fuel, btable, has_ref):
    name = None
    for c in _cands(rec.get("item")):
        name = name or _BOILER.get(c)
    if metric == "black" or name == "烟气黑度":
        out.update(std_name="烟气黑度", basis=f"GB 13271-2014 表{btable}", limit_text="≤1级（林格曼黑度）")
        out["metric_cn"] = METRIC_CN["black"]
        v = _num(rec.get("value"))
        out["result"] = "数值无法识别" if v is None else (OK if v <= BN.BLACKNESS else EXCEED)
        if "<" in str(rec.get("value")) or "＜" in str(rec.get("value")):
            out["result"] = OK
        notes.append("监控位置为烟囱排放口")
        return _finish(out, notes)
    if name is None:
        _fallback(rec, out, notes, "GB 13271-2014 未列该项目")
        return _finish(out, notes)
    out["std_name"] = name
    out["basis"] = f"GB 13271-2014 表{btable} {BN.FUEL_CN[fuel]}"
    if metric == "rate":
        out["result"] = NA
        notes.append("GB 13271-2014 未规定排放速率限值")
        return _finish(out, notes)
    lim = BN.BOILER[btable][name][BN.FUEL_IDX[fuel]]
    if lim is None:
        out["result"] = NA
        notes.append(f"{BN.FUEL_CN[fuel]}该项目无限值（原表为“-”）")
        return _finish(out, notes)
    f = _air_factor(rec.get("unit") or "mg/m3", "mg/m3")
    if f is None:
        out["result"] = "单位无法换算"
        return _finish(out, notes)
    ref = BN.REF_O2[fuel]
    if metric == "conc":
        if has_ref:
            _value(rec, out)
            out["result"] = NA
            out["limit_text"] = fmt_num(lim)
            notes.append("实测浓度，判定以同一样品的折算浓度为准")
            return _finish(out, notes)
        o2 = _flt(rec.get("o2"))
        if o2 is None:
            out["result"] = "缺少含氧量，无法折算"
            out["limit_text"] = fmt_num(lim)
            notes.append(f"须按第5.2条式(1)折算为基准氧含量 {fmt_num(ref)}% 后判定，请在核对表填写实测含氧量")
            return _finish(out, notes)
        if o2 >= 21:
            out["result"] = "含氧量有误"
            return _finish(out, notes)
        f *= (21 - ref) / (21 - o2)
        notes.append(f"按第5.2条式(1)折算：ρ=ρ′×(21-{fmt_num(ref)})/(21-{fmt_num(o2)})")
    val = _value(rec, out, f)
    if val is None:
        return _finish(out, notes)
    if metric == "conc":
        out["value_disp"] = (fmt_num(round(val["v"], 3)) + "（折算）") if val["v"] is not None else out["value_disp"]
    out["limit_text"] = fmt_num(lim)
    _compare(out, val["v"], val["nd"], val["dl"], lim)
    if name == "二氧化硫" and btable == 1 and fuel == "coal":
        notes.append("位于广西、重庆、四川、贵州的在用燃煤锅炉二氧化硫执行 550 mg/m³（表1注）")
    return _finish(out, notes)


# ------------------------------------------------------------------ 无组织废气
def judge_fug(rec, subs=None):
    out = _base(rec)
    notes = []
    if UPWIND_RE.search(str(rec.get("station", ""))):
        notes.append("上风向参照点，评价以下风向周界外浓度最高点为准")
    item = _lookup(_A2, rec.get("item"))
    if item is None:
        _fallback(rec, out, notes, "GB 16297-1996 表2未列该项目")
        return _finish(out, notes)
    sub = _sub(item, subs)
    point, lim, unit = sub["fug"]
    out["std_name"] = item["name"]
    out["basis"] = "GB 16297-1996 表2 无组织排放监控浓度限值"
    if sub["scope"] and len(item["subs"]) > 1:
        notes.append(f"适用情形：{sub['scope']}")
    if lim is None or isinstance(lim, str):
        out["limit_text"] = lim or point
        out["result"] = NA
        notes.append(f"标准要求：{lim or point}，不作浓度数值判定")
        return _finish(out, notes)
    f = _air_factor(rec.get("unit") or unit, unit)
    if f is None:
        out["result"] = "单位无法换算"
        notes.append(f"单位 {rec.get('unit')} 无法换算为 {unit}")
        return _finish(out, notes)
    val = _value(rec, out, f)
    if val is None:
        return _finish(out, notes)
    out["limit_text"] = fmt_num(lim) + ("" if unit == "mg/m3" else f" {unit}")
    out["unit_disp"] = unit
    _compare(out, val["v"], val["nd"], val["dl"], lim)
    notes.append(f"监控点：{point}")
    return _finish(out, notes)


# ------------------------------------------------------------------ 恶臭（GB 14554-93）
def judge_odor_stack(rec, height=None):
    out = _base(rec)
    notes = []
    metric = rec.get("metric") or metric_of(rec.get("metric_cn"), rec.get("unit"))
    out["metric"] = metric
    out["metric_cn"] = METRIC_CN.get(metric, metric)
    item = _lookup(_O, rec.get("item"))
    if item is None:
        _fallback(rec, out, notes, "GB 14554-93 表2未列该项目")
        return _finish(out, notes)
    odor = item["name"] == "臭气浓度"
    out["std_name"] = item["name"]
    out["basis"] = "GB 14554-93 表2"
    if odor:
        out["metric"], out["metric_cn"] = "odor", "臭气浓度"
    elif metric != "rate":
        _value(rec, out)
        out["result"] = NA
        notes.append("GB 14554-93 表2对该项目仅规定排放量（kg/h），不规定排放浓度")
        return _finish(out, notes)
    h = _flt(rec.get("height")) or height
    if not h:
        out["result"] = "缺少排气筒高度"
        notes.append("请在核对表“排气筒高度”列或左侧参数中填写排气筒高度")
        return _finish(out, notes)
    th, lim, how = O.stack_height(item["stack"], h, item.get("open_top", False))
    notes.append(how)
    if lim is None:
        _value(rec, out)
        out["result"] = NA
        return _finish(out, notes)
    f = 1.0
    if not odor:
        f = _air_factor(rec.get("unit") or "kg/h", "kg/h")
        if f is None:
            out["result"] = "单位无法换算"
            notes.append(f"排放量单位 {rec.get('unit')} 无法换算为 kg/h")
            return _finish(out, notes)
    val = _value(rec, out, f)
    if val is None:
        return _finish(out, notes)
    out["limit_text"] = fmt_num(lim)
    if odor:
        out["unit_disp"] = "无量纲"
    _compare(out, val["v"], val["nd"], val["dl"], lim)
    return _finish(out, notes)


def judge_odor_fence(rec, grade=1):
    out = _base(rec)
    notes = []
    if UPWIND_RE.search(str(rec.get("station", ""))):
        notes.append("上风向参照点，列出供对照")
    item = _lookup(_O, rec.get("item"))
    if item is None:
        _fallback(rec, out, notes, "GB 14554-93 表1未列该项目")
        return _finish(out, notes)
    lim = item["fence"][grade]
    out["std_name"] = item["name"]
    out["basis"] = f"GB 14554-93 表1 {O.FENCE_CN[grade]}"
    f = 1.0
    if item["unit"] != "无量纲":
        f = _air_factor(rec.get("unit") or item["unit"], item["unit"])
        if f is None:
            out["result"] = "单位无法换算"
            notes.append(f"单位 {rec.get('unit')} 无法换算为 mg/m³")
            return _finish(out, notes)
    val = _value(rec, out, f)
    if val is None:
        return _finish(out, notes)
    out["limit_text"] = fmt_num(lim)
    out["unit_disp"] = item["unit"]
    _compare(out, val["v"], val["nd"], val["dl"], lim)
    rl = _report_limit(rec)
    if isinstance(rl, float) and abs(rl - lim) > 1e-9:
        notes.append(f"报告所列限值 {rec['report_limit']} 与所选{O.FENCE_CN[grade]}限值 {fmt_num(lim)} 不一致，请核对标准分级")
    return _finish(out, notes)


# ------------------------------------------------------------------ 厂界噪声
def judge_bnoise(rec, bcls="3", frequent=False, indoor=False):
    out = _base(rec)
    out.update(period=rec.get("item", ""), over=DASH)
    notes = []
    pv = parse_value(rec.get("value"))
    if not pv["ok"] or pv["nd"]:
        out["result"] = "数值无法识别"
        return _finish(out, notes)
    v = pv["value"]
    out["value_disp"] = fmt_num(v)
    day, night = BN.BOUNDARY[bcls]
    item = str(rec.get("item", ""))
    if indoor:
        day, night = day - BN.INDOOR_REDUCE, night - BN.INDOOR_REDUCE
        notes.append("厂界与噪声敏感建筑物距离小于 1 m，室内测量，限值减 10 dB(A)（第4.1.5条）")
    if re.search(r"Lmax|最大声级|突发|频发|偶发", item, re.I):
        fr = "频发" in item or (frequent and "偶发" not in item)
        m = BN.FREQUENT_MARGIN if fr else BN.SPORADIC_MARGIN
        limit = night + m
        notes.append(f"夜间{'频发' if fr else '偶发'}噪声最大声级超过限值的幅度不得高于 {m} dB(A)"
                     f"（第4.1.{2 if fr else 3}条）")
    elif "夜" in item:
        limit = night
    elif "昼" in item:
        limit = day
    else:
        out["result"] = "未注明昼间/夜间"
        notes.append("请在核对表中填写昼间或夜间")
        return _finish(out, notes)
    out["basis"] = f"GB 12348-2008 {BN.BOUNDARY_CN[bcls]}"
    out["limit_text"] = fmt_num(limit)
    rl = _num(rec.get("report_limit"))
    if rl is not None and rl != limit and not re.search(r"Lmax|最大", item, re.I):
        notes.append(f"报告所列限值 {rec['report_limit']} 与所选 {BN.BOUNDARY_CN[bcls]} 限值 {limit} dB(A) 不一致，请核对厂界外声环境功能区类别")
    out["result"] = EXCEED if v > limit else OK
    if v > limit:
        out["over"] = fmt_num(round(v - limit, 1))
    return _finish(out, notes)


# ------------------------------------------------------------------ 批量与汇总
def evaluate(records, kind, p):
    out = _evaluate(records, kind, p)
    for r, o in zip(records, out):
        db = [s for s in str(r.get("table_std", "")).split("；") if s.startswith("DB")]
        if db:
            o["note"] = "；".join(x for x in (o["note"], f"报告表注引用地方标准 {'、'.join(db)}，本软件未录入，"
                                              "执行标准及限值须核实（信息不足）") if x)
    return out


def _evaluate(records, kind, p):
    if kind == WASTEWATER:
        return [judge_ww(r, p.get("grade", 1), p.get("industry", "other"), p.get("lowf", False)) for r in records]
    if kind == ODOR_STACK:
        return [judge_odor_stack(r, p.get("height")) for r in records]
    if kind == ODOR_FENCE:
        return [judge_odor_fence(r, p.get("grade", 1)) for r in records]
    if kind in GAS:
        ref = {(r.get("station"), r.get("date"), _norm(r.get("item")))
               for r in records if (r.get("metric") or metric_of(r.get("metric_cn"), r.get("unit"))) == "conc_ref"}
        std = "13271" if kind == BOILER else "16297"
        return [judge_stack(r, std, p.get("grade", 2), p.get("subs"), p.get("height"),
                            p.get("bldg_ok", True), boiler_fuel(r, p.get("fuel", "coal")), p.get("btable", 2),
                            has_ref=(r.get("station"), r.get("date"), _norm(r.get("item"))) in ref)
                for r in records]
    if kind == FUGITIVE:
        return [judge_fug(r, p.get("subs")) for r in records]
    return [judge_bnoise(r, p.get("bcls", "3"), p.get("frequent", False), p.get("indoor", False)) for r in records]


def _fmt_range(rows):
    nums = [r["_v"] for r in rows if r.get("_v") is not None]
    nds = [str(r.get("value")) for r in rows if r.get("_v") is None and parse_value(r.get("value"))["nd"]]
    if nums:
        lo, hi = min(nums), max(nums)
        s = fmt_num(round(lo, 4)) if lo == hi else f"{fmt_num(round(lo, 4))}~{fmt_num(round(hi, 4))}"
        return s + (f"（另{len(nds)}次未检出）" if nds else "")
    return nds[0] if nds else DASH


def _group_result(rows):
    res = [r["result"] for r in rows]
    if any(x == EXCEED for x in res):
        return EXCEED
    if res and all(x == OK for x in res):
        return OK
    judged = [x for x in res if x in (OK, EXCEED)]
    if judged and all(x == OK for x in judged):
        return OK + "（部分未评价）"
    return next((x for x in res if x not in (OK,)), DASH)


def summarize(results, kind):
    if kind == BNOISE:
        st_order = list(OrderedDict.fromkeys(r["station"] for r in results))
        return [OrderedDict(station=r["station"], date=r.get("date", ""), period=r["period"], time=r.get("time", ""),
                            value=r["value_disp"], limit=r["limit_text"], over=r["over"], basis=r["basis"],
                            result=r["result"], note=r["note"])
                for r in sorted(results, key=lambda r: (st_order.index(r["station"]), r.get("date", ""),
                                                        "夜" in r["period"], "max" in r["period"].lower()))]
    groups = OrderedDict()
    for r in results:
        key = (r.get("station", ""), r.get("std_name") if r.get("std_name") != DASH else r.get("item"), r.get("metric", ""))
        groups.setdefault(key, []).append(r)
    rows = []
    for (st, item, metric), rs in groups.items():
        rows.append(_sum_row(st, item, metric, rs))
    if kind == FUGITIVE:          # 各项目下风向周界外浓度最高点
        by_item = OrderedDict()
        for r in results:
            if not UPWIND_RE.search(str(r.get("station", ""))):
                by_item.setdefault(r.get("std_name") if r.get("std_name") != DASH else r.get("item"), []).append(r)
        for item, rs in by_item.items():
            stations = list(OrderedDict.fromkeys(r["station"] for r in rs))
            if len(stations) < 2:
                continue
            best = max(rs, key=lambda r: r.get("_v") if r.get("_v") is not None else -1)
            row = _sum_row("周界外浓度最高点", item, "", rs)
            row["range"] = best.get("value_disp", DASH)
            row["note"] = f"取下风向各点最大值（{best['station']}）"
            rows.append(row)
    return rows


def _sum_row(st, item, metric, rs):
    judged = [r for r in rs if r["result"] in (OK, EXCEED)]
    ex = [r for r in judged if r["result"] == EXCEED]
    mx = max((_flt(r["exceed_times"]) or 0 for r in ex), default=None)
    limits = list(OrderedDict.fromkeys(r["limit_text"] for r in rs if r["limit_text"] != DASH))
    notes = list(OrderedDict.fromkeys(n for r in rs for n in r["note"].split("；") if n and n != "未检出"))
    heights = list(OrderedDict.fromkeys(str(r.get("height") or "") for r in rs if r.get("height")))
    return OrderedDict(
        station=st, item=item, metric=METRIC_CN.get(metric, metric), unit=rs[0].get("unit_disp") or rs[0].get("unit", ""),
        height="、".join(heights), n=len(rs), range=_fmt_range(rs), limit="、".join(limits) or DASH,
        max_exceed=fmt_num(mx) if mx is not None else DASH,
        exceed_rate=f"{len(ex) / len(judged) * 100:.0f}" if judged else DASH,
        result=_group_result(rs), basis=rs[0].get("basis", ""), note="；".join(notes))
