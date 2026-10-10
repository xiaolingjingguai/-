# -*- coding: utf-8 -*-
"""
《土壤环境质量 建设用地土壤污染风险管控标准（试行）》（GB 36600—2018）限值库

来源：项目资料"土壤环境质量 建设用地土壤污染风险管控标准（试行） GB 36600-2018 代替 HJ 350-2007.pdf"
第 3~6 页表 1、表 2。数值由原文文字层逐行解析，带上标、科学计数或跨行名称的 12 行按原文页面图片人工补录。
- 2018-06-22 发布，2018-08-01 实施，代替 HJ 350-2007（标题页）。
- 第 5.3.1 条：规划用途为第一类用地适用第一类用地筛选值和管制值，第二类用地适用第二类；规划用途不明确的适用第一类。
- 第 5.3.2 条：含量等于或低于筛选值，风险一般情况下可以忽略；
  第 5.3.3 条：高于筛选值，应开展详细调查；第 5.3.5 条：高于管制值，通常存在不可接受风险。
- 表 1、表 2 注①：砷、钴、钒含量超过筛选值但等于或低于土壤环境背景值的，不纳入污染地块管理。
单位：mg/kg。screen=(第一类用地, 第二类用地) 筛选值；control=(第一类用地, 第二类用地) 管制值。
"""
STANDARD_INFO = dict(code="GB 36600—2018", name="土壤环境质量 建设用地土壤污染风险管控标准（试行）", status="现行")
UNIT = "mg/kg"

