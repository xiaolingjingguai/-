# -*- coding: utf-8 -*-
"""
地下水质量判定模块（GB/T 14848-2017）

评价方法：
1. 单指标评价：GB/T 14848-2017 第6.2条，"按指标值所在的限值范围确定地下水质量类别，
   指标限值相同时，从优不从劣"。
2. 综合评价：GB/T 14848-2017 第6.3条，"按单指标评价结果最差的类别确定，并指出最差类别的指标"。
3. 达标判定与标准指数：对照目标类别（一般为Ⅲ类）。标准指数按 HJ 610-2016《环境影响评价技术导则
   地下水环境》第8.4.1.2条公式（2）~（4）：
     一般指标  P_i = C_i / C_si
     pH        pH ≤ 7.0 时 P_pH = (7.0 - pH) / (7.0 - pH_sd)
               pH > 7.0 时 P_pH = (pH - 7.0) / (pH_su - 7.0)
               Ⅰ~Ⅲ类 pH_sd = 6.5、pH_su = 8.5；Ⅳ类 pH_sd = 5.5、pH_su = 9.0
   P > 1 为超标；超标倍数 = (C_i - C_si) / C_si，pH 不计算超标倍数。
4. 未检出：检出限不高于Ⅰ类限值的记"Ⅰ类"；检出限高于Ⅰ类限值的记"≤X类"（检出限只能证明
   不劣于X类），此类指标不参与综合类别判定，在综合评价表中单独列出；标准指数记"—"；
   检出限高于目标类别限值时，记"检出限高于标准限值，无法判定"。
"""
import re
from collections import OrderedDict
from judge import _norm, parse_value, fmt_num, fmt_limit, DASH
from gb14848_limits import TABLE1, TABLE2

CLASSES = ["I", "II", "III", "IV", "V"]
CN = ["Ⅰ类", "Ⅱ类", "Ⅲ类", "Ⅳ类", "Ⅴ类"]
RADIO_OVER = "＞Ⅲ类"          # 放射性指标超过Ⅲ类上限，Ⅳ、Ⅴ类原文均为"＞"，无法细分
RANK = {c: i for i, c in enumerate(CN)}
RANK[RADIO_OVER] = 3

_INDEX = {}
for _tb, _rows in (("表1", TABLE1), ("表2", TABLE2)):
    for _r in _rows:
        for _a in [_r["name"]] + _r.get("aliases", []):
            _INDEX.setdefault(_norm(_a), (_tb, _r))


def match_item(name):
    key = _norm(name)
    if key in _INDEX:
        return _INDEX[key]
    key2 = re.sub(r"以.{1,8}计$", "", key)
    if key2 in _INDEX:
        return _INDEX[key2]
    # 报告常写"总铅、总锌"等（测定的即总量），按标准中的"铅、锌"判定
    m = re.match(r"^总(铜|锌|铅|镉|汞|砷|硒|铁|锰|镍|钡|钴|钼|铍|硼|锑|银|铊|钠)$", key2)
    if m and m.group(1) in _INDEX:
        return _INDEX[m.group(1)]
    return None, None


def unit_factor(unit, std_unit):
    u, su = _norm(unit or ""), _norm(std_unit)
    if not u or u == su:
        return 1.0, ""
    if su == "mg/l" and u in ("μg/l", "ug/l", "µg/l"):
        return 0.001, "μg/L 已换算为 mg/L"
    if su == "μg/l" and u == "mg/l":
        return 1000.0, "mg/L 已换算为 μg/L"
    if su == "μg/l" and u in ("ug/l", "µg/l"):
        return 1.0, ""
    if su == "铂钴色度单位" and u in ("度", "倍", "pt-co", "铂钴色度"):
        return 1.0, ""
    if su == "mpn/100ml" and u in ("cfu/100ml", "个/100ml"):
        return 1.0, ""
    if su == "mpn/100ml" and u in ("mpn/l", "个/l", "cfu/l"):
        return 0.1, f"{unit} 已换算为 MPN/100mL"
    if su == "cfu/ml" and u in ("个/ml",):
        return 1.0, ""
    if su in ("", "无量纲") and u in ("无量纲", "/"):
        return 1.0, ""
    return None, f"单位 {unit} 与标准单位 {std_unit} 不一致，无法自动换算"


def _class_le(row, v):
    """数值型指标：返回类别序号 0~4（从优不从劣）。"""
    for i, lim in enumerate(row["values"]):
        if lim is not None and v <= lim:
            return i
    return 4


def _class_ph(v):
    if 6.5 <= v <= 8.5:
        return 0
    if 5.5 <= v < 6.5 or 8.5 < v <= 9.0:
        return 3
    return 4


def _target_limit_text(row, t):
    kind = row.get("kind", "le")
    if kind == "ph":
        return "6.5～8.5" if t <= 2 else ("5.5～9.0" if t == 3 else DASH)
    if kind == "text":
        return "无"
    if t >= 4:
        return DASH
    if kind == "radio" and t >= 3:
        return DASH
    lim = row["values"][t]
    if lim is None:
        return "不得检出"
    return "≤" + fmt_limit(lim)


