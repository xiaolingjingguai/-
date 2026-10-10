# -*- coding: utf-8 -*-
"""
核对表"所选标准限值"列：按当前评价参数取本软件标准库限值，并与报告所列标准值比较。
限值取自与"开始判定"相同的判定函数（pipeline.assess 的逐样结果），保证核对表与判定结果一致。
"""
import re

import pipeline
from judge import DASH

_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")


def nums(text):
    """提取数值（识别 a×10^b、a×10ⁿ 写法）"""
    t = str(text or "").translate(_SUP).replace("^", "")
    out = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)(?:\s*[×xX]\s*10\s*(-?\d+))?", t):
        v = float(m.group(1))
        if m.group(2):
            v *= 10 ** int(m.group(2))
        out.append(v)
    return out


def lib_text(kind, det):
    """逐样判定结果 → 显示用限值文字"""
    if kind == pipeline.SOIL:
        if det.get("screen") in (None, "", DASH):
            if "pH" in str(det.get("note", "")) and det.get("std_name") != "pH":
                return "缺少该样品pH，无法定档"
            return DASH
        c = det.get("control")
        return f"筛选值 {det['screen']}" + (f" / 管制值 {c}" if c not in (None, "", DASH) else "")
    if kind in pipeline.EMISSION:
        t = str(det.get("limit_text") or DASH)
        if t == DASH and det.get("result") not in ("达标", "超标", ""):
            return det["result"]
        if t != DASH and det.get("metric") == "rate":
            t += " kg/h"
        if t != DASH and kind == pipeline.BNOISE:
            t += " dB(A)"
        return t
    t = str(det.get("limit_text") or DASH)
    if kind == pipeline.AIR and t != DASH and det.get("unit_disp"):
        t += " " + det["unit_disp"]
    if kind == pipeline.NOISE and t != DASH:
        t += " dB(A)"
    return t


def mismatch(kind, rec, det):
    """报告标准值与所选限值不一致返回 True；任一方缺失返回 False"""
    rep = nums(rec.get("report_limit"))
    if not rep:
        return False
    if kind == pipeline.SOIL:
        lib = nums(det.get("screen")) + nums(det.get("control"))
    else:
        lib = nums(det.get("limit_text"))
    if not lib or str(det.get("limit_text", "")) == DASH and kind != pipeline.SOIL:
        return False
    f = 1.0
    if kind == pipeline.AIR:
        import air_judge
        f = air_judge.unit_factor(rec.get("unit"), det.get("unit_disp") or "") or 1.0
    return any(all(abs(r * f - x) > 1e-9 * max(1.0, abs(x)) for x in lib) for r in rep)


def compute(records, kind, params):
    """返回 [(显示文字, 是否不一致)]，与 records 一一对应"""
    if not records:
        return []
    detail = pipeline.assess([dict(r) for r in records], kind, **params)["detail"]
    return [(lib_text(kind, d), mismatch(kind, r, d)) for r, d in zip(records, detail)]
