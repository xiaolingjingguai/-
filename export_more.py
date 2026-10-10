# -*- coding: utf-8 -*-
"""环境空气、声环境、土壤的导出表头、表题、表注（写出复用 export.write_excel / write_word）"""
from export import write_excel, write_word, collect_notes
from gb3095_limits import STANDARD_INFO as AIR_STD
from gb3096_limits import STANDARD_INFO as NOISE_STD, CLASS_CN as NOISE_CLS
from air_judge import LEVEL_CN, PHASE_CN
from soil_judge import LAND_CN
from marine_limits import SED_INFO, BIO_INFO, CLASS_CN as MARINE_CLS

# ---------------------------------------------------------------- 环境空气
AIR_HEAD = ["监测点位", "污染物", "平均时间", "单位", "样本数", "浓度范围", "标准限值", "最大浓度占标率（%）",
            "超标率（%）", "最大超标倍数", "达标情况", "备注"]
AIR_KEYS = ["station", "item", "period", "unit", "n", "range", "limit", "max_ratio", "exceed_rate", "max_exceed",
            "result", "note"]
AIR_DETAIL_HEAD = ["监测点位", "采样日期", "污染物（报告原名）", "对应标准项目", "平均时间", "监测值", "单位", "标准限值",
                   "占标率（%）", "超标倍数", "判定结果", "备注"]
AIR_DETAIL_KEYS = ["station", "date", "item", "std_name", "period_cn", "value_disp", "unit_disp", "limit_text",
                   "ratio", "exceed_times", "result", "note"]


def air_title(level, phase):
    return f"环境空气质量现状监测结果及评价（执行 {AIR_STD['code']} {LEVEL_CN[level]}{PHASE_CN[phase]}）"


def air_note(level, phase):
    stage = ("过渡阶段浓度限值（第4.4条：2026年3月1日至2030年12月31日执行）" if phase == "transition"
             else "浓度限值（第4.4条：2031年1月1日起执行）")
    return ("注：1. 评价标准为《环境空气质量标准》（GB 3095—2026）" f"{LEVEL_CN[level]}{stage}；\n"
            "2. 占标率 P=C/C0×100%，超标倍数=(C-C0)/C0，C0 为对应平均时间的浓度限值；\n"
            "3. 未检出项目以\"＜检出限\"表示，检出限不高于标准限值的判定为达标；\n"
            "4. 超标率=超标样本数/有效判定样本数×100%；\n"
            "5. GB 3095—2026 未规定的项目（如氨、硫化氢）采用监测报告所列限值，其依据见备注，须复核。")


# ---------------------------------------------------------------- 声环境
NOISE_HEAD = ["监测点位", "监测日期", "时段", "测量时间", "等效声级 Leq（dB(A)）", "标准限值（dB(A)）", "超标量（dB(A)）",
              "评价依据", "达标情况", "备注"]
NOISE_KEYS = ["station", "date", "period", "time", "value", "limit", "over", "basis", "result", "note"]


def noise_title(cls):
    return f"声环境质量现状监测结果及评价（执行 {NOISE_STD['code']} {NOISE_CLS[cls]}标准）"


def noise_note(cls):
    return ("注：1. 评价标准为《声环境质量标准》（GB 3096-2008）" f"{NOISE_CLS[cls]}声环境功能区限值（表1）；\n"
            "2. 超标量=测量值-标准限值；\n"
            "3. 昼间指 6:00 至 22:00，夜间指 22:00 至次日 6:00（GB 3096-2008 第3.4条）；\n"
            "4. 厂界噪声执行《工业企业厂界环境噪声排放标准》（GB 12348-2008）的，按该标准表1所选功能区类别限值判定。")


# ---------------------------------------------------------------- 土壤
SOIL_HEAD = ["监测点位", "监测项目", "单位", "样品数", "测定值", "风险筛选值", "风险管制值", "最大标准指数",
             "超筛选值率（%）", "最大超筛选值倍数", "评价结果", "备注"]
SOIL_KEYS = ["station", "item", "unit", "n", "range", "screen", "control", "max_index", "exceed_rate", "max_exceed",
             "result", "note"]
SOIL_DETAIL_HEAD = ["监测点位", "采样日期", "监测项目（报告原名）", "对应标准项目", "所在表", "测定值", "单位", "风险筛选值",
                    "风险管制值", "标准指数", "超筛选值倍数", "评价结果", "备注"]
SOIL_DETAIL_KEYS = ["station", "date", "item", "std_name", "table", "value_disp", "unit_disp", "screen", "control",
                    "index", "exceed_times", "result", "note"]


def soil_title(land):
    std = "GB 36600—2018" if land.startswith("build") else "GB 15618—2018"
    return f"土壤环境质量现状监测结果及评价（{LAND_CN[land]}，执行 {std}）"


