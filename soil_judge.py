# -*- coding: utf-8 -*-
"""
土壤环境质量现状判定

建设用地：GB 36600—2018，按所选第一类/第二类用地的风险筛选值、管制值判定（第 5.3.1 条）。
农用地：GB 15618—2018，按样品 pH 所在分档及用地类型（水田/其他/果园）取筛选值；镉、汞、砷、铅、铬另与表 3 管制值比较。

结果分级（建设用地第 5.3.2~5.3.5 条；农用地第 6.1~6.3 条）：
  ≤ 筛选值              → "未超筛选值"（风险一般情况下可以忽略 / 风险低）
  ＞ 筛选值、≤ 管制值   → "超筛选值"
  ＞ 管制值             → "超管制值"
标准指数 P = C / 筛选值；超筛选值倍数 = (C - 筛选值) / 筛选值（仅超筛选值时计算）。
未检出：检出限 ≤ 筛选值判"未超筛选值"；检出限 > 筛选值无法判定。
"""
import re
from collections import OrderedDict

from judge import parse_value, fmt_num, fmt_limit, _norm, DASH
import gb36600_limits as B
import gb15618_limits as F

LAND_CN = {"build1": "建设用地第一类用地", "build2": "建设用地第二类用地",
           "paddy": "农用地（水田）", "other": "农用地（其他）", "orchard": "农用地（果园）"}

_IDX_B, _IDX_F = {}, {}
for _tb, _rows in (("表1", B.TABLE1), ("表2", B.TABLE2)):
    for _r in _rows:
        for _a in [_r["name"]] + _r["aliases"]:
            _IDX_B.setdefault(_norm(_a), (_tb, _r))
for _r in F.TABLE1:
    for _a in [_r["name"]] + _r["aliases"]:
        _IDX_F.setdefault(_norm(_a), ("表1", _r))
for _r in F.TABLE2:
    for _a in [_r["name"]] + _r["aliases"]:
        _IDX_F.setdefault(_norm(_a), ("表2", _r))


def _key(name):
    k = _norm(name)
    k = re.sub(r"以.{1,6}计$", "", k)
    k = re.sub(r"^总(?=(砷|镉|铬|铜|铅|汞|镍|锌|锑|铍|钴|钒)$)", "", k)
    return k


def match_item(name):
    """parser 用：两部标准任一收录或为 pH 即视为土壤项目"""
    k = _key(name)
    if k in ("ph", "ph值"):
        return "pH", None
    if k in _IDX_B:
        return _IDX_B[k]
    if k in _IDX_F:
        return _IDX_F[k]
    return None, None


def unit_factor(unit):
    u = (unit or "mg/kg").replace("µ", "μ").replace("ug", "μg").lower().replace(" ", "")
    if u in ("mg/kg", "mg/kg干重", "mg/kg(干重)"):
        return 1.0
    if u.startswith("μg/kg"):
        return 0.001
    if u.startswith("ng/kg"):
        return 1e-6
    if u.startswith("g/kg"):
        return 1000.0
    if u.startswith("mg/kg"):
        return 1.0
    return None


def _limits(name, land, ph):
    """返回 (标准, 表号, 规范名称, 筛选值, 管制值, 附注) 或 None"""
    k = _key(name)
    if land in ("build1", "build2"):
        hit = _IDX_B.get(k)
        if not hit:
            return None
        tb, row = hit
        i = 0 if land == "build1" else 1
        note = "超筛选值但不高于土壤环境背景值的不纳入污染地块管理（表注①）" if row.get("bg_note") else ""
        return B.STANDARD_INFO["code"], tb, row["name"], row["screen"][i], row["control"][i], note
    hit = _IDX_F.get(k)
    if not hit:
        return None
    tb, row = hit
    if tb == "表2":
        return F.STANDARD_INFO["code"], tb, row["name"], row["value"], None, ""
    if ph is None:
        return F.STANDARD_INFO["code"], tb, row["name"], None, None, "缺少该样品 pH，无法确定筛选值档位"
    b = F.ph_bin(ph)
    vals = row["values"]
    if "*" in vals:
        sv = vals["*"][b]
    elif land == "paddy" and "水田" in vals:
        sv = vals["水田"][b]
    elif land == "orchard" and "果园" in vals:
        sv = vals["果园"][b]
    else:
        sv = vals["其他"][b]
    cv = F.TABLE3.get(row["name"], (None,) * 4)[b]
    return F.STANDARD_INFO["code"], tb, row["name"], sv, cv, f"按 {F.PH_BINS[b]} 档"


def _sample_key(r):
    return (r["station"], r.get("date", ""))


