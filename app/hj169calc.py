"""HJ 169-2018 计算核心（纯函数，无界面依赖）。

每个函数返回 dict：v 为主结果，steps 为 [(项目, 公式/依据, 代入, 结果)]，warn 为提示列表。
公式编号均指《建设项目环境风险评价技术导则》（HJ 169-2018）。
"""
import math

G = 9.81    # 重力加速度，式(F.1) 注明取 9.81 m/s²
R = 8.314   # 气体常数 J/(mol·K)；导则未给数值，取通用值
M_AIR = 0.028965  # 干空气平均摩尔质量 kg/mol（通用值）
P_ATM = 101325.0  # 标准大气压 Pa


def fmt(x, d=4):
    if x is None or isinstance(x, float) and not math.isfinite(x):
        return "—"
    a = abs(x)
    if a != 0 and (a < 1e-3 or a >= 1e7):
        m, e = ("%.*e" % (d - 1, x)).split("e")
        return "%s×10^%d" % (m, int(e))
    s = "%.*g" % (d, x)
    if "e" in s:
        s = repr(float(s))
    return s


def _st(label, formula, subst, result):
    return (label, formula, subst, result)


# ---------------- 附录C ----------------
def q_value(items):
    """items: [{'name','cas','q','qc'}]，q、qc 单位 t。"""
    steps, warn, parts = [], [], []
    Q = 0.0
    for it in items:
        qc = it.get("qc")
        if not qc or qc <= 0:
            warn.append("%s：临界量缺失，未计入 Q" % (it.get("name") or "未命名物质"))
            continue
        r = it["q"] / qc
        Q += r
        parts.append("%s/%s" % (fmt(it["q"]), fmt(qc)))
        cas = "（CAS %s）" % it["cas"] if it.get("cas") else ""
        steps.append(_st(it["name"] + cas, "qᵢ/Qᵢ", "%s t ÷ %s t" % (fmt(it["q"]), fmt(qc)), fmt(r)))
    steps.append(_st("Q 合计", "式(C.1) Q = q₁/Q₁ + q₂/Q₂ + … + qₙ/Qₙ", " + ".join(parts) or "—", fmt(Q)))
    if Q < 1:
        cls = "Q<1"
    elif Q < 10:
        cls = "1≤Q<10"
    elif Q < 100:
        cls = "10≤Q<100"
    else:
        cls = "Q≥100"
    return {"v": Q, "cls": cls, "steps": steps, "warn": warn}


# 表C.1
C1 = [
    ("石化、化工、医药、轻工、化纤、有色冶炼等：涉及光气及光气化、电解（氯碱）、氯化、硝化、合成氨、裂解（裂化）、氟化、加氢、"
     "重氮化、氧化、过氧化、胺基化、磺化、聚合、烷基化、新型煤化工、电石生产、偶氮化工艺", 10, "10/套"),
    ("石化、化工等：无机酸制酸工艺、焦化工艺", 5, "5/套"),
    ("石化、化工等：其他高温（≥300 ℃）或高压（设计压力≥10.0 MPa）且涉及危险物质的工艺过程、危险物质贮存罐区", 5, "5/套（罐区）"),
    ("管道、港口/码头等：涉及危险物质管道运输项目、港口/码头等", 10, "10"),
    ("石油天然气：石油、天然气、页岩气开采（含净化），气库、油库（不含加气站），油气管线（不含城镇燃气管线）", 10, "10"),
    ("其他：涉及危险物质使用、贮存的项目", 5, "5"),
]