def judge_one(rec, target_class="III"):
    t = CLASSES.index(target_class)
    out = dict(rec)
    out.update(value_disp=str(rec["value"]), unit_disp=rec.get("unit") or "", std_name=rec["item"],
               table=None, limit_text=DASH, index=DASH, exceed_times=DASH, cls=DASH,
               result="", note="")
    table, row = match_item(rec["item"])
    if row is None:
        out["result"] = "GB/T 14848-2017 未列此指标"
        return out
    out.update(std_name=row["name"], table=table, limit_text=_target_limit_text(row, t))
    kind = row.get("kind", "le")
    notes = []
    raw = str(rec["value"]).strip()

    if kind == "text":
        if raw in ("无", "未检出", "未见"):
            ci = 0
        elif raw in ("有",):
            ci = 4
        else:
            out["result"] = "监测值无法识别"
            return out
        out["cls"] = CN[ci]
        out["result"] = "达标" if ci <= t else "超标"
        return out

    pv = parse_value(rec["value"])
    if not pv["ok"]:
        out["result"] = "监测值无法识别"
        return out
    f, unote = unit_factor(rec.get("unit"), row["unit"])
    if unote:
        notes.append(unote)
    if f is None:
        out["result"] = "单位无法换算，未判定"
        out["note"] = "；".join(notes)
        return out
    if f != 1.0:
        out["unit_disp"] = row["unit"]
        out["value_disp"] = (f"{fmt_num(pv['dl'] * f)}L" if pv["nd"] and pv["dl"] is not None
                             else ("未检出" if pv["nd"] else fmt_num(pv["value"] * f)))

    # ---------- 未检出
    if pv["nd"]:
        if kind == "nd_I":
            ci = 0
        elif pv["dl"] is None:
            # 无检出限：只能认为不劣于目标类别
            ci = None
            notes.append(f"{row['name']}报告仅注明未检出、未给出检出限，按达标计，类别未定")
        else:
            ci = _class_le(row, pv["dl"] * f) if kind != "radio" else None
        if ci is None and pv["dl"] is not None and kind == "radio":
            ci = _class_le(dict(values=row["values"] + [float("inf")]), pv["dl"] * f)
        if ci is not None:
            # 检出限能证明属于Ⅰ类时记"Ⅰ类"；否则记"≤X类"（只能证明不劣于X类），不参与综合类别判定
            out["cls"] = CN[ci] if ci == 0 else "≤" + CN[ci]
        ok = ci is None or ci <= t
        out["result"] = "达标" if ok else "检出限高于标准限值，无法判定"
        out["note"] = "；".join(notes)
        return out

    v = pv["value"] * f
    # ---------- pH
    if kind == "ph":
        ci = _class_ph(v)
        sd, su = (6.5, 8.5) if t <= 2 else (5.5, 9.0)
        out["index"] = round((7.0 - v) / (7.0 - sd) if v <= 7.0 else (v - 7.0) / (su - 7.0), 2)
        out["cls"] = CN[ci]
        out["result"] = "达标" if ci <= t else "超标"
        out["note"] = "；".join(notes)
        return out
    # ---------- 放射性
    if kind == "radio":
        ci = _class_le(dict(values=row["values"] + [float("inf")]), v)
        out["cls"] = CN[ci] if ci <= 2 else RADIO_OVER
        if ci > 2:
            notes.append("放射性指标超过指导值，应进行核素分析和评价（原文表1注d）")
    # ---------- 阴离子表面活性剂：检出即不属Ⅰ类
    elif kind == "nd_I":
        ci = _class_le(row, v)          # Ⅰ类限值为 None（不得检出），自动跳过
        out["cls"] = CN[ci]
    else:
        ci = _class_le(row, v)
        out["cls"] = CN[ci]
    if t < 4 and not (kind == "radio" and t >= 3) and row["values"][t] is not None:
        cs = row["values"][t]
        out["index"] = round(v / cs, 2)
        if v > cs:
            out["exceed_times"] = round((v - cs) / cs, 2)
    out["result"] = "达标" if (ci <= t) else "超标"
    out["note"] = "；".join(notes)
    return out


def evaluate(records, target_class="III"):
    out = []
    for r in records:
        o = judge_one(r, target_class)
        _cmp_limit(o, r)
        out.append(o)
    return out


def _cmp_limit(out, rec):
    rl = str(rec.get("report_limit") or "").strip()
    if not rl or rl in ("/", "—", "-") or out["limit_text"] == DASH:
        return
    nums = lambda s: [float(x) for x in re.findall(r"\d+(?:\.\d+)?", s)]
    if nums(rl) != nums(out["limit_text"]):
        out["note"] = "；".join(x for x in (out["note"], f"报告标准值{rl}与本库限值{out['limit_text']}不一致，请核对") if x)


