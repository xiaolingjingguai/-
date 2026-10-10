# -*- coding: utf-8 -*-
"""排放标准大类（废水、有组织废气、无组织废气、厂界噪声）的导出表头、表题、表注（写出复用 export.write_excel / write_word）"""
from export import write_excel, write_word, collect_notes
import emission_judge as E
import gb8978_limits as W
import gb16297_limits as A
import gb13271_gb12348_limits as BN
import gb14554_limits as O

EM_HEAD = ["监测点位", "监测项目", "单位", "样本数", "监测值范围", "标准限值", "最大超标倍数", "超标率（%）", "达标情况", "备注"]
EM_KEYS = ["station", "item", "unit", "n", "range", "limit", "max_exceed", "exceed_rate", "result", "note"]
STACK_HEAD = ["排气筒/点位", "污染物", "指标", "单位", "排气筒高度（m）", "样本数", "监测值范围", "标准限值", "最大超标倍数",
              "超标率（%）", "达标情况", "备注"]
STACK_KEYS = ["station", "item", "metric", "unit", "height", "n", "range", "limit", "max_exceed", "exceed_rate",
              "result", "note"]
BN_HEAD = ["监测点位", "监测日期", "时段", "测量时间", "测量值（dB(A)）", "标准限值（dB(A)）", "超标量（dB(A)）", "评价依据",
           "达标情况", "备注"]
BN_KEYS = ["station", "date", "period", "time", "value", "limit", "over", "basis", "result", "note"]
DETAIL_HEAD = ["监测点位", "采样日期/频次", "监测项目（报告原名）", "对应标准项目", "指标", "监测值", "单位", "标准限值",
               "超标倍数", "判定结果", "评价依据", "备注"]
DETAIL_KEYS = ["station", "date", "item", "std_name", "metric_cn", "value_disp", "unit", "limit_text", "exceed_times",
               "result", "basis", "note"]

COMMON_NOTE = ("行业排放标准优先于综合排放标准；福建省地方排放标准（DB35）有规定且严于国家标准的应优先执行，"
               "本软件未录入地方标准与行业标准，执行标准须按项目环评批复、排污许可证核实（信息不足之处须复核）")


def heads(kind):
    if kind in E.GAS:
        return STACK_HEAD, STACK_KEYS
    if kind == E.BNOISE:
        return BN_HEAD, BN_KEYS
    return EM_HEAD, EM_KEYS


def _fuels(p):
    """锅炉燃料：按各点位名称识别出的燃料（export 时写入 p["fuels"]），否则按左侧所选"""
    return p.get("fuels") or [p.get("fuel", "coal")]


def title(kind, p):
    if kind == E.ODOR_STACK:
        return "恶臭污染物有组织排放监测结果及评价（执行 GB 14554-93 表2）"
    if kind == E.ODOR_FENCE:
        return f"恶臭污染物厂界监测结果及评价（执行 GB 14554-93 表1 {O.FENCE_CN[p.get('grade', 1)]}）"
    if kind == E.WASTEWATER:
        g = p.get("grade", 1)
        return (f"废水污染物排放监测结果及评价（执行 GB 8978-1996 表4{W.GRADE_CN[g]}，"
                f"{W.IND_CN.get(p.get('industry', 'other'), '')}）")
    if kind in E.GAS:
        if kind == E.BOILER:
            fu = "、".join(BN.FUEL_CN[f] for f in _fuels(p))
            return f"锅炉废气排放监测结果及评价（执行 GB 13271-2014 {dict(BN.BOILER_TABLES)[p.get('btable', 2)]}，{fu}）"
        return f"有组织废气排放监测结果及评价（执行 GB 16297-1996 表2 {A.GRADE_CN[p.get('grade', 2)]}）"
    if kind == E.FUGITIVE:
        return "无组织废气排放监测结果及评价（执行 GB 16297-1996 表2 无组织排放监控浓度限值）"
    return f"厂界噪声监测结果及评价（执行 GB 12348-2008 {BN.BOUNDARY_CN[p.get('bcls', '3')]}）"