def m_value(units):
    """units: [(C1 序号, 套数)]"""
    steps, warn = [], []
    M = 0
    for idx, cnt in units:
        name, score, _ = C1[idx]
        M += score * cnt
        steps.append(_st(name[:30] + ("…" if len(name) > 30 else ""), "分值 × 套数", "%s × %s" % (score, fmt(cnt)), fmt(score * cnt)))
    if M > 20:
        cls = "M1"
    elif M > 10:
        cls = "M2"
    elif M > 5:
        cls = "M3"
    elif M == 5:
        cls = "M4"
    else:
        cls = "M4"
        warn.append("M=%s，小于表C.1 最低分值 5（“涉及危险物质使用、贮存的项目”）。请复核工艺单元是否漏计；此处暂按 M4 处理。" % fmt(M))
    steps.append(_st("M 合计", "C.1.2：M＞20→M1；10＜M≤20→M2；5＜M≤10→M3；M=5→M4",
                     " + ".join(fmt(C1[i][1] * c) for i, c in units) or "0", "%s，%s" % (fmt(M), cls)))
    return {"v": M, "cls": cls, "steps": steps, "warn": warn}


TABLE_C2 = {
    "Q≥100": {"M1": "P1", "M2": "P1", "M3": "P2", "M4": "P3"},
    "10≤Q<100": {"M1": "P1", "M2": "P2", "M3": "P3", "M4": "P4"},
    "1≤Q<10": {"M1": "P2", "M2": "P3", "M3": "P4", "M4": "P4"},
}


def p_level(qcls, mcls):
    return None if qcls == "Q<1" else TABLE_C2[qcls][mcls]


def e_air(mode="site", pop5km=0, pop500=0, special=False, per_km=0):
    steps, warn = [], []
    if mode == "pipe":
        n = per_km
        e = "E1" if n > 200 else "E2" if n > 100 else "E3"
        if n in (200, 100):
            warn.append("管段周边 200 m 每千米人口恰为 %s 人，表D.1 未明确等于临界值的归属，请复核。" % fmt(n))
        steps.append(_st("管线周边 200 m 每千米人口", "表D.1：＞200 人→E1；100～200 人→E2；＜100 人→E3", "%s 人/km" % fmt(n), e))
        return {"v": e, "steps": steps, "warn": warn}
    b5 = "E1" if pop5km > 50000 else "E2" if pop5km > 10000 else "E3"
    b05 = "E1" if pop500 > 1000 else "E2" if pop500 > 500 else "E3"
    if pop5km in (50000, 10000):
        warn.append("5 km 人口恰为 %s 人，表D.1 未明确等于临界值的归属，请复核。" % fmt(pop5km))
    if pop500 in (1000, 500):
        warn.append("500 m 人口恰为 %s 人，表D.1 未明确等于临界值的归属，请复核。" % fmt(pop500))
    cand = [b5, b05] + (["E1"] if special else [])
    e = min(cand)
    steps.append(_st("5 km 范围人口", "表D.1：＞5 万→E1；1 万～5 万→E2；＜1 万→E3", "%s 人" % fmt(pop5km), b5))
    steps.append(_st("500 m 范围人口", "表D.1：＞1000→E1；500～1000→E2；＜500→E3", "%s 人" % fmt(pop500), b05))
    if special:
        steps.append(_st("其他需要特殊保护区域", "表D.1：存在→E1", "存在", "E1"))
    steps.append(_st("大气环境敏感程度", "各判别条件取高值（“或”关系）", "、".join(cand), e))
    return {"v": e, "steps": steps, "warn": warn}


TABLE_D2 = {"S1": {"F1": "E1", "F2": "E1", "F3": "E2"}, "S2": {"F1": "E1", "F2": "E2", "F3": "E3"},
            "S3": {"F1": "E1", "F2": "E2", "F3": "E3"}}
TABLE_D5 = {"D1": {"G1": "E1", "G2": "E1", "G3": "E2"}, "D2": {"G1": "E1", "G2": "E2", "G3": "E3"},
            "D3": {"G1": "E2", "G2": "E3", "G3": "E3"}}


