# -*- coding: utf-8 -*-
"""
达标判定与统计模块

计算方法：
1. 单因子评价：依据 GB 3838-2002 第5.1条"进行单因子评价，评价结果应说明水质达标情况，
   超标的应说明超标项目和超标倍数"。
2. 标准指数（HJ 2.3-2018《环境影响评价技术导则 地表水环境》水质指数法，附录条款号请复核）：
   一般项目      S_i = C_i / C_si
   pH            pH ≤ 7.0 时 S_pH = (7.0 - pH) / (7.0 - pH_sd)
                 pH > 7.0 时 S_pH = (pH - 7.0) / (pH_su - 7.0)     pH_sd = 6，pH_su = 9
   溶解氧        DO ≥ DO_s 时 S_DO = |DO_f - DO| / (DO_f - DO_s)
                 DO < DO_s 时 S_DO = 10 - 9 × DO / DO_s
                 DO_f = 468 / (31.6 + T)，T 为水温（℃），取同断面同次水温监测值
   S > 1 表示超标。
3. 超标倍数 = (C_i - C_si) / C_si
   参照《地表水环境质量评价办法（试行）》（环办〔2011〕22号），水温、pH、溶解氧不计算超标倍数。
4. 未检出（"L"、"ND"、"<DL"）：检出限 ≤ 标准限值时判定达标，标准指数、超标倍数记"—"；
   检出限 > 标准限值时无法判定，结果记"检出限高于标准限值，无法判定"。
"""
import re
from collections import OrderedDict
from gb3838_limits import TABLE1, TABLE2, TABLE3, CLASSES, CLASS_CN

DASH = "—"


def fmt_num(x):
    """数值转字符串，保留 6 位有效数字，不用科学计数法。"""
    x = float(f"{x:.6g}")
    return f"{x:.12f}".rstrip("0").rstrip(".")


def fmt_limit(v):
    """按标准原文写法输出限值：整数写整数，1.0 保留一位小数，避免科学计数法。"""
    r = repr(v)
    if "e" in r:
        r = f"{v:.10f}".rstrip("0")
    return r


# ------------------------------------------------------------------ 名称识别
def _norm(s):
    s = str(s).strip()
    s = s.translate(str.maketrans("（）［］，＋－　", "()[],+- "))
    s = re.sub(r"[\s()\[\]（）、,_·]", "", s)
    return s.lower()


_INDEX = {}
for _tb, _rows in (("表1", TABLE1), ("表2", TABLE2), ("表3", TABLE3)):
    for _r in _rows:
        for _a in [_r["name"]] + _r.get("aliases", []):
            _INDEX.setdefault(_norm(_a), (_tb, _r))


def match_item(name):
    """监测项目名称 → (表号, 标准条目)。识别不了返回 (None, None)。"""
    key = _norm(name)
    if key in _INDEX:
        return _INDEX[key]
    # 去掉"以X计"后缀再试，如"氨氮(以N计)"
    key2 = re.sub(r"以.{1,4}计$", "", key)
    if key2 in _INDEX:
        return _INDEX[key2]
    # 报告常写"总铅、总锌"等（测定的即总量），按标准中的"铅、锌"判定
    m = re.match(r"^总(铜|锌|铅|镉|汞|砷|硒|铁|锰|镍|钡|钴|钼|铍|硼|锑|银|铊|钠)$", key2)
    if m and m.group(1) in _INDEX:
        return _INDEX[m.group(1)]
    return None, None


# ------------------------------------------------------------------ 数值识别
_ND_PAT = re.compile(r"^(?:ND|未检出|N\.D\.?)[\(（]?([0-9.Ee\-×x^]*)[\)）]?$", re.I)


def _to_float(s):
    s = s.replace("×10^", "e").replace("×10", "e").replace("x10^", "e").replace("X10^", "e")
    return float(s)


