# -*- coding: utf-8 -*-
"""
海洋沉积物质量（GB 18668-2002）、海洋生物质量（GB 18421-2001）现状判定

1. 单因子标准指数 P = C / C0（C0 为所选类别标准值），P ≤ 1 为符合，P > 1 为超标；
   超标倍数 = (C - C0) / C0（仅超标时计算）。
2. 同时给出单因子所符合的最优类别（第一类 / 第二类 / 第三类 / 劣于第三类）。
3. 未检出：检出限 ≤ C0 判符合，标准指数记"—"；检出限 > C0 无法判定。
4. 沉积物：重金属等以干重计，有机碳以 % 计；大肠菌群、粪大肠菌群第三类不作要求。
5. 生物质量：标准仅适用于海洋贝类（双壳类），以去壳部分鲜重计；报告注明干重的不作换算，提示人工核对含水率；
   样品名称含鱼、虾、蟹、头足类等非双壳类的，判"不适用"。牡蛎的铜、锌第三类按表 1 括号内数值。
"""
import re
from collections import OrderedDict

from judge import parse_value, fmt_num, fmt_limit, _norm, DASH
from marine_limits import SEDIMENT, BIOTA, SED_INFO, BIO_INFO, CLASS_CN

SED, BIO = "sediment", "biota"
INFO = {SED: SED_INFO, BIO: BIO_INFO}
_IDX = {SED: {}, BIO: {}}
for _k, _rows in ((SED, SEDIMENT), (BIO, BIOTA)):
    for _r in _rows:
        for _a in [_r["name"]] + _r["aliases"]:
            _IDX[_k].setdefault(_norm(_a), _r)

NON_BIVALVE = r"鱼|虾|蟹|鱿|乌贼|章鱼|墨鱼|头足|藻|海参|海胆|螺"
OYSTER = r"牡蛎|蚝"


def _key(name):
    k = _norm(name)
    k = re.sub(r"以.{1,6}计$", "", k)
    k = re.sub(r"(干重|湿重|鲜重)$", "", k)
    return k


def match_item(name, kind=SED):
    return ("表1", _IDX[kind][_key(name)]) if _key(name) in _IDX[kind] else (None, None)


def matcher(kind):
    return lambda name: match_item(name, kind)


def unit_factor(unit, std_unit):
    """返回 (系数, 说明)；无法换算返回 (None, 说明)"""
    u = (unit or "").replace("µ", "μ").replace("ug", "μg").replace(" ", "").lower()
    u = u.replace("（", "(").replace("）", ")")
    s = std_unit.lower()
    if not u:
        return 1.0, "报告未注明单位，按标准单位计"
    if s == "%":
        if u.startswith("%") or "10-2" in u or "10⁻²" in u:
            return 1.0, ""
        if u.startswith("g/kg"):
            return 0.1, ""
        if u.startswith("mg/kg"):
            return 1e-4, ""
        return None, f"单位 {unit} 无法换算为 %"
    if s.startswith("个/"):
        su = s.split("/")[1]
        if u.startswith("个/") or u.startswith("mpn/") or u.startswith("cfu/"):
            uu = u.split("/")[1]
            if uu.startswith(su[:2]):
                return 1.0, ""
            if su.startswith("kg") and uu.startswith("g"):
                return 1000.0, ""
            if su.startswith("g") and uu.startswith("kg"):
                return 0.001, ""
            if su.startswith("kg") and uu.startswith("100g"):
                return 10.0, ""
        return None, f"单位 {unit} 无法换算为 {std_unit}"
    if u.startswith(("mg/kg", "μg/g", "10-6", "×10-6", "×10⁻⁶", "10⁻⁶")):
        return 1.0, ""
    if u.startswith(("μg/kg", "ng/g")):
        return 0.001, ""
    if u.startswith("ng/kg"):
        return 1e-6, ""
    return None, f"单位 {unit} 无法换算为 {std_unit}"


def _best_class(c, values):
    for i, v in enumerate(values):
        if v is not None and c <= v:
            return CLASS_CN[i + 1]
    if values[2] is None:
        return "劣于第二类"
    return "劣于第三类"