def d_class(Mb, K, continuous=True):
    """表D.7：Mb 单位 m，K 单位 cm/s"""
    if not continuous:
        return "D1"
    if Mb >= 1.0 and K <= 1e-6:
        return "D3"
    if 0.5 <= Mb < 1.0 and K <= 1e-6:
        return "D2"
    if Mb >= 1.0 and 1e-6 < K <= 1e-4:
        return "D2"
    return "D1"


TABLE_2 = {
    "E1": {"P1": "Ⅳ+", "P2": "Ⅳ", "P3": "Ⅲ", "P4": "Ⅲ"},
    "E2": {"P1": "Ⅳ", "P2": "Ⅲ", "P3": "Ⅲ", "P4": "Ⅱ"},
    "E3": {"P1": "Ⅲ", "P2": "Ⅲ", "P3": "Ⅱ", "P4": "Ⅰ"},
}
RANK = {"Ⅰ": 1, "Ⅱ": 2, "Ⅲ": 3, "Ⅳ": 4, "Ⅳ+": 5}
GRADE = {"Ⅳ+": "一级", "Ⅳ": "一级", "Ⅲ": "二级", "Ⅱ": "三级", "Ⅰ": "简单分析"}


def potential(p, e):
    return TABLE_2[e][p] if p else "Ⅰ"


def max_pot(pots):
    return max(pots, key=lambda x: RANK[x]) if pots else "Ⅰ"


# ---------------- 4.4、4.5 评价工作内容与评价范围 ----------------
def air_scope(grade, mode="site", reach=0.0):
    """4.5.1 大气环境风险评价范围。grade 为“一级/二级/三级/简单分析”，reach 为大气毒性终点浓度最大预测到达距离（m，无则 0）。
    返回 (范围文字, 依据, 提示)。简单分析导则未规定范围，返回“信息不足”字样。"""
    if grade == "简单分析":
        return ("导则未规定（简单分析）", "4.5.1 未对简单分析规定大气评价范围；按 4.5.4 结合环境敏感目标分布确定",
                "简单分析的大气评价范围导则未规定，信息不足，请按 4.5.4 结合敏感目标分布确定并在报告中说明。")
    pipe = mode == "pipe"
    d = (200 if pipe else 5000) if grade in ("一级", "二级") else (100 if pipe else 3000)
    base = ("管道中心线两侧各不低于 %d m" % d) if pipe else ("距建设项目边界不低于 %s km" % fmt(d / 1000))
    note = ""
    if reach and reach > d:
        base += "；大气毒性终点浓度预测到达距离 %s m 超出该范围，评价范围应扩大至不低于 %s m" % (fmt(reach), fmt(reach))
        note = "4.5.1：大气毒性终点浓度预测到达距离超出评价范围，已按预测到达距离调整评价范围。"
    return base, "4.5.1", note


SW_SCOPE = ("参照《环境影响评价技术导则 地表水环境》（HJ 2.3-2018）确定", "4.5.2")
GW_SCOPE = ("参照《环境影响评价技术导则 地下水环境》（HJ 610-2016）确定", "4.5.3")

# 4.4.4 各要素预测评价要求（按评价工作等级）
PRED = {
    "大气": {"一级": "选取最不利气象条件和事故发生地的最常见气象条件，选择适用的数值方法进行分析预测，给出危险物质释放可能造成的大气环境影响范围与程度；存在极高大气环境风险的项目应进一步开展关心点概率分析（4.4.4.1）",
             "二级": "选取最不利气象条件，选择适用的数值方法进行分析预测，给出危险物质释放可能造成的大气环境影响范围与程度（4.4.4.1）",
             "三级": "定性分析说明大气环境影响后果（4.4.4.1）"},
    "地表水": {"一级": "选择适用的数值方法预测地表水环境风险，给出可能造成的影响范围与程度（4.4.4.2）",
              "二级": "选择适用的数值方法预测地表水环境风险，给出可能造成的影响范围与程度（4.4.4.2）",
              "三级": "定性分析说明地表水环境影响后果（4.4.4.2）"},
    "地下水": {"一级": "优先选择适用的数值方法预测地下水环境风险，给出可能造成的影响范围与程度（4.4.4.3）",
              "二级": "风险预测分析与评价要求参照 HJ 610 执行（4.4.4.3）",
              "三级": "风险预测分析与评价要求参照 HJ 610 执行（4.4.4.3）"},
}
SIMPLE = "简单分析：在描述危险物质、环境影响途径、环境危害后果、风险防范措施等方面给出定性的说明（表1 注a、附录A）"