def parse_value(raw):
    """
    解析监测值字符串。
    返回 dict(value=数值或None, nd=是否未检出, dl=检出限或None, ok=是否解析成功)
    支持：7.2、0.05L、<0.05、＜0.05、ND、ND(0.01)、未检出、1.2×10^3、1.2E3
    """
    if raw is None:
        return dict(value=None, nd=False, dl=None, ok=False)
    if isinstance(raw, (int, float)):
        return dict(value=float(raw), nd=False, dl=None, ok=True)
    s = str(raw).strip().replace(" ", "").replace("＜", "<").replace("〈", "<")
    if s in ("", "-", "—", "/"):
        return dict(value=None, nd=False, dl=None, ok=False)
    m = re.match(r"^([0-9.Ee\-×x^]+)L$", s)                    # 0.05L
    if m:
        return dict(value=None, nd=True, dl=_to_float(m.group(1)), ok=True)
    m = re.match(r"^<([0-9.Ee\-×x^]+)$", s)                    # <0.05
    if m:
        return dict(value=None, nd=True, dl=_to_float(m.group(1)), ok=True)
    m = _ND_PAT.match(s)                                       # ND / ND(0.01)
    if m:
        dl = _to_float(m.group(1)) if m.group(1) else None
        return dict(value=None, nd=True, dl=dl, ok=True)
    try:
        return dict(value=_to_float(s), nd=False, dl=None, ok=True)
    except ValueError:
        return dict(value=None, nd=False, dl=None, ok=False)


# ------------------------------------------------------------------ 单位换算
def unit_factor(unit, std_unit):
    """返回 (换算系数, 说明)。监测值 × 系数 = 标准单位下的数值。无法换算返回 (None, 说明)。"""
    u = _norm(unit or "")
    su = _norm(std_unit)
    if not u or u == su:
        return 1.0, ""
    if su == "mg/l":
        if u in ("μg/l", "ug/l", "µg/l"):
            return 0.001, "μg/L 已换算为 mg/L"
        if u in ("ng/l",):
            return 1e-6, "ng/L 已换算为 mg/L"
    if su == "个/l":
        if u in ("mpn/l", "cfu/l"):
            return 1.0, f"{unit} 按 个/L 等同处理，请复核"
        if u in ("mpn/100ml", "cfu/100ml", "个/100ml"):
            return 10.0, f"{unit} ×10 换算为 个/L"
    if su == "无量纲" and u in ("", "无量纲", "/"):
        return 1.0, ""
    return None, f"单位 {unit} 与标准单位 {std_unit} 不一致，无法自动换算"


# ------------------------------------------------------------------ 限值选取
def get_limit(table, row, target_class, water_body, tn_ref=False):
    """返回 (限值, 说明)。限值为 float 或 (下限, 上限)；不适用返回 (None, 原因)。"""
    if table == "表1":
        if row["direction"] == "none":
            return None, "标准未规定浓度限值"
        if row.get("lake_only") and water_body != "lake":
            if tn_ref:   # 河流总氮参照所选类别限值评价（用户开关）
                return row["values"][CLASSES.index(target_class)], \
                    f"河流{row['name']}参照{CLASS_CN[target_class]}标准限值评价"
            return None, f"{row['name']}标准限值仅适用于湖、库，河流不评价"
        idx = CLASSES.index(target_class)
        if water_body == "lake" and "lake_values" in row:
            return row["lake_values"][idx], "湖、库限值"
        return row["values"][idx], ""
    return row["value"], ""


def classify(row, v, water_body, tn_ref=False):
    """单因子水质类别：返回满足的最高功能类别，如"Ⅱ类"或"劣Ⅴ类"。"""
    if row.get("direction") in (None, "none", "range") or (row.get("lake_only") and water_body != "lake" and not tn_ref):
        return DASH
    vals = row["lake_values"] if (water_body == "lake" and "lake_values" in row) else row["values"]
    for c, lim in zip(CLASSES, vals):
        if (row["direction"] == "le" and v <= lim) or (row["direction"] == "ge" and v >= lim):
            return CLASS_CN[c]
    return "劣Ⅴ类"