def note(kind, p):
    if kind == E.ODOR_STACK:
        return ("注：1. 评价标准为《恶臭污染物排放标准》（GB 14554-93）表2恶臭污染物排放标准值，"
                "八种恶臭污染物按排放量（kg/h）判定，臭气浓度按无量纲标准值判定，表2不规定排放浓度；\n"
                "2. 排气筒最低高度不得低于15 m（第6.1.1条）；介于表2所列两种高度之间的排气筒，"
                "采用四舍五入方法计算其高度（第6.1.2条）；\n"
                "3. 按生产周期确定采样频率，取其最大测定值（第6.1.4条），表中按逐次监测值判定；\n"
                f"4. {COMMON_NOTE}。")
    if kind == E.ODOR_FENCE:
        return ("注：1. 评价标准为《恶臭污染物排放标准》（GB 14554-93）表1恶臭污染物厂界标准值"
                f"{O.FENCE_CN[p.get('grade', 1)]}；排入GB 3095一类区执行一级、二类区执行二级、三类区执行三级（第4.1条），"
                "1994年6月1日起立项的新、扩、改建设项目执行新扩改建标准值（第4.2.1条）；\n"
                "2. 厂界监测点的一次最大监测值（包括臭气浓度）都必须低于或等于厂界标准值（第5.1条）；"
                "采样点设在厂界下风向侧或有臭气方位的边界线上（第6.2.1条），上风向参照点列出供对照；\n"
                f"3. {COMMON_NOTE}。")
    if kind == E.WASTEWATER:
        return ("注：1. 评价标准为《污水综合排放标准》（GB 8978-1996），第一类污染物执行表1（在车间或车间处理设施排放口采样），"
                f"第二类污染物执行表4{W.GRADE_CN[p.get('grade', 1)]}（1998年1月1日后建设的单位，第4.2.2条）；\n"
                "2. 标准分级（第4.1条）：排入GB 3838 Ⅲ类水域（保护区和游泳区除外）和GB 3097二类海域执行一级，"
                "排入Ⅳ、Ⅴ类水域和三类海域执行二级，排入设置二级污水处理厂的城镇排水系统执行三级；\n"
                "3. 超标倍数=(C-C0)/C0；未检出以\"检出限+L\"表示，检出限不高于限值的判为达标；\n"
                f"4. {COMMON_NOTE}。")
    if kind in E.GAS:
        if kind == E.BOILER:
            ref = "、".join(f"{BN.REF_O2[f]:g}%" for f in _fuels(p))
            return ("注：1. 评价标准为《锅炉大气污染物排放标准》（GB 13271-2014），排放浓度为标准状态下干烟气中的数值；\n"
                    f"2. 实测浓度按第5.2条式(1) ρ=ρ′×(21-φ(O2))/(21-φ′(O2)) 折算为基准氧含量 {ref}（燃煤9%，燃油、燃气3.5%）的排放浓度后判定，"
                    "报告已给出折算浓度的，以折算浓度判定；\n"
                    "3. GB 13271-2014 未规定排放速率限值；烟气黑度监控位置为烟囱排放口；\n"
                    f"4. {COMMON_NOTE}。")
        return ("注：1. 评价标准为《大气污染物综合排放标准》（GB 16297-1996）表2新污染源排放限值，"
                f"排放速率执行{A.GRADE_CN[p.get('grade', 2)]}标准；\n"
                "2. 排气筒高度介于表列高度之间的，排放速率按附录B内插法计算，高于或低于表列高度的按外推法计算；"
                "排气筒低于15 m的，外推结果再严格50%（第7.4条）；未高出周围200 m半径范围建筑5 m以上的，"
                "按表列值严格50%（第7.1条）；\n"
                "3. 三项指标均为任何1 h平均值不得超过的限值（第8.2条），表中按逐次监测值判定；\n"
                f"4. {COMMON_NOTE}。")
    if kind == E.FUGITIVE:
        return ("注：1. 评价标准为《大气污染物综合排放标准》（GB 16297-1996）表2无组织排放监控浓度限值，"
                "监控点为周界外浓度最高点（一般设于无组织排放源下风向单位周界外10 m范围内，附录C）；\n"
                "2. 上风向参照点数据列出供对照，评价以下风向周界外浓度最高点为准；\n"
                "3. 臭气浓度、氨、硫化氢等恶臭污染物执行 GB 14554-93，在本软件\"GB 14554-93\"页判定；\n"
                f"4. {COMMON_NOTE}。")
    extra = []
    if p.get("indoor"):
        extra.append("厂界与噪声敏感建筑物距离小于1 m，在敏感建筑物室内测量，限值减10 dB(A)（第4.1.5条）")
    return ("注：1. 评价标准为《工业企业厂界环境噪声排放标准》（GB 12348-2008）表1"
            f"{BN.BOUNDARY_CN[p.get('bcls', '3')]}声环境功能区限值；\n"
            "2. 超标量=测量值-标准限值；各测点测量结果单独评价，同一测点每天按昼间、夜间评价（第6.1条）；\n"
            "3. 夜间频发噪声最大声级超过限值的幅度不得高于10 dB(A)，夜间偶发噪声不得高于15 dB(A)（第4.1.2、4.1.3条）"
            + ("；\n4. " + "；".join(extra) if extra else "") + "。")


def export(path, res, kind, p):
    if kind == E.BOILER:
        fu = p.get("fuel", "coal")
        p = dict(p, fuels=[f for f, _ in BN.FUELS if f in {E.boiler_fuel(r, fu) for r in res["summary"]}])
    t, n = title(kind, p), note(kind, p)
    head, keys = heads(kind)
    sheets = [("汇总表", t, head, keys, res["summary"], n)]
    if kind != E.BNOISE:
        dk = [k for k in DETAIL_KEYS if kind in E.GAS or k != "metric_cn"]
        dh = [DETAIL_HEAD[DETAIL_KEYS.index(k)] for k in dk]
        sheets.append(("逐样明细", t, dh, dk, res["detail"], n))
    if path.endswith(".xlsx"):
        write_excel(path, sheets)
    else:
        k2 = [k for k in keys if k != "note"]
        h2 = [head[keys.index(k)] for k in k2]
        write_word(path, [(t, h2, k2, res["summary"], n + collect_notes(res["summary"], n.count("\n") + 2))])