# ---------------- 附录F ----------------
CD_LIQ = {"gt": {"circle": 0.65, "triangle": 0.60, "rect": 0.55}, "le": {"circle": 0.50, "triangle": 0.45, "rect": 0.40}}
CD_GAS = {"circle": 1.00, "triangle": 0.95, "rect": 0.90}
SHAPE_CN = {"circle": "圆形（多边形）", "triangle": "三角形", "rect": "长方形"}


def liquid_leak(Cd, A, rho, P, P0, h):
    term = 2 * (P - P0) / rho + 2 * G * h
    warn = []
    if term <= 0:
        warn.append("根号内为非正值（P＜P₀ 且液位不足），不发生液体泄漏。")
    QL = Cd * A * rho * math.sqrt(term) if term > 0 else 0.0
    steps = [
        _st("根号内项", "2(P−P₀)/ρ + 2gh", "2×(%s−%s)/%s + 2×9.81×%s" % (fmt(P), fmt(P0), fmt(rho), fmt(h)), "%s m²/s²" % fmt(term)),
        _st("液体泄漏速率 Q_L", "式(F.1) Q_L = C_d·A·ρ·√[2(P−P₀)/ρ + 2gh]", "%s×%s×%s×√%s" % (fmt(Cd), fmt(A), fmt(rho), fmt(term)), "%s kg/s" % fmt(QL)),
    ]
    return {"v": QL, "steps": steps, "warn": warn}


def gas_leak(Cd, A, P, P0, M, gamma, T):
    k = gamma
    crit = (2 / (k + 1)) ** (k / (k - 1))
    ratio = P0 / P
    critical = ratio <= crit
    Y = 1.0
    steps = [
        _st("临界压力比", "(2/(γ+1))^(γ/(γ−1))", "(2/(%s+1))^(%s/(%s−1))" % (fmt(k), fmt(k), fmt(k)), fmt(crit)),
        _st("流态判别", "式(F.2) P₀/P ≤ 临界压力比 → 音速流动（临界流）" if critical else "式(F.3) P₀/P ＞ 临界压力比 → 亚音速流动（次临界流）",
            "P₀/P = %s/%s = %s" % (fmt(P0), fmt(P), fmt(ratio)), "临界流" if critical else "次临界流"),
    ]
    if not critical:
        a = ratio ** (1 / k)
        b = math.sqrt(1 - ratio ** ((k - 1) / k))
        c = math.sqrt((2 / (k - 1)) * ((k + 1) / 2) ** ((k + 1) / (k - 1)))
        Y = a * b * c
        steps.append(_st("流出系数 Y", "式(F.5) Y = (P₀/P)^(1/γ) × [1−(P₀/P)^((γ−1)/γ)]^½ × {[2/(γ−1)]×[(γ+1)/2]^((γ+1)/(γ−1))}^½",
                         "%s × %s × %s" % (fmt(a), fmt(b), fmt(c)), fmt(Y)))
    else:
        steps.append(_st("流出系数 Y", "临界流 Y = 1.0（式(F.4)注）", "—", "1.0"))
    root = math.sqrt(M * k / (R * T) * (2 / (k + 1)) ** ((k + 1) / (k - 1)))
    QG = Y * Cd * A * P * root
    steps.append(_st("根号项", "√{Mγ/(R·T_G) × [2/(γ+1)]^((γ+1)/(γ−1))}",
                     "√{%s×%s/(8.314×%s) × (2/%s)^(%s/%s)}" % (fmt(M), fmt(k), fmt(T), fmt(k + 1), fmt(k + 1), fmt(k - 1)), "%s s/m" % fmt(root)))
    steps.append(_st("气体泄漏速率 Q_G", "式(F.4) Q_G = Y·C_d·A·P·√{…}", "%s×%s×%s×%s×%s" % (fmt(Y), fmt(Cd), fmt(A), fmt(P), fmt(root)), "%s kg/s" % fmt(QG)))
    warn = []
    if P <= P0:
        warn.append("容器压力不高于环境压力，不发生气体泄漏。")
    return {"v": QG if P > P0 else 0.0, "critical": critical, "Y": Y, "steps": steps, "warn": warn}