# ------------------------------------------------------------------ 单样判定
def judge_one(rec, target_class="III", water_body="river", drinking_source=False, water_temp=None,
              tn_ref=False):
    """tn_ref：河流总氮是否参照所选类别限值评价（默认否，按标准原文不评价）"""
    """
    rec: dict(station, date, item, value, unit)
    返回在 rec 基础上增加：std_name, table, limit_text, index, exceed_times, result, cls, note
    """
    out = dict(rec)
    table, row = match_item(rec["item"])
    out.update(value_disp=str(rec["value"]), unit_disp=rec.get("unit") or "",
               std_name=rec["item"], table=table, limit_text=DASH, index=DASH,
               exceed_times=DASH, result="", cls=DASH, note="")
    if row is None:
        out["result"] = "GB 3838-2002 未列此项目"
        return out
    out["std_name"] = row["name"]
    if table in ("表2", "表3") and not drinking_source:
        out["result"] = "不适用（仅适用于集中式生活饮用水地表水源地）"
        return out

    lim, lim_note = get_limit(table, row, target_class, water_body, tn_ref)
    pv = parse_value(rec["value"])
    notes = [lim_note] if lim_note else []

    if lim is None:
        out["result"] = "不评价"
        out["note"] = "；".join(notes)
        return out

    direction = row.get("direction", "le")
    out["limit_text"] = (f"{fmt_limit(lim[0])}～{fmt_limit(lim[1])}" if direction == "range"
                         else ("≥" if direction == "ge" else "≤") + fmt_limit(lim))

    if not pv["ok"]:
        out["result"] = "监测值无法识别"
        out["note"] = "；".join(notes)
        return out

    f, unote = unit_factor(rec.get("unit"), row["unit"])
    if unote:
        notes.append(unote)
    if f is None:
        out["result"] = "单位无法换算，未判定"
        out["note"] = "；".join(notes)
        return out
    if f != 1.0:   # 汇总表统一以标准单位显示
        out["unit_disp"] = row["unit"]
        out["value_disp"] = (f"{fmt_num(pv['dl'] * f)}L" if pv["nd"] and pv["dl"] is not None
                             else ("未检出" if pv["nd"] else fmt_num(pv["value"] * f)))

    # 未检出
    if pv["nd"]:
        dl = pv["dl"] * f if pv["dl"] is not None else None
        if direction == "le" and (dl is None or dl <= lim):
            out["result"] = "达标"
            out["cls"] = DASH
            if dl is None:
                notes.append("报告未给出检出限")
        else:
            out["result"] = "检出限高于标准限值，无法判定"
        out["note"] = "；".join(notes)
        return out

    v = pv["value"] * f
    if direction == "range":
        lo, hi = lim
        s = (7.0 - v) / (7.0 - lo) if v <= 7.0 else (v - 7.0) / (hi - 7.0)
        out["index"] = round(s, 2)
        out["result"] = "达标" if lo <= v <= hi else "超标"
    elif direction == "ge":
        ok = v >= lim
        if water_temp is not None:
            dof = 468.0 / (31.6 + water_temp)
            s = abs(dof - v) / (dof - lim) if v >= lim else 10 - 9 * v / lim
            out["index"] = round(s, 2)
        else:
            notes.append("缺同次水温，未计算溶解氧标准指数")
        out["result"] = "达标" if ok else "超标"
        out["cls"] = classify(row, v, water_body, tn_ref) if table == "表1" else DASH
    else:
        s = v / lim
        out["index"] = round(s, 2)
        if v > lim:
            out["result"] = "超标"
            out["exceed_times"] = round((v - lim) / lim, 2)
        else:
            out["result"] = "达标"
        out["cls"] = classify(row, v, water_body, tn_ref) if table == "表1" else DASH
    out["note"] = "；".join(notes)
    return out