def soil_note(land):
    if land.startswith("build"):
        return ("注：1. 评价标准为《土壤环境质量 建设用地土壤污染风险管控标准（试行）》（GB 36600—2018）"
                f"{'第一类' if land == 'build1' else '第二类'}用地风险筛选值和管制值（第5.3.1条）；\n"
                "2. 标准指数 P=C/筛选值；超筛选值倍数=(C-筛选值)/筛选值；\n"
                "3. 含量等于或低于筛选值的，风险一般情况下可以忽略（第5.3.2条）；高于筛选值的应开展详细调查（第5.3.3条）；"
                "高于管制值的通常存在不可接受风险（第5.3.5条）；\n"
                "4. 未检出项目以\"检出限+L\"表示。")
    return ("注：1. 评价标准为《土壤环境质量 农用地土壤污染风险管控标准（试行）》（GB 15618—2018），"
            f"用地类型：{LAND_CN[land]}，按各样品 pH 所在分档取筛选值；\n"
            "2. 标准指数 P=C/筛选值；超筛选值倍数=(C-筛选值)/筛选值；\n"
            "3. 等于或低于筛选值的，风险低，一般情况下可以忽略（第6.1条）；镉、汞、砷、铅、铬高于筛选值、不高于管制值的，"
            "原则上应采取安全利用措施（第6.2条）；高于管制值的，原则上应采取严格管控措施（第6.3条）；\n"
            "4. 未检出项目以\"检出限+L\"表示。")


# ---------------------------------------------------------------- 海洋沉积物、海洋生物质量
MARINE_HEAD = ["监测站位", "监测项目", "单位", "样品数", "测定值", "标准值", "最大标准指数", "超标率（%）",
               "最大超标倍数", "单因子类别", "评价结果", "备注"]
MARINE_KEYS = ["station", "item", "unit", "n", "range", "limit", "max_index", "exceed_rate", "max_exceed", "cls",
               "result", "note"]
MARINE_DETAIL_HEAD = ["监测站位", "采样日期", "监测项目（报告原名）", "对应标准项目", "测定值", "单位", "标准值",
                      "标准指数", "超标倍数", "单因子类别", "评价结果", "备注"]
MARINE_DETAIL_KEYS = ["station", "date", "item", "std_name", "value_disp", "unit_disp", "limit_text", "index",
                      "exceed_times", "cls", "result", "note"]


def marine_title(kind, cls):
    info = SED_INFO if kind == "sediment" else BIO_INFO
    what = "海洋沉积物质量" if kind == "sediment" else "海洋生物质量"
    return f"{what}现状监测结果及评价（执行 {info['code']} {MARINE_CLS[cls]}标准）"


def marine_note(kind, cls):
    if kind == "sediment":
        return ("注：1. 评价标准为《海洋沉积物质量》（GB 18668-2002）" f"{MARINE_CLS[cls]}标准值（表1）；\n"
                "2. 标准指数 P=C/C0，超标倍数=(C-C0)/C0；单因子类别为测定值所符合的最优类别；\n"
                "3. 除大肠菌群、粪大肠菌群外，各项目均以干重计（表1注1），有机碳单位为 %；\n"
                "4. 未检出项目以\"检出限+L\"表示。")
    return ("注：1. 评价标准为《海洋生物质量》（GB 18421-2001）" f"{MARINE_CLS[cls]}标准值（表1），"
            "标准以海洋贝类（双壳类）为监测生物；\n"
            "2. 以贝类去壳部分的鲜重计（表1注1）；六六六、滴滴涕为四种异构体总和；\n"
            "3. 标准指数 P=C/C0，超标倍数=(C-C0)/C0；单因子类别为测定值所符合的最优类别；\n"
            "4. 鱼类、甲壳类等非双壳类生物不适用本标准，其评价依据须另行确定；\n"
            "5. 未检出项目以\"检出限+L\"表示。")


def _word_keys(head, keys):
    k2 = [k for k in keys if k != "note"]
    return [head[keys.index(k)] for k in k2], k2


def export(path, res, kind, p):
    if kind == "air":
        lv, ph = p.get("level", 2), p.get("phase", "transition")
        title, note = air_title(lv, ph), air_note(lv, ph)
        sheets = [("汇总表", title, AIR_HEAD, AIR_KEYS, res["summary"], note),
                  ("逐样明细", title, AIR_DETAIL_HEAD, AIR_DETAIL_KEYS, res["detail"], note)]
        head, keys = AIR_HEAD, AIR_KEYS
    elif kind == "noise":
        cls = p.get("noise_cls", "2")
        title, note = noise_title(cls), noise_note(cls)
        sheets = [("汇总表", title, NOISE_HEAD, NOISE_KEYS, res["summary"], note)]
        head, keys = NOISE_HEAD, NOISE_KEYS
    elif kind in ("sediment", "biota"):
        cls = p.get("marine_cls", 1)
        title, note = marine_title(kind, cls), marine_note(kind, cls)
        sheets = [("汇总表", title, MARINE_HEAD, MARINE_KEYS, res["summary"], note),
                  ("逐样明细", title, MARINE_DETAIL_HEAD, MARINE_DETAIL_KEYS, res["detail"], note)]
        head, keys = MARINE_HEAD, MARINE_KEYS
    else:
        land = p.get("land", "build2")
        title, note = soil_title(land), soil_note(land)
        sheets = [("汇总表", title, SOIL_HEAD, SOIL_KEYS, res["summary"], note),
                  ("逐样明细", title, SOIL_DETAIL_HEAD, SOIL_DETAIL_KEYS, res["detail"], note)]
        head, keys = SOIL_HEAD, SOIL_KEYS
    if path.endswith(".xlsx"):
        write_excel(path, sheets)
    else:
        h, k = _word_keys(head, keys)
        n0 = note.count("\n") + 2
        write_word(path, [(title, h, k, res["summary"], note + collect_notes(res["summary"], n0))])