def two_phase_leak(Cd, A, P, Cp, TLG, TC, H, rho1, rho2, pc_mode="ratio"):
    """pc_mode：'ratio' 按 P_C = 0.55P；'literal' 按导则原文 0.55 Pa"""
    warn = []
    Pc = 0.55 if pc_mode == "literal" else 0.55 * P
    Fv = Cp * (TLG - TC) / H
    steps = [
        _st("临界压力 P_C", "按导则原文“取 0.55 Pa”" if pc_mode == "literal" else "P_C = 0.55P（对导则“取 0.55 Pa”的量纲推断，见说明）",
            "—" if pc_mode == "literal" else "0.55×%s" % fmt(P), "%s Pa" % fmt(Pc)),
        _st("蒸发比例 F_V", "式(F.8) F_V = C_p(T_LG − T_C)/H", "%s×(%s−%s)/%s" % (fmt(Cp), fmt(TLG), fmt(TC), fmt(H)), fmt(Fv)),
    ]
    if Fv > 1:
        warn.append("F_V＞1，液体将全部蒸发成气体，应按气体泄漏计算（附录F.1.3）。")
    if Fv <= 0:
        warn.append("F_V≤0，不发生闪蒸，可按液体泄漏式(F.1)计算（附录F.1.3）。")
    FvC = min(max(Fv, 0.0), 1.0)
    rhom = 1 / (FvC / rho1 + (1 - FvC) / rho2)
    steps.append(_st("两相混合物平均密度 ρ_m", "式(F.7) ρ_m = 1/[F_V/ρ₁ + (1−F_V)/ρ₂]", "1/(%s/%s + %s/%s)" % (fmt(FvC), fmt(rho1), fmt(1 - FvC), fmt(rho2)), "%s kg/m³" % fmt(rhom)))
    QLG = Cd * A * math.sqrt(2 * rhom * (P - Pc))
    steps.append(_st("两相流泄漏速率 Q_LG", "式(F.6) Q_LG = C_d·A·√[2ρ_m(P − P_C)]", "%s×%s×√[2×%s×(%s−%s)]" % (fmt(Cd), fmt(A), fmt(rhom), fmt(P), fmt(Pc)), "%s kg/s" % fmt(QLG)))
    return {"v": QLG, "Fv": Fv, "rhom": rhom, "steps": steps, "warn": warn}


SURF = {  # 表F.2
    "cement": ("水泥", 1.1, 1.29e-7), "soil8": ("土地（含水 8%）", 0.9, 4.3e-7), "drysoil": ("干涸土地", 0.3, 2.3e-7),
    "wet": ("湿地", 0.6, 3.3e-7), "gravel": ("砂砾地", 2.5, 11.0e-7),
}
STAB = {  # 表F.3
    "AB": ("不稳定（A,B）", 0.2, 3.846e-3), "D": ("中性（D）", 0.25, 4.685e-3), "EF": ("稳定（E,F）", 0.3, 5.285e-3),
}


EVAP_PARTS = ("flash", "heat", "mass")