# ------------------------------------------------------------------ 批量判定
def _cmp_limit(out, rec):
    """核对报告自带标准值与本库限值是否一致，不一致写入备注。"""
    rl = str(rec.get("report_limit") or "").strip()
    if not rl:
        return
    def nums(t):
        return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)]
    mine = out["limit_text"]
    if rl in ("/", "—", "-", "／"):
        return
    if mine == DASH:
        msg = f"第三方报告{out['std_name']}按{rl}评价"
    elif nums(rl) != nums(mine):
        msg = f"报告标准值{rl}与本库限值{mine}不一致，请核对"
    else:
        return
    out["note"] = "；".join([x for x in (out["note"], msg) if x])


def evaluate(records, target_class="III", water_body="river", drinking_source=False, tn_ref=False):
    """records: list[dict(station, date, item, value, unit)]，返回逐样判定结果列表。"""
    # 同断面同日期水温，用于溶解氧标准指数
    temps = {}
    for r in records:
        _, row = match_item(r["item"])
        if row is not None and row["name"] == "水温":
            pv = parse_value(r["value"])
            if pv["ok"] and pv["value"] is not None:
                temps[(r["station"], r["date"])] = pv["value"]
    out = []
    for r in records:
        o = judge_one(r, target_class, water_body, drinking_source,
                      temps.get((r["station"], r["date"])), tn_ref)
        _cmp_limit(o, r)
        out.append(o)
    return out


_CLS_ORDER = ["Ⅰ类", "Ⅱ类", "Ⅲ类", "Ⅳ类", "Ⅴ类", "劣Ⅴ类"]


def summarize(results):
    """
    按 断面 × 项目 汇总：监测值范围、标准限值、最大标准指数、超标率、最大超标倍数、单因子类别、达标情况。
    超标率 = 超标样次 / 有效判定样次 × 100%
    """
    groups = OrderedDict()
    st_order = list(OrderedDict.fromkeys(r["station"] for r in results))
    for r in sorted(results, key=lambda r: st_order.index(r["station"])):   # 稳定排序：同断面行相邻
        groups.setdefault((r["station"], r["std_name"]), []).append(r)
    rows = []
    for (st, item), rs in groups.items():
        judged = [r for r in rs if r["result"] in ("达标", "超标")]
        nums, nds, raw_disp = [], [], []
        for r in rs:
            pv = parse_value(r["value_disp"])
            raw_disp.append(r["value_disp"])
            if pv["ok"] and not pv["nd"]:
                nums.append((pv["value"], r["value_disp"]))
            elif pv["nd"]:
                nds.append((pv["dl"] or 0, r["value_disp"]))
        if nums:
            lo = min(nds)[1] if nds else min(nums)[1]
            hi = max(nums)[1]
            rng = lo if lo == hi else f"{lo}～{hi}"
        else:
            rng = raw_disp[0] if len(set(raw_disp)) == 1 else "未检出"
        idx = [r["index"] for r in rs if isinstance(r["index"], (int, float))]
        ext = [r["exceed_times"] for r in rs if isinstance(r["exceed_times"], (int, float))]
        n_ex = sum(1 for r in judged if r["result"] == "超标")
        cls = [r["cls"] for r in rs if r["cls"] in _CLS_ORDER]
        if judged:
            res = "超标" if n_ex else "达标"
            rate = f"{n_ex / len(judged) * 100:.1f}"
        else:
            res = rs[0]["result"]
            rate = DASH
        notes = list(OrderedDict.fromkeys(
            n for r in rs for n in r["note"].split("；") if n and not n.startswith("测定温度")))
        rows.append(OrderedDict(
            station=st, item=item, unit=rs[0]["unit_disp"], n=len(rs), range=rng,
            limit=rs[0]["limit_text"], max_index=max(idx) if idx else DASH, exceed_rate=rate,
            max_exceed=max(ext) if ext else DASH,
            cls=max(cls, key=_CLS_ORDER.index) if cls else DASH,
            result=res, note="；".join(notes)))
    return rows