# 表 1 建设用地土壤污染风险筛选值和管制值（基本项目）
TABLE1 = [
    dict(no=1, name="砷", cas="7440-38-2", aliases=['As'], screen=(20, 60), control=(120, 140), bg_note=True),
    dict(no=2, name="镉", cas="7440-43-9", aliases=['Cd'], screen=(20, 65), control=(47, 172)),
    dict(no=3, name="铬（六价）", cas="18540-29-9", aliases=['六价铬', 'Cr6+', '铬(六价)', 'Cr(VI)'], screen=(3.0, 5.7), control=(30, 78)),
    dict(no=4, name="铜", cas="7440-50-8", aliases=['Cu'], screen=(2000, 18000), control=(8000, 36000)),
    dict(no=5, name="铅", cas="7439-92-1", aliases=['Pb'], screen=(400, 800), control=(800, 2500)),
    dict(no=6, name="汞", cas="7439-97-6", aliases=['Hg'], screen=(8, 38), control=(33, 82)),
    dict(no=7, name="镍", cas="7440-02-0", aliases=['Ni'], screen=(150, 900), control=(600, 2000)),
    dict(no=8, name="四氯化碳", cas="56-23-5", aliases=[], screen=(0.9, 2.8), control=(9, 36)),
    dict(no=9, name="氯仿", cas="67-66-3", aliases=['三氯甲烷'], screen=(0.3, 0.9), control=(5, 10)),
    dict(no=10, name="氯甲烷", cas="74-87-3", aliases=[], screen=(12, 37), control=(21, 120)),
    dict(no=11, name="1,1-二氯乙烷", cas="75-34-3", aliases=[], screen=(3, 9), control=(20, 100)),
    dict(no=12, name="1,2-二氯乙烷", cas="107-06-2", aliases=[], screen=(0.52, 5), control=(6, 21)),
    dict(no=13, name="1,1-二氯乙烯", cas="75-35-4", aliases=[], screen=(12, 66), control=(40, 200)),
    dict(no=14, name="顺-1,2-二氯乙烯", cas="156-59-2", aliases=[], screen=(66, 596), control=(200, 2000)),
    dict(no=15, name="反-1,2-二氯乙烯", cas="156-60-5", aliases=[], screen=(10, 54), control=(31, 163)),
    dict(no=16, name="二氯甲烷", cas="75-09-2", aliases=['亚甲基氯'], screen=(94, 616), control=(300, 2000)),
    dict(no=17, name="1,2-二氯丙烷", cas="78-87-5", aliases=[], screen=(1, 5), control=(5, 47)),
    dict(no=18, name="1,1,1,2-四氯乙烷", cas="630-20-6", aliases=[], screen=(2.6, 10), control=(26, 100)),
    dict(no=19, name="1,1,2,2-四氯乙烷", cas="79-34-5", aliases=[], screen=(1.6, 6.8), control=(14, 50)),
    dict(no=20, name="四氯乙烯", cas="127-18-4", aliases=[], screen=(11, 53), control=(34, 183)),
    dict(no=21, name="1,1,1-三氯乙烷", cas="71-55-6", aliases=[], screen=(701, 840), control=(840, 840)),
    dict(no=22, name="1,1,2-三氯乙烷", cas="79-00-5", aliases=[], screen=(0.6, 2.8), control=(5, 15)),
    dict(no=23, name="三氯乙烯", cas="79-01-6", aliases=[], screen=(0.7, 2.8), control=(7, 20)),
    dict(no=24, name="1,2,3-三氯丙烷", cas="96-18-4", aliases=[], screen=(0.05, 0.5), control=(0.5, 5)),
    dict(no=25, name="氯乙烯", cas="75-01-4", aliases=[], screen=(0.12, 0.43), control=(1.2, 4.3)),
    dict(no=26, name="苯", cas="71-43-2", aliases=[], screen=(1, 4), control=(10, 40)),
    dict(no=27, name="氯苯", cas="108-90-7", aliases=[], screen=(68, 270), control=(200, 1000)),
    dict(no=28, name="1,2-二氯苯", cas="95-50-1", aliases=[], screen=(560, 560), control=(560, 560)),
    dict(no=29, name="1,4-二氯苯", cas="106-46-7", aliases=[], screen=(5.6, 20), control=(56, 200)),
    dict(no=30, name="乙苯", cas="100-41-4", aliases=[], screen=(7.2, 28), control=(72, 280)),
    dict(no=31, name="苯乙烯", cas="100-42-5", aliases=[], screen=(1290, 1290), control=(1290, 1290)),
    dict(no=32, name="甲苯", cas="108-88-3", aliases=[], screen=(1200, 1200), control=(1200, 1200)),
    dict(no=33, name="间二甲苯+对二甲苯", cas="108-38-3,106-42-3", aliases=['间,对-二甲苯', '间/对-二甲苯', '间、对-二甲苯', '间对二甲苯'], screen=(163, 570), control=(500, 570)),
    dict(no=34, name="邻二甲苯", cas="95-47-6", aliases=[], screen=(222, 640), control=(640, 640)),
    dict(no=35, name="硝基苯", cas="98-95-3", aliases=[], screen=(34, 76), control=(190, 760)),
    dict(no=36, name="苯胺", cas="62-53-3", aliases=[], screen=(92, 260), control=(211, 663)),
    dict(no=37, name="2-氯酚", cas="95-57-8", aliases=[], screen=(250, 2256), control=(500, 4500)),
    dict(no=38, name="苯并[a]蒽", cas="56-55-3", aliases=['苯并(a)蒽'], screen=(5.5, 15), control=(55, 151)),
    dict(no=39, name="苯并[a]芘", cas="50-32-8", aliases=['苯并(a)芘'], screen=(0.55, 1.5), control=(5.5, 15)),
    dict(no=40, name="苯并[b]荧蒽", cas="205-99-2", aliases=['苯并(b)荧蒽'], screen=(5.5, 15), control=(55, 151)),
    dict(no=41, name="苯并[k]荧蒽", cas="207-08-9", aliases=['苯并(k)荧蒽'], screen=(55, 151), control=(550, 1500)),
    dict(no=42, name="䓛", cas="218-01-9", aliases=['屈'], screen=(490, 1293), control=(4900, 12900)),
    dict(no=43, name="二苯并[a, h]蒽", cas="53-70-3", aliases=['二苯并[a,h]蒽', '二苯并(a,h)蒽'], screen=(0.55, 1.5), control=(5.5, 15)),
    dict(no=44, name="茚并[1,2,3-cd]芘", cas="193-39-5", aliases=['茚并(1,2,3-cd)芘'], screen=(5.5, 15), control=(55, 151)),
    dict(no=45, name="萘", cas="91-20-3", aliases=[], screen=(25, 70), control=(255, 700)),
]