def evap_auto_parts(TT, Tb, T0):
    """按附录F.1.4 适用条件自动确定参与计算的蒸发项：
    闪蒸——储存温度高于沸点（过热液体）；热量蒸发——环境（地面）温度高于沸点；质量蒸发——液池存在即计。"""
    parts = []
    if TT > Tb:
        parts.append("flash")
    if T0 > Tb:
        parts.append("heat")
    parts.append("mass")
    return parts


def evaporation(QL, Cp, TT, Tb, Hv, H, T0, S, surface, t1, t2, t3, stab, p, M, u, r, parts=EVAP_PARTS):
    """parts：参与计算的蒸发项（flash/heat/mass）；未选项不计算、不列入计算过程，速率记为 0。"""
    steps, warn = [], []
    Fv, Q1, Q2, Q3 = 0.0, 0.0, 0.0, 0.0
    if "flash" in parts:
        Fv = Cp * (TT - Tb) / Hv
        steps.append(_st("闪蒸比例 F_v", "式(F.9) F_v = C_p(T_T − T_b)/H_v", "%s×(%s−%s)/%s" % (fmt(Cp), fmt(TT), fmt(Tb), fmt(Hv)), fmt(Fv)))
        if Fv <= 0:
            warn.append("储存温度不高于沸点，不发生闪蒸，Q₁=0。")
            Fv = 0.0
        if Fv > 1:
            warn.append("F_v＞1，泄漏液体全部闪蒸，按 F_v=1 计。")
            Fv = 1.0
        Q1 = QL * Fv
        steps.append(_st("闪蒸蒸发速率 Q₁", "式(F.10) Q₁ = Q_L × F_v", "%s×%s" % (fmt(QL), fmt(Fv)), "%s kg/s" % fmt(Q1)))
    if "heat" in parts:
        sname, lam, alp = SURF[surface]
        if T0 > Tb and Fv < 1:
            Q2 = lam * S * (T0 - Tb) / (H * math.sqrt(math.pi * alp * t2))
            steps.append(_st("热量蒸发速率 Q₂", "式(F.11) Q₂ = λS(T₀ − T_b)/(H√(παt))；地面：%s，λ=%s W/(m·K)，α=%s m²/s（表F.2）" % (sname, lam, fmt(alp, 3)),
                             "%s×%s×(%s−%s)/(%s×√(π×%s×%s))" % (lam, fmt(S), fmt(T0), fmt(Tb), fmt(H), fmt(alp, 3), fmt(t2)), "%s kg/s" % fmt(Q2)))
        else:
            steps.append(_st("热量蒸发速率 Q₂", "式(F.11)", "环境温度不高于沸点，不发生热量蒸发" if T0 <= Tb else "已全部闪蒸，无液池", "0 kg/s"))
    if "mass" in parts:
        stname, n, a = STAB[stab]
        e1, e2 = (2 - n) / (2 + n), (4 + n) / (2 + n)
        if Fv < 1:
            Q3 = a * p * M / (R * T0) * u ** e1 * r ** e2
            steps.append(_st("质量蒸发速率 Q₃", "式(F.12) Q₃ = α·p·M/(R·T₀)·u^((2−n)/(2+n))·r^((4+n)/(2+n))；稳定度 %s：n=%s，α=%s（表F.3）" % (stname, n, fmt(a)),
                             "%s×%s×%s/(8.314×%s)×%s^%s×%s^%s" % (fmt(a), fmt(p), fmt(M), fmt(T0), fmt(u), fmt(e1), fmt(r), fmt(e2)), "%s kg/s" % fmt(Q3)))
        else:
            steps.append(_st("质量蒸发速率 Q₃", "式(F.12)", "已全部闪蒸，无液池", "0 kg/s"))
    terms = [(q, t, k) for q, t, k, on in ((Q1, t1, "Q₁t₁", "flash" in parts), (Q2, t2, "Q₂t₂", "heat" in parts), (Q3, t3, "Q₃t₃", "mass" in parts)) if on]
    Wp = sum(q * t for q, t, _ in terms)
    steps.append(_st("液体蒸发总量 W_p", "式(F.13) W_p = " + " + ".join(k for _, _, k in terms) + ("（未选蒸发项不计）" if len(terms) < 3 else ""),
                     " + ".join("%s×%s" % (fmt(q), fmt(t)) for q, t, _ in terms), "%s kg" % fmt(Wp)))
    leaked = QL * max([t for _, t, _ in terms] or [0])
    if leaked > 0 and Wp > leaked:
        warn.append("蒸发总量 %s kg 大于泄漏总量估算值 %s kg，按式(F.13)机械相加已超出物料守恒，报告中应以泄漏量为上限并说明。" % (fmt(Wp), fmt(leaked)))
    return {"v": Wp, "Q1": Q1, "Q2": Q2, "Q3": Q3, "Fv": Fv, "steps": steps, "warn": warn, "parts": list(parts)}


