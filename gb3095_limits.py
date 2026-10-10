# -*- coding: utf-8 -*-
"""
《环境空气质量标准》（GB 3095—2026）浓度限值库

来源：项目资料"环境空气质量标准 GB3095 2026.pdf"（生态环境部环境标准研究所审校排版的正式电子版），
第 3~4 页表 1、表 2，已逐项对照原文录入。
- 发布 2026-02-13，实施 2026-03-01；代替 GB 3095—2012（含 2018 年修改单），自实施之日起后者废止（前言）。
- 第 4.4 条：自实施之日起至 2030-12-31 止，基本项目（表 1）实施"过渡阶段浓度限值"；自 2031-01-01 起
  实施表 1"浓度限值"。
- 第 4.5 条：其他项目（表 2）由国务院生态环境主管部门或者省级人民政府根据实际情况确定具体实施方式。
- 第 4.2 条：一类区适用一级浓度限值，二类区适用二级浓度限值。
- 第 4.3 条：SO2、NO2、CO、O3、NOx 为参比状态（298.15 K、1 013.25 hPa）浓度；PM2.5、PM10、BaP、TSP、Pb
  为监测时大气温度和压力下的浓度。

数据结构：limits[平均时间] = {"transition": (一级, 二级), "final": (一级, 二级)}
平均时间键：1h（1 小时平均）、8h（日最大 8 小时平均）、24h（日平均）、season（季平均）、year（年平均）
"""

PERIOD_CN = {"1h": "1小时平均", "8h": "日最大8小时平均", "24h": "日平均", "season": "季平均", "year": "年平均"}

STANDARD_INFO = dict(
    code="GB 3095—2026", name="环境空气质量标准",
    status="现行（2026-03-01 实施，代替 GB 3095—2012 及其修改单）",
)

UG, MG = "μg/m³", "mg/m³"

# 表 1 环境空气污染物基本项目浓度限值
TABLE1 = [
    dict(no=1, name="二氧化硫", aliases=["SO2", "SO₂", "二氧化硫(SO2)"], unit=UG, limits={
        "year": {"transition": (20, 60), "final": (20, 20)},
        "24h": {"transition": (50, 150), "final": (50, 50)},
        "1h": {"transition": (150, 500), "final": (150, 150)}}),
    dict(no=2, name="二氧化氮", aliases=["NO2", "NO₂"], unit=UG, limits={
        "year": {"transition": (40, 40), "final": (30, 30)},
        "24h": {"transition": (80, 80), "final": (50, 50)},
        "1h": {"transition": (200, 200), "final": (200, 200)}}),
    dict(no=3, name="一氧化碳", aliases=["CO"], unit=MG, limits={
        "24h": {"transition": (4, 4), "final": (4, 4)},
        "1h": {"transition": (10, 10), "final": (10, 10)}}),
    dict(no=4, name="臭氧", aliases=["O3", "O₃"], unit=UG, limits={
        "8h": {"transition": (100, 160), "final": (100, 160)},
        "1h": {"transition": (160, 200), "final": (160, 200)}}),
    dict(no=5, name="颗粒物（粒径小于等于10 μm）", aliases=["PM10", "PM₁₀", "可吸入颗粒物", "颗粒物PM10"], unit=UG,
         limits={
             "year": {"transition": (40, 60), "final": (20, 50)},
             "24h": {"transition": (50, 120), "final": (50, 100)}}),
    dict(no=6, name="颗粒物（粒径小于等于2.5 μm）", aliases=["PM2.5", "PM₂.₅", "细颗粒物", "颗粒物PM2.5"], unit=UG,
         limits={
             "year": {"transition": (15, 30), "final": (10, 25)},
             "24h": {"transition": (35, 60), "final": (25, 50)}}),
]

# 表 2 环境空气污染物其他项目浓度限值（氮氧化物年平均、日平均过渡阶段值见表 2 注 a、b）
TABLE2 = [
    dict(no=1, name="总悬浮颗粒物", aliases=["TSP"], unit=UG, limits={
        "year": {"transition": (80, 200), "final": (80, 200)},
        "24h": {"transition": (120, 300), "final": (120, 300)}}),
    dict(no=2, name="氮氧化物", aliases=["NOx", "NOX", "氮氧化物(以NO2计)"], unit=UG, limits={
        "year": {"transition": (50, 50), "final": (40, 40)},
        "24h": {"transition": (100, 100), "final": (70, 70)},
        "1h": {"transition": (250, 250), "final": (250, 250)}}),
    dict(no=3, name="铅", aliases=["Pb"], unit=UG, limits={
        "year": {"transition": (0.5, 0.5), "final": (0.5, 0.5)},
        "season": {"transition": (1.0, 1.0), "final": (1.0, 1.0)}}),
    dict(no=4, name="苯并[a]芘", aliases=["BaP", "苯并(a)芘", "苯并a芘"], unit=UG, limits={
        "year": {"transition": (0.001, 0.001), "final": (0.001, 0.001)},
        "24h": {"transition": (0.0025, 0.0025), "final": (0.0025, 0.0025)}}),
]

# 附录 A（资料性附录）为省级制定地方标准的参考值，不作为判定依据，故不录入。
