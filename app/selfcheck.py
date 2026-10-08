"""计算核心自校验：参照值由独立手算脚本按导则原式计算。"""
import math
import sys

import hj169calc as H

A10 = math.pi * 0.010 ** 2 / 4
A5 = math.pi * 0.005 ** 2 / 4
A50 = math.pi * 0.05 ** 2 / 4
R100, R200 = math.sqrt(100 / math.pi), math.sqrt(200 / math.pi)


def ev_nh3():
    return H.evaporation(QL=1.5589690071088, Cp=4651, TT=293.15, Tb=239.85, Hv=1369895, H=1369895, T0=298.15, S=100,
                         surface="cement", t1=600, t2=600, t3=1800, stab="EF", p=101325, M=0.0170305, u=1.5, r=R100)


def ev_meoh():
    return H.evaporation(QL=10.04, Cp=2531, TT=293.15, Tb=337.65, Hv=1098874, H=1098874, T0=298.15, S=200,
                         surface="cement", t1=600, t2=1200, t3=1800, stab="EF", p=12880, M=0.0320419, u=1.5, r=R200)


def _meoh_mass():
    return H.evaporation(QL=10.04, Cp=2531, TT=293.15, Tb=337.65, Hv=1098874, H=1098874, T0=298.15, S=200,
                         surface="cement", t1=600, t2=1200, t3=1800, stab="EF", p=12880, M=0.0320419, u=1.5, r=R200, parts=["mass"])


RHO_A = H.ideal_rho(101325, 0.028965, 298.15)
CASES = [
    ("液氨 Q_L (F.1)", 1.5589690071088, lambda: H.liquid_leak(0.65, A10, 609.4, 854500, 101325, 2)["v"]),
    ("液氨 F_v (F.9)", 0.1809615335481916, lambda: ev_nh3()["Fv"]),
    ("液氨 Q1 (F.10)", 0.28211342228051006, lambda: ev_nh3()["Q1"]),
    ("液氨 Q2 (F.11)", 0.3002123421240961, lambda: ev_nh3()["Q2"]),
    ("液氨 Q3 (F.12)", 0.12610628741537228, lambda: ev_nh3()["Q3"]),
    ("液氨 W_p (F.13)", 576.3867759904338, lambda: ev_nh3()["v"]),
    ("液氨 Q_LG (F.6-F.8)", 0.12008299205017271, lambda: H.two_phase_leak(0.8, A10, 854500, 4651, 293.15, 239.85, 1369895, 0.865, 609.4)["v"]),
    ("液氯 Q_G 临界流 (F.4)", 0.049799136204622216, lambda: H.gas_leak(1, A5, 700000, 101325, 0.070906, 1.325, 293.15)["v"]),
    ("液氯 Y 次临界流 (F.5)", 0.9575789904816651, lambda: H.gas_leak(1, A5, 150000, 101325, 0.070906, 1.325, 293.15)["Y"]),
    ("液氯 Q_G 次临界流 (F.4)", 0.010218558551503087, lambda: H.gas_leak(1, A5, 150000, 101325, 0.070906, 1.325, 293.15)["v"]),
    ("甲醇 Q_L (F.1)", 10.04192528712694, lambda: H.liquid_leak(0.65, A50, 794.4, 101325, 101325, 5)["v"]),
    ("甲醇 Q3 (F.12)", 0.057653338060338205, lambda: ev_meoh()["Q3"]),
    ("空气密度", 1.1839825766228769, lambda: RHO_A),
    ("甲醇 R_i 连续 (G.2)", 0.09479086362838535, lambda: H.richardson(500, 1.5, 1800, H.ideal_rho(101325, 0.0320419, 298.15), RHO_A, Q=ev_meoh()["Q3"], Drel=2 * R200)["v"]),
    ("液氯 R_i 瞬时 (G.3)", 58.30085785024061, lambda: H.richardson(2000, 1.5, 60, H.ideal_rho(101325, 0.070906, 239.15), RHO_A, Qt=1000)["v"]),
    ("Q 值 (C.1)", 5.333333333333333, lambda: H.q_value([{"name": "氨", "q": 20, "qc": 5}, {"name": "盐酸", "q": 10, "qc": 7.5}])["v"]),
    ("SO2 (F.14)", 10.0, lambda: H.so2(1000, 0.5)["v"]),
    ("CO (F.15)", 0.59415, lambda: H.co(3, 85, 0.01)["v"]),
]


def run():
    lines, bad = [], 0
    for name, ref, fn in CASES:
        v = fn()
        ok = abs(v - ref) / abs(ref) < 1e-9
        bad += not ok
        lines.append("%-24s 手算 %-22r 程序 %-22r %s" % (name, ref, v, "一致" if ok else "不一致"))
    # 判级逻辑
    checks = [
        (H.m_value([(2, 1)])["cls"], "M4"), (H.p_level("1≤Q<10", "M4"), "P4"), (H.potential("P4", "E2"), "Ⅱ"),
        (H.GRADE["Ⅱ"], "三级"), (H.e_air("site", 30000, 300)["v"], "E2"), (H.d_class(1.2, 5e-5), "D2"),
        (H.TABLE_D5["D2"]["G3"], "E3"), (H.release_ratio(300, 500)["v"], 3), (H.release_ratio(50, 5000)["v"], None),
        (H.max_pot(["Ⅱ", "Ⅳ+", "Ⅲ"]), "Ⅳ+"), (H.potential(None, "E1"), "Ⅰ"),
        (H.evap_auto_parts(293.15, 337.65, 298.15), ["mass"]), (H.evap_auto_parts(293.15, 239.85, 298.15), ["flash", "heat", "mass"]),
        (abs(_meoh_mass()["v"] - ev_meoh()["Q3"] * 1800) < 1e-9 and len(_meoh_mass()["steps"]) == 2, True),
        (H.air_scope("二级")[0], "距建设项目边界不低于 5 km"), (H.air_scope("三级")[0], "距建设项目边界不低于 3 km"),
        (H.air_scope("一级", "pipe")[0], "管道中心线两侧各不低于 200 m"), ("6200 m" in H.air_scope("一级", "site", 6200)[0], True), (H.gas_leak(1, A5, 700000, 101325, 0.070906, 1.325, 293.15)["critical"], True),
    ]
    for got, exp in checks:
        ok = got == exp
        bad += not ok
        lines.append("判级 %-10r 期望 %-10r %s" % (got, exp, "一致" if ok else "不一致"))
    lines.append("合计 %d 项，不一致 %d 项" % (len(CASES) + len(checks), bad))
    return bad, lines


if __name__ == "__main__":
    bad, lines = run()
    print("\n".join(lines))
    sys.exit(1 if bad else 0)