# 表F.4
F4_COLS = [(0, 200), (200, 1000), (1000, 2000), (2000, 10000), (10000, 20000), (20000, math.inf)]
F4_COL_LABEL = ["＜200", "≥200，＜1000", "≥1000，＜2000", "≥2000，＜10000", "≥10000，＜20000", "≥20000"]
F4_ROWS = [(-math.inf, 100), (100, 500), (500, 1000), (1000, 5000), (5000, 10000), (10000, 20000), (20000, 50000), (50000, 100000)]
F4_ROW_LABEL = ["≤100", "＞100，≤500", "＞500，≤1000", "＞1000，≤5000", "＞5000，≤10000", "＞10000，≤20000", "＞20000，≤50000", "＞50000，≤100000"]
F4 = [
    [5, 10, None, None, None, None],
    [1.5, 3, 6, None, None, None],
    [1, 2, 4, 5, 8, None],
    [None, 0.5, 1, 1.5, 2, 3],
    [None, None, 0.5, 1, 1, 2],
    [None, None, None, 0.5, 1, 1],
    [None, None, None, None, 0.5, 0.5],
    [None, None, None, None, None, 0.5],
]


def release_ratio(Q, LC50):
    ri = next((i for i, (lo, hi) in enumerate(F4_ROWS) if lo < Q <= hi), -1)
    ci = next((i for i, (lo, hi) in enumerate(F4_COLS) if lo <= LC50 < hi), -1)
    warn, v = [], None
    if ri < 0:
        warn.append("在线量超出表F.4 范围（＞100000 t），导则未给取值。")
    elif ci < 0:
        warn.append("LC₅₀ 取值无效。")
    else:
        v = F4[ri][ci]
        if v is None:
            warn.append("表F.4 该格为空，导则未给释放比例，信息不足。")
    steps = [_st("释放比例", "表F.4（Q 为在线量 t，LC₅₀ 单位 mg/m³）",
                 "Q 行：%s；LC₅₀ 列：%s" % (F4_ROW_LABEL[ri] if ri >= 0 else "超出", F4_COL_LABEL[ci] if ci >= 0 else "—"),
                 "信息不足" if v is None else "%s %%" % fmt(v))]
    if v is not None:
        steps.append(_st("未燃烧释放量", "Q × 释放比例", "%s t × %s%%" % (fmt(Q), fmt(v)), "%s t" % fmt(Q * v / 100)))
    return {"v": v, "ri": ri, "ci": ci, "steps": steps, "warn": warn}


def so2(B, S_pct):
    v = 2 * B * S_pct / 100
    return {"v": v, "steps": [_st("二氧化硫排放速率", "式(F.14) G = 2BS（S 以质量分数代入）", "2×%s×%s%%" % (fmt(B), fmt(S_pct)), "%s kg/h" % fmt(v))], "warn": []}