def summarize(results):
    """按 监测点 × 指标 汇总（字段与地表水模块一致，便于共用导出）。"""
    groups = OrderedDict()
    order = list(OrderedDict.fromkeys(r["station"] for r in results))
    for r in sorted(results, key=lambda r: order.index(r["station"])):
        groups.setdefault((r["station"], r["std_name"]), []).append(r)
    rows = []
    for (st, item), rs in groups.items():
        judged = [r for r in rs if r["result"] in ("达标", "超标")]
        nums, nds = [], []
        for r in rs:
            pv = parse_value(r["value_disp"])
            if pv["ok"] and not pv["nd"]:
                nums.append((pv["value"], r["value_disp"]))
            elif pv["nd"]:
                nds.append((pv["dl"] or 0, r["value_disp"]))
        if nums:
            lo = min(nds)[1] if nds else min(nums)[1]
            hi = max(nums)[1]
            rng = lo if lo == hi else f"{lo}～{hi}"
        else:
            vals = list(OrderedDict.fromkeys(r["value_disp"] for r in rs))
            rng = "、".join(vals)
        idx = [r["index"] for r in rs if isinstance(r["index"], (int, float))]
        ext = [r["exceed_times"] for r in rs if isinstance(r["exceed_times"], (int, float))]
        n_ex = sum(1 for r in judged if r["result"] == "超标")
        cls = [r["cls"] for r in rs if r["cls"] in RANK]
        nd_cls = [r["cls"] for r in rs if r["cls"].startswith("≤")]
        notes = list(OrderedDict.fromkeys(
            n for r in rs for n in r["note"].split("；") if n and not n.startswith("测定温度")))
        rows.append(OrderedDict(
            station=st, item=item, unit=rs[0]["unit_disp"], n=len(rs), range=rng,
            limit=rs[0]["limit_text"], max_index=max(idx) if idx else DASH,
            exceed_rate=f"{n_ex / len(judged) * 100:.1f}" if judged else DASH,
            max_exceed=max(ext) if ext else DASH,
            cls=max(cls, key=RANK.get) if cls else (nd_cls[0] if nd_cls else DASH),
            result=("超标" if n_ex else "达标") if judged else rs[0]["result"],
            note="；".join(notes)))
    return rows


def overall(results):
    """GB/T 14848-2017 第6.3条综合评价：每个监测点（每次采样）取单指标最差类别，并列出最差类别指标。"""
    groups = OrderedDict()
    for r in results:
        groups.setdefault((r["station"], r["date"]), []).append(r)
    rows = []
    for (st, d), rs in groups.items():
        cls = [r for r in rs if r["cls"] in RANK]
        if not cls:
            continue
        worst = max(RANK[r["cls"]] for r in cls)
        worst_items = [r["std_name"] for r in cls if RANK[r["cls"]] == worst]
        nd_items = [f"{r['std_name']}（{r['cls']}）" for r in rs if r["cls"].startswith("≤")]
        rows.append(OrderedDict(station=st, date=d, cls=[c for c, k in RANK.items() if k == worst][0],
                                worst_items=("—（检出指标均为Ⅰ类）" if worst == 0
                                             else "、".join(OrderedDict.fromkeys(worst_items))),
                                n=len(cls), nd_items="、".join(nd_items) or DASH))
    return rows


def statistics(results):
    """
    HJ 610-2016 第8.4.1.1条要求的统计分析：按指标统计全部监测点位的
    最小值、最大值、均值、标准差、检出率、超标率。
    最小值、最大值、均值、标准差仅以检出值计算（未检出样不参与）；标准差为样本标准差（n-1），
    检出值少于 2 个时记"—"。
    """
    import statistics as st
    groups = OrderedDict()
    for r in results:
        if r["table"] is None:
            continue
        groups.setdefault(r["std_name"], []).append(r)
    rows = []
    for item, rs in groups.items():
        vals, n_det = [], 0
        for r in rs:
            pv = parse_value(r["value_disp"])
            if pv["ok"] and not pv["nd"]:
                vals.append(pv["value"])
                n_det += 1
            elif not pv["ok"] and r["value_disp"] in ("有",):
                n_det += 1
        judged = [r for r in rs if r["result"] in ("达标", "超标")]
        n_ex = sum(1 for r in judged if r["result"] == "超标")
        f = lambda x: fmt_num(float(f"{x:.4g}"))
        rows.append(OrderedDict(
            item=item, unit=rs[0]["unit_disp"], n=len(rs), n_det=n_det,
            det_rate=f"{n_det / len(rs) * 100:.1f}",
            min=f(min(vals)) if vals else "未检出", max=f(max(vals)) if vals else "未检出",
            mean=f(st.mean(vals)) if vals else DASH,
            sd=f(st.stdev(vals)) if len(vals) >= 2 else DASH,
            exceed_rate=f"{n_ex / len(judged) * 100:.1f}" if judged else DASH))
    return rows