def evaluate(records, land="build2"):
    ph = {}
    for r in records:
        if match_item(r["item"])[0] == "pH":
            pv = parse_value(r["value"])
            if pv["ok"] and not pv["nd"]:
                ph[_sample_key(r)] = pv["value"]
    return [judge_one(r, land, ph.get(_sample_key(r))) for r in records]


def judge_one(rec, land="build2", ph=None):
    out = dict(rec)
    out.update(std_name=rec["item"], table=DASH, screen=DASH, control=DASH, index=DASH, exceed_times=DASH,
               result="", note="", value_disp=rec["value"], unit_disp=rec.get("unit") or "mg/kg", basis=DASH)
    if match_item(rec["item"])[0] == "pH":
        out.update(std_name="pH", unit_disp="无量纲", result="不评价",
                   note="pH 用于确定农用地筛选值档位" if land not in ("build1", "build2") else "")
        return out
    lim = _limits(rec["item"], land, ph)
    std = B.STANDARD_INFO["code"] if land in ("build1", "build2") else F.STANDARD_INFO["code"]
    if lim is None:
        out["result"] = f"{std} 未列此项目"
        return out
    code, tb, name, sv, cv, extra = lim
    out.update(std_name=name, table=tb, basis=f"{code} {tb}")
    notes = [extra] if extra and "背景值" not in extra else []
    if sv is None:
        out["result"] = "无法判定"
        out["note"] = extra
        return out
    out["screen"] = fmt_limit(sv)
    out["control"] = fmt_limit(cv) if cv is not None else DASH
    f = unit_factor(rec.get("unit"))
    if f is None:
        out["result"] = "单位无法换算"
        return out
    out["unit_disp"] = "mg/kg"
    pv = parse_value(rec["value"])
    if not pv["ok"]:
        out["result"] = "数值无法识别"
        return out
    if pv["nd"]:
        dl = (pv["dl"] or 0) * f
        out["value_disp"] = f"{fmt_num(dl)}L" if pv["dl"] else "未检出"
        if pv["dl"] is None or dl <= sv:
            out["result"] = "未超筛选值"
            notes.append("未检出")
        else:
            out["result"] = "检出限高于筛选值，无法判定"
    else:
        c = pv["value"] * f
        out["value_disp"] = fmt_num(c)
        out["index"] = round(c / sv, 3)
        if cv is not None and c > cv:
            out["result"] = "超管制值"
        elif c > sv:
            out["result"] = "超筛选值"
        else:
            out["result"] = "未超筛选值"
        if c > sv:
            out["exceed_times"] = round((c - sv) / sv, 2)
            if extra and "背景值" in extra:
                notes.append(extra)
    out["note"] = "；".join(n for n in notes if n)
    return out


_RANK = {"未超筛选值": 0, "超筛选值": 1, "超管制值": 2}


def summarize(results):
    """按 点位（样品） × 项目 汇总"""
    groups = OrderedDict()
    st_order = list(OrderedDict.fromkeys(r["station"] for r in results))
    for r in sorted(results, key=lambda r: st_order.index(r["station"])):
        groups.setdefault((r["station"], r["std_name"]), []).append(r)
    rows = []
    for (st, item), rs in groups.items():
        judged = [r for r in rs if r["result"] in _RANK]
        vals = [str(r["value_disp"]) for r in rs]
        nums = [(parse_value(v)["value"], v) for v in vals if parse_value(v)["ok"] and not parse_value(v)["nd"]]
        if len(set(vals)) == 1:
            rng = vals[0]
        elif nums:
            rng = f"{min(nums)[1]}～{max(nums)[1]}"
        else:
            rng = "未检出"
        idx = [r["index"] for r in rs if isinstance(r["index"], (int, float))]
        ext = [r["exceed_times"] for r in rs if isinstance(r["exceed_times"], (int, float))]
        n_ex = sum(1 for r in judged if _RANK[r["result"]] > 0)
        res = max((r["result"] for r in judged), key=_RANK.get) if judged else rs[0]["result"]
        notes = list(OrderedDict.fromkeys(n for r in rs for n in (r["note"] + "；" + (r.get("src_note") or "")).split("；") if n))
        rows.append(OrderedDict(
            station=st, item=item, unit=rs[0]["unit_disp"], n=len(rs), range=rng, screen=rs[0]["screen"],
            control=rs[0]["control"], max_index=max(idx) if idx else DASH,
            exceed_rate=f"{n_ex / len(judged) * 100:.1f}" if judged else DASH,
            max_exceed=max(ext) if ext else DASH, result=res, note="；".join(notes)))
    return rows
