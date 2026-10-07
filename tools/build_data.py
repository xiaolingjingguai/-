"""生成 app/data/substances.json（物质库）。

用法：python tools/build_data.py <HJ169附录数据目录> <chemicals 仓库根目录> <输出 json>
输入：
  表B.1.csv、表B.2.csv、表H.1.csv（HJ 169-2018 附录B、H 结构化数据）
  lem3146种终点浓度_中文名与DOE比对_20261007.xlsx（3146 种终点浓度、中文名、DOE 2026-09-17 比对值）
  风险物质理化性质_chemicals库_20261007.csv（3204 个 CAS 理化、燃爆、毒理字段及来源）
  CalebBell/chemicals 原始数据（提交 e79047588b30）：补汽化热、液体比热容、γ、20 ℃ 饱和液体密度
"""
import csv
import json
import os
import sys

import openpyxl

T20 = 293.15
R = 8.314462618


def rd(path, enc="utf-8-sig", delim=","):
    with open(path, encoding=enc) as f:
        return list(csv.DictReader(f, delimiter=delim))


def num(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def main(src, chem, out):
    C = os.path.join(chem, "chemicals")
    B1 = rd(os.path.join(src, "表B.1.csv"))
    B2 = rd(os.path.join(src, "表B.2.csv"))
    H1 = rd(os.path.join(src, "表H.1.csv"))
    P = {r["CAS号"]: r for r in rd(os.path.join(src, "风险物质理化性质_chemicals库_20261007.csv"))}

    wb = openpyxl.load_workbook(os.path.join(src, "lem3146种终点浓度_中文名与DOE比对_20261007.xlsx"), read_only=True)
    rows = wb["全部3146种"].iter_rows(values_only=True)
    next(rows)
    LEM = {}
    for r in rows:
        cas = str(r[2]).strip() if r[2] else ""
        if not cas:
            continue
        LEM[cas] = {"en": r[1], "cn": r[3], "cn_src": r[4], "ep1": num(r[14]), "ep2": num(r[15]),
                    "doe1": num(r[27]), "doe2": num(r[28]), "cmp": r[33]}

    hv = {r["CAS"]: r for r in rd(os.path.join(C, "Phase Change/CRC Handbook Heat of Vaporization.tsv"), "utf-8", "\t")}
    crc = {r["CAS"]: r for r in rd(os.path.join(C, "Heat Capacity/CRC Standard Thermodynamic Properties of Chemical Substances.tsv"), "utf-8", "\t")}
    p100 = {r["CAS"]: r for r in rd(os.path.join(C, "Heat Capacity/Perry_Table_2-153_DIPPR_100.tsv"), "utf-8", "\t")}
    p114 = {r["CAS"]: r for r in rd(os.path.join(C, "Heat Capacity/Perry_Table_2-153_DIPPR_114.tsv"), "utf-8", "\t")}
    p105 = {r["CAS"]: r for r in rd(os.path.join(C, "Density/Perry Parameters 105.tsv"), "utf-8", "\t")}
    tc = {}
    with open(os.path.join(C, "Critical Properties/DIPPRPinaMartines.tsv"), encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if p[0] != "CAS" and len(p) > 1:
                tc[p[0]] = p[1]

    subs = {}

    def rec(cas):
        if cas not in subs:
            subs[cas] = {"cas": cas, "cn": "", "en": "", "cn_src": "", "b1": [], "h1": None, "lem": None, "p": {}}
        return subs[cas]

    for i, r in enumerate(B1):
        cas = r["CAS号"].strip()
        key = cas if cas not in ("", "/") else "无CAS-%d" % (i + 1)
        s = rec(key)
        s["b1"].append([r["物质名称"], num(r["临界量/t"]), r["备注"]])
        if not s["cn"]:
            s["cn"], s["cn_src"] = r["物质名称"], "HJ 169-2018 表B.1"
    for r in H1:
        cas = r["CAS号"].strip()
        if cas in ("", "/"):
            continue
        s = rec(cas)
        s["h1"] = [r["毒性终点浓度-1/(mg/m3)"], r["毒性终点浓度-2/(mg/m3)"]]
        if not s["cn"]:
            s["cn"], s["cn_src"] = r["物质名称"], "HJ 169-2018 表H.1"
    for cas, l in LEM.items():
        s = rec(cas)
        s["lem"] = [l["ep1"], l["ep2"], l["doe1"], l["doe2"], l["cmp"]]
        if not s["en"]:
            s["en"] = l["en"] or ""
        if not s["cn"] and l["cn"]:
            s["cn"], s["cn_src"] = l["cn"], l["cn_src"] or ""

    FIELDS = [  # (键, 数值列, 来源列)
        ("formula", "分子式", "分子式/分子量来源"), ("mw", "分子量/(g/mol)", "分子式/分子量来源"),
        ("mp", "熔点/℃", "熔点来源"), ("tb", "沸点/℃", "沸点来源"), ("fp", "闪点/℃", "闪点来源"),
        ("ait", "自燃点/℃", "自燃点来源"), ("lel", "爆炸下限/%(V/V)", "爆炸极限来源"), ("uel", "爆炸上限/%(V/V)", "爆炸极限来源"),
        ("pv20", "20℃饱和蒸气压/kPa", "蒸气压来源"), ("rhoL", "密度/(g/cm3)（≈相对密度，水=1）", "密度来源"),
        ("rhoG", "气体密度/(g/L)", "密度来源"), ("vd", "相对蒸气密度（空气=1）", ""),
        ("iarc", "IARC致癌分类", "IARC来源"), ("ld50o", "LD50经口（大鼠）", "LD50经口（大鼠）来源"),
        ("ld50d", "LD50经皮（兔/大鼠）", "LD50经皮（兔/大鼠）来源"), ("lc50", "LC50吸入（大鼠）", "LC50吸入（大鼠）来源"),
        ("sol", "水溶性（原文）", "水溶性来源"),
    ]
    TEXT = {"formula", "iarc", "ld50o", "ld50d", "lc50", "sol"}
    for cas, r in P.items():
        s = rec(cas)
        if not s["en"]:
            s["en"] = r["英文名"]
        if not s["cn"] and r["中文名"]:
            s["cn"], s["cn_src"] = r["中文名"], "理化性质库"
        for k, col, scol in FIELDS:
            v = r.get(col, "")
            if not v or v == "信息不足" or v == "未列入":
                if k == "iarc" and v == "未列入":
                    s["p"][k] = ["未列入", ""]
                continue
            s["p"][k] = [v if k in TEXT else num(v), r.get(scol, "") if scol else ""]
            if k not in TEXT and s["p"][k][0] is None:
                del s["p"][k]

    for cas, s in subs.items():
        p = s["p"]
        mw = p.get("mw", [None])[0]
        if not mw:
            continue
        if cas in hv and num(hv[cas]["HvapTb"]):
            p["hvTb"] = [round(num(hv[cas]["HvapTb"]) / mw * 1000),
                         "CRC手册·Heat of Vaporization（正常沸点 %s K，%s J/mol，按分子量换算）" % (hv[cas]["Tb"], hv[cas]["HvapTb"])]
        if cas in crc:
            cpg = num(crc[cas]["Cpg"])
            if cpg:
                p["gamma"] = [round(cpg / (cpg - R), 3), "CRC手册·标准热力学性质，298.15 K 理想气体 Cp=%s J/(mol·K)，γ=Cp/(Cp−R)" % crc[cas]["Cpg"]]
            cpl = num(crc[cas]["Cpl"])
            if cpl:
                p["cpL"] = [round(cpl / mw * 1000), "CRC手册·标准热力学性质，298.15 K 液体 Cp=%s J/(mol·K)" % crc[cas]["Cpl"]]
        if "cpL" not in p and cas in p100:
            r = p100[cas]
            a, b, c, d, e = [num(r[k]) or 0 for k in "ABCDE"]
            if num(r["Tmin"]) <= T20 <= num(r["Tmax"]):
                v = a + b * T20 + c * T20 ** 2 + d * T20 ** 3 + e * T20 ** 4
                p["cpL"] = [round(v / mw), "Perry手册8版表2-153（DIPPR式100，20 ℃，适用 %s～%s K）" % (r["Tmin"], r["Tmax"])]
        elif "cpL" not in p and cas in p114 and cas in tc:
            r = p114[cas]
            a, b, c, d = [num(r[k]) or 0 for k in "ABCD"]
            t = 1 - T20 / float(tc[cas])
            if num(r["Tmin"]) <= T20 <= num(r["Tmax"]):
                v = a * a / t + b - 2 * a * c * t - a * d * t ** 2 - c * c * t ** 3 / 3 - c * d * t ** 4 / 2 - d * d * t ** 5 / 5
                p["cpL"] = [round(v / mw), "Perry手册8版表2-153（DIPPR式114，20 ℃，Tc=%s K 取 DIPPR，适用 %s～%s K）" % (tc[cas], r["Tmin"], r["Tmax"])]
        if cas in p105:
            r = p105[cas]
            c1, c2, c3, c4, lo, hi = [num(r[k]) for k in ("C1", "C2", "C3", "C4", "Tmin", "Tmax")]
            if lo <= T20 <= hi and T20 < c3:
                p["rhoL20"] = [round(c1 / c2 ** (1 + (1 - T20 / c3) ** c4) * mw / 1000, 1),
                               "Perry手册8版表2-32（DIPPR式105，20 ℃ 饱和液体，适用 %s～%s K）" % (r["Tmin"], r["Tmax"])]

    data = {
        "version": "2026-10-07",
        "subs": sorted(subs.values(), key=lambda s: (not s["b1"], not s["h1"], s["cn"] or s["en"])),
        "b2": [[r["物质"], num(r["推荐临界量/t"]), r["分类依据"]] for r in B2],
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print("物质记录", len(subs), "表B.1", sum(1 for s in subs.values() if s["b1"]), "表H.1",
          sum(1 for s in subs.values() if s["h1"]), "终点浓度(lem)", sum(1 for s in subs.values() if s["lem"]))


if __name__ == "__main__":
    main(*sys.argv[1:4])
