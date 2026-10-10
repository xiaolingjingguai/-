# -*- coding: utf-8 -*-
"""
海洋沉积物质量（GB 18668-2002）、海洋生物质量（GB 18421-2001）标准值库

来源：项目资料"海洋沉积物质量标准GB18668-2002.pdf""海洋生物质量标准(GB18421-2001).pdf"，
按原文第 1~2 页表 1 逐项录入（PDF 文字层字体编码错乱，数值已对照页面图像核对）。

GB 18668-2002：2002-03-10 批准，2002-10-01 实施。
  - 第 3.1 条：第一类适用于海洋渔业水域、海洋自然保护区、珍稀与濒危生物自然保护区、海水养殖区、海水浴场、
    人体直接接触沉积物的海上运动或娱乐区、与人类食用直接有关的工业用水区；第二类适用于一般工业用水区、
    滨海风景旅游区；第三类适用于海洋港口水域、特殊用途的海洋开发作业区。
  - 表 1 注 1：除大肠菌群、粪大肠菌群、病原体外，序号 6~18 均以干重计；×10⁻⁶ 即 mg/kg，×10⁻² 即 %。
  - 表 1 注 2、注 3：供人生食的贝类增养殖底质，大肠菌群 ≤14 个/g 湿重，粪大肠菌群 ≤3 个/g 湿重。
  - 大肠菌群、粪大肠菌群限值在原表中为第一类、第二类合并单元格，第三类空白（不作要求）。
GB 18421-2001：2001-08-28 批准，2002-03-01 实施。
  - 第 1 章：以海洋贝类（双壳类）为监测生物，适用于天然生长和人工养殖的海洋贝类。
  - 第 3 章分类同上（第一类：海洋渔业水域、海水养殖区、海洋自然保护区、与人类食用直接有关的工业用水区；
    第二类：一般工业用水区、滨海风景旅游区；第三类：港口水域和海洋开发作业区）。
  - 表 1 单位 mg/kg，以贝类去壳部分的鲜重计（注 1）；六六六、滴滴涕为四种异构体总和（注 2、注 3）。
  - 铜、锌第三类：牡蛎分别为 100、500 mg/kg。

数据结构：values = (第一类, 第二类, 第三类)，None 表示该类别不作要求。
"""

SED_INFO = dict(code="GB 18668-2002", name="海洋沉积物质量", status="现行（2002-10-01 实施）")
BIO_INFO = dict(code="GB 18421-2001", name="海洋生物质量", status="现行（2002-03-01 实施）")

CLASS_CN = {1: "第一类", 2: "第二类", 3: "第三类"}

# GB 18668-2002 表 1（序号 1、2、5 为感官/定性要求，不作数值判定）
SEDIMENT = [
    dict(no=3, name="大肠菌群", aliases=["总大肠菌群"], unit="个/g湿重", values=(200, 200, None),
         note="供人生食的贝类增养殖底质要求≤14个/g湿重（表1注2）"),
    dict(no=4, name="粪大肠菌群", aliases=[], unit="个/g湿重", values=(40, 40, None),
         note="供人生食的贝类增养殖底质要求≤3个/g湿重（表1注3）"),
    dict(no=6, name="汞", aliases=["Hg", "总汞"], unit="mg/kg", values=(0.20, 0.50, 1.00)),
    dict(no=7, name="镉", aliases=["Cd", "总镉"], unit="mg/kg", values=(0.50, 1.50, 5.00)),
    dict(no=8, name="铅", aliases=["Pb", "总铅"], unit="mg/kg", values=(60.0, 130.0, 250.0)),
    dict(no=9, name="锌", aliases=["Zn", "总锌"], unit="mg/kg", values=(150.0, 350.0, 600.0)),
    dict(no=10, name="铜", aliases=["Cu", "总铜"], unit="mg/kg", values=(35.0, 100.0, 200.0)),
    dict(no=11, name="铬", aliases=["Cr", "总铬"], unit="mg/kg", values=(80.0, 150.0, 270.0)),
    dict(no=12, name="砷", aliases=["As", "总砷"], unit="mg/kg", values=(20.0, 65.0, 93.0)),
    dict(no=13, name="有机碳", aliases=["总有机碳", "TOC", "有机碳(TOC)"], unit="%", values=(2.0, 3.0, 4.0)),
    dict(no=14, name="硫化物", aliases=["硫化物(以S计)"], unit="mg/kg", values=(300.0, 500.0, 600.0)),
    dict(no=15, name="石油类", aliases=["油类", "石油烃"], unit="mg/kg", values=(500.0, 1000.0, 1500.0)),
    dict(no=16, name="六六六", aliases=["HCH", "六六六(总量)"], unit="mg/kg", values=(0.50, 1.00, 1.50)),
    dict(no=17, name="滴滴涕", aliases=["DDT", "滴滴涕(总量)"], unit="mg/kg", values=(0.02, 0.05, 0.10)),
    dict(no=18, name="多氯联苯", aliases=["PCBs", "PCB", "多氯联苯(总量)"], unit="mg/kg", values=(0.02, 0.20, 0.60)),
]

# GB 18421-2001 表 1（感官要求为定性要求，不作数值判定）
BIOTA = [
    dict(name="粪大肠菌群", aliases=[], unit="个/kg", values=(3000, 5000, None)),
    dict(name="麻痹性贝毒", aliases=["PSP"], unit="mg/kg", values=(0.8, 0.8, 0.8)),
    dict(name="总汞", aliases=["汞", "Hg"], unit="mg/kg", values=(0.05, 0.10, 0.30)),
    dict(name="镉", aliases=["Cd", "总镉"], unit="mg/kg", values=(0.2, 2.0, 5.0)),
    dict(name="铅", aliases=["Pb", "总铅"], unit="mg/kg", values=(0.1, 2.0, 6.0)),
    dict(name="铬", aliases=["Cr", "总铬"], unit="mg/kg", values=(0.5, 2.0, 6.0)),
    dict(name="砷", aliases=["As", "总砷"], unit="mg/kg", values=(1.0, 5.0, 8.0)),
    dict(name="铜", aliases=["Cu", "总铜"], unit="mg/kg", values=(10, 25, 50), oyster=(10, 25, 100)),
    dict(name="锌", aliases=["Zn", "总锌"], unit="mg/kg", values=(20, 50, 100), oyster=(20, 50, 500)),
    dict(name="石油烃", aliases=["石油类", "油类"], unit="mg/kg", values=(15, 50, 80)),
    dict(name="六六六", aliases=["HCH"], unit="mg/kg", values=(0.02, 0.15, 0.50)),
    dict(name="滴滴涕", aliases=["DDT"], unit="mg/kg", values=(0.01, 0.10, 0.50)),
]