# 表 2 建设用地土壤污染风险筛选值和管制值（其他项目）
TABLE2 = [
    dict(no=1, name="锑", cas="7440-36-0", aliases=['Sb'], screen=(20, 180), control=(40, 360)),
    dict(no=2, name="铍", cas="7440-41-7", aliases=['Be'], screen=(15, 29), control=(98, 290)),
    dict(no=3, name="钴", cas="7440-48-4", aliases=['Co'], screen=(20, 70), control=(190, 350), bg_note=True),
    dict(no=4, name="甲基汞", cas="22967-92-6", aliases=[], screen=(5.0, 45), control=(10, 120)),
    dict(no=5, name="钒", cas="7440-62-2", aliases=['V'], screen=(165, 752), control=(330, 1500), bg_note=True),
    dict(no=6, name="氰化物", cas="57-12-5", aliases=[], screen=(22, 135), control=(44, 270)),
    dict(no=7, name="一溴二氯甲烷", cas="75-27-4", aliases=[], screen=(0.29, 1.2), control=(2.9, 12)),
    dict(no=8, name="溴仿", cas="75-25-2", aliases=[], screen=(32, 103), control=(320, 1030)),
    dict(no=9, name="二溴氯甲烷", cas="124-48-1", aliases=[], screen=(9.3, 33), control=(93, 330)),
    dict(no=10, name="1,2-二溴乙烷", cas="106-93-4", aliases=[], screen=(0.07, 0.24), control=(0.7, 2.4)),
    dict(no=11, name="六氯环戊二烯", cas="77-47-4", aliases=[], screen=(1.1, 5.2), control=(2.3, 10)),
    dict(no=12, name="2,4-二硝基甲苯", cas="121-14-2", aliases=[], screen=(1.8, 5.2), control=(18, 52)),
    dict(no=13, name="2,4-二氯酚", cas="120-83-2", aliases=[], screen=(117, 843), control=(234, 1690)),
    dict(no=14, name="2,4,6-三氯酚", cas="88-06-2", aliases=[], screen=(39, 137), control=(78, 560)),
    dict(no=15, name="2,4-二硝基酚", cas="51-28-5", aliases=[], screen=(78, 562), control=(156, 1130)),
    dict(no=16, name="五氯酚", cas="87-86-5", aliases=[], screen=(1.1, 2.7), control=(12, 27)),
    dict(no=17, name="邻苯二甲酸二(2-乙基己基)酯", cas="117-81-7", aliases=['DEHP'], screen=(42, 121), control=(420, 1210)),
    dict(no=18, name="邻苯二甲酸丁基苄酯", cas="85-68-7", aliases=[], screen=(312, 900), control=(3120, 9000)),
    dict(no=19, name="邻苯二甲酸二正辛酯", cas="117-84-0", aliases=[], screen=(390, 2812), control=(800, 5700)),
    dict(no=20, name="3,3'-二氯联苯胺", cas="91-94-1", aliases=[], screen=(1.3, 3.6), control=(13, 36)),
    dict(no=21, name="阿特拉津", cas="1912-24-9", aliases=[], screen=(2.6, 7.4), control=(26, 74)),
    dict(no=22, name="氯丹", cas="12789-03-6", aliases=[], screen=(2.0, 6.2), control=(20, 62)),
    dict(no=23, name="p,p'-滴滴滴", cas="72-54-8", aliases=[], screen=(2.5, 7.1), control=(25, 71)),
    dict(no=24, name="p,p'-滴滴伊", cas="72-55-9", aliases=[], screen=(2.0, 7.0), control=(20, 70)),
    dict(no=25, name="滴滴涕", cas="50-29-3", aliases=[], screen=(2.0, 6.7), control=(21, 67)),
    dict(no=26, name="敌敌畏", cas="62-73-7", aliases=[], screen=(1.8, 5.0), control=(18, 50)),
    dict(no=27, name="乐果", cas="60-51-5", aliases=[], screen=(86, 619), control=(170, 1240)),
    dict(no=28, name="硫丹", cas="115-29-7", aliases=[], screen=(234, 1687), control=(470, 3400)),
    dict(no=29, name="七氯", cas="76-44-8", aliases=[], screen=(0.13, 0.37), control=(1.3, 3.7)),
    dict(no=30, name="α-六六六", cas="319-84-6", aliases=[], screen=(0.09, 0.3), control=(0.9, 3)),
    dict(no=31, name="β-六六六", cas="319-85-7", aliases=[], screen=(0.32, 0.92), control=(3.2, 9.2)),
    dict(no=32, name="γ-六六六", cas="58-89-9", aliases=[], screen=(0.62, 1.9), control=(6.2, 19)),
    dict(no=33, name="六氯苯", cas="118-74-1", aliases=[], screen=(0.33, 1), control=(3.3, 10)),
    dict(no=34, name="灭蚁灵", cas="2385-85-5", aliases=[], screen=(0.03, 0.09), control=(0.3, 0.9)),
    dict(no=35, name="多氯联苯（总量）", cas="-", aliases=[], screen=(0.14, 0.38), control=(1.4, 3.8)),
    dict(no=36, name="3,3',4,4',5-五氯联苯（PCB 126）", cas="57465-28-8", aliases=[], screen=(4e-5, 1e-4), control=(4e-4, 1e-3)),
    dict(no=37, name="3,3',4,4',5,5'-六氯联苯（PCB 169）", cas="32774-16-6", aliases=[], screen=(1e-4, 4e-4), control=(1e-3, 4e-3)),
    dict(no=38, name="二噁英类（总毒性当量）", cas="-", aliases=[], screen=(1e-5, 4e-5), control=(1e-4, 4e-4)),
    dict(no=39, name="多溴联苯（总量）", cas="-", aliases=[], screen=(0.02, 0.06), control=(0.2, 0.6)),
    dict(no=40, name="石油烃（C10-C40）", cas="-", aliases=['石油烃(C10-C40)', '石油烃C10-C40', '石油烃'], screen=(826, 4500), control=(5000, 9000)),
]