def judge_one(rec, kind=SED, cls=1):
    out = dict(rec)
    out.update(std_name=rec["item"], limit_text=DASH, index=DASH, exceed_times=DASH, cls=DASH,
               result="", note="", value_disp=rec["value"], unit_disp=rec.get("unit", ""))
    notes = []
    _, row = match_item(rec["item"], kind)
    if row is None:
        out["result"] = f"{INFO[kind]['code']} 未列此项目"
        return out
    out["std_name"] = row["name"]
    sample = " ".join(str(rec.get(k, "")) for k in ("station", "species", "raw"))
    values = row["values"]
    if kind == BIO:
        if re.search(NON_BIVALVE, sample):
            out["result"] = "不适用"
            out["note"] = "GB 18421-2001 仅适用于海洋贝类（双壳类），该样品不属于双壳贝类，评价依据须另行确定（信息不足）"
            return out
        if row.get("oyster") and re.search(OYSTER, sample):
            values = row["oyster"]
            if cls == 3:
                notes.append("牡蛎按表1第三类括号内数值")
        if re.search(r"干重", (rec.get("unit") or "") + sample):
            out["result"] = "以干重计，无法直接判定"
            out["note"] = "标准以去壳部分鲜重计（表1注1），须按样品含水率换算后判定"
            return out
    c0 = values[cls - 1]
    if c0 is None:
        out["result"] = "该类别不作要求"
        return out
    out["limit_text"] = fmt_limit(c0)
    if row.get("note"):
        notes.append(row["note"])
    f, why = unit_factor(rec.get("unit"), row["unit"])
    if f is None:
        out["result"] = "单位无法换算"
        out["note"] = why
        return out
    if why:
        notes.append(why)
    out["unit_disp"] = row["unit"]
    pv = parse_value(rec["value"])
    if not pv["ok"]:
        out["result"] = "数值无法识别"
        return out
    if pv["nd"]:
        dl = (pv["dl"] or 0) * f
        out["value_disp"] = f"{fmt_num(dl)}L" if pv["dl"] else "未检出"
        if pv["dl"] is None or dl <= c0:
            out["result"] = "符合"
            out["cls"] = _best_class(dl, values) if pv["dl"] else CLASS_CN[1]
            notes.append("未检出")
        else:
            out["result"] = "检出限高于标准值，无法判定"
    else:
        c = pv["value"] * f
        out["value_disp"] = fmt_num(c)
        out["index"] = round(c / c0, 3)
        out["cls"] = _best_class(c, values)
        if c > c0:
            out["result"] = "超标"
            out["exceed_times"] = round((c - c0) / c0, 2)
        else:
            out["result"] = "符合"
    out["note"] = "；".join(dict.fromkeys(n for n in notes if n))
    return out


def evaluate(records, kind=SED, cls=1):
    return [judge_one(r, kind, cls) for r in records]


def summarize(results):
    """按 站位 × 项目 汇总"""
    groups = OrderedDict()
    st_order = list(OrderedDict.fromkeys(r["station"] for r in results))
    for r in sorted(results, key=lambda r: st_order.index(r["station"])):
        groups.setdefault((r["station"], r["std_name"]), []).append(r)
    order = [CLASS_CN[1], CLASS_CN[2], CLASS_CN[3], "劣于第二类", "劣于第三类"]
    rows = []
    for (st, item), rs in groups.items():
        judged = [r for r in rs if r["result"] in ("符合", "超标")]
        vals = [str(r["value_disp"]) for r in rs]
        nums = [(parse_value(v)["value"], v) for v in vals if parse_value(v)["ok"] and not parse_value(v)["nd"]]
        if len(set(vals)) == 1:
            rng = vals[0]
        elif nums:
            rng = f"{min(nums)[1]}～{max(nums)[1]}"
        else:
            rng = vals[0]
        idx = [r["index"] for r in rs if isinstance(r["index"], (int, float))]
        ext = [r["exceed_times"] for r in rs if isinstance(r["exceed_times"], (int, float))]
        cls = [r["cls"] for r in rs if r["cls"] in order]
        n_ex = sum(1 for r in judged if r["result"] == "超标")
        res = ("超标" if n_ex else "符合") if judged else rs[0]["result"]
        notes = list(OrderedDict.fromkeys(n for r in rs for n in (r["note"] + "；" + (r.get("src_note") or "")).split("；") if n))
        rows.append(OrderedDict(
            station=st, item=item, unit=rs[0]["unit_disp"], n=len(rs), range=rng, limit=rs[0]["limit_text"],
            max_index=max(idx) if idx else DASH, exceed_rate=f"{n_ex / len(judged) * 100:.1f}" if judged else DASH,
            max_exceed=max(ext) if ext else DASH, cls=max(cls, key=order.index) if cls else DASH,
            result=res, note="；".join(notes)))
    return rows