def co(q_pct, C_pct, Q):
    warn = []
    if q_pct < 1.5 or q_pct > 6:
        warn.append("q 超出导则推荐范围 1.5%～6.0%。")
    if C_pct != 85:
        warn.append("C 未取导则规定值 85%，请说明依据。")
    v = 2330 * (q_pct / 100) * (C_pct / 100) * Q
    return {"v": v, "steps": [_st("一氧化碳产生量", "式(F.15) G = 2330qCQ（q、C 以小数代入，Q 单位 t/s）",
                                 "2330×%s×%s×%s" % (fmt(q_pct / 100), fmt(C_pct / 100), fmt(Q)), "%s kg/s" % fmt(v))], "warn": warn}


# ---------------- 附录G ----------------
def richardson(X, Ur, Td, rho_rel, rho_a, Q=None, Drel=None, Qt=None):
    steps, warn = [], []
    T = 2 * X / Ur
    cont = Td > T
    steps.append(_st("到达时间 T", "式(G.4) T = 2X/U_r", "2×%s/%s" % (fmt(X), fmt(Ur)), "%s s" % fmt(T)))
    steps.append(_st("排放类型", "G.2.1：T_d＞T 为连续排放；T_d≤T 为瞬时排放", "T_d = %s s，T = %s s" % (fmt(Td), fmt(T)), "连续排放" if cont else "瞬时排放"))
    dr = (rho_rel - rho_a) / rho_a
    steps.append(_st("相对过剩密度", "(ρ_rel − ρ_a)/ρ_a", "(%s−%s)/%s" % (fmt(rho_rel), fmt(rho_a), fmt(rho_a)), fmt(dr)))
    if cont:
        inner = G * (Q / rho_rel) / Drel * dr
        Ri = math.copysign(abs(inner) ** (1 / 3), inner) / Ur
        thr = 1 / 6
        heavy = Ri >= thr
        steps.append(_st("理查德森数 R_i", "式(G.2) R_i = [g(Q/ρ_rel)/D_rel × (ρ_rel−ρ_a)/ρ_a]^(1/3) / U_r",
                         "[9.81×(%s/%s)/%s×%s]^(1/3)/%s" % (fmt(Q), fmt(rho_rel), fmt(Drel), fmt(dr), fmt(Ur)), fmt(Ri)))
        steps.append(_st("判定", "连续排放：R_i ≥ 1/6 为重质气体，R_i ＜ 1/6 为轻质气体", "R_i = %s，1/6 = 0.1667" % fmt(Ri), "重质气体" if heavy else "轻质气体"))
    else:
        Ri = G * (Qt / rho_rel) ** (1 / 3) / (Ur * Ur) * dr
        thr = 0.04
        heavy = Ri > thr
        steps.append(_st("理查德森数 R_i", "式(G.3) R_i = g(Q_t/ρ_rel)^(1/3)/U_r² × (ρ_rel−ρ_a)/ρ_a",
                         "9.81×(%s/%s)^(1/3)/%s²×%s" % (fmt(Qt), fmt(rho_rel), fmt(Ur), fmt(dr)), fmt(Ri)))
        steps.append(_st("判定", "瞬时排放：R_i ＞ 0.04 为重质气体，R_i ≤ 0.04 为轻质气体", "R_i = %s" % fmt(Ri), "重质气体" if heavy else "轻质气体"))
    if dr <= 0:
        warn.append("排放物初始密度不大于环境空气密度，R_i 为非正值，按轻质（中性）气体处理。")
    elif abs(Ri - thr) / thr < 0.2:
        warn.append("R_i 处于临界值附近（±20%），宜按 G.2.1 分别采用重质、轻质气体模型模拟，取影响范围最大的结果。")
    model = "SLAB（G.1.1，平坦地形重质气体）" if heavy else "AFTOX（G.1.2，平坦地形中性/轻质气体及液池蒸发）"
    return {"v": Ri, "cont": cont, "heavy": heavy, "model": model, "T": T, "steps": steps, "warn": warn}


def ideal_rho(P, M, T):
    return P * M / (R * T)
