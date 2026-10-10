# -*- coding: utf-8 -*-
"""生成土壤模拟监测报告（虚构数据，仅用于软件调试）：建设用地、农用地各一份"""
from docx import Document


def table(doc, rows, note):
    t = doc.add_table(rows=len(rows) + 1, cols=len(rows[0]))
    t.style = "Table Grid"
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            t.cell(i, j).text = str(v)
    last = t.rows[len(rows)].cells
    m = last[0].merge(last[-1])
    m.text = note


doc = Document()
doc.add_paragraph("【模拟数据，仅用于软件调试】土壤检测结果")
rows = [["检测项目", "检测结果", "检测结果", "检测结果"],
        ["检测项目", "T1", "T1", "T2"],
        ["检测项目", "0~0.5m", "0.5~1.5m", "0~0.2m"],
        ["检测项目", "TR2607-1-1", "TR2607-1-2", "TR2607-2-1"],
        ["pH（无量纲）", "6.82", "7.05", "5.91"],
        ["砷（mg/kg）", "12.4", "9.8", "68.0"],
        ["镉（mg/kg）", "0.21", "0.15", "0.36"],
        ["铬（六价）（mg/kg）", "0.5L", "0.5L", "0.5L"],
        ["铜（mg/kg）", "35", "28", "61"],
        ["铅（mg/kg）", "42.6", "38.1", "905"],
        ["汞（mg/kg）", "0.082", "0.064", "0.157"],
        ["镍（mg/kg）", "26", "21", "33"],
        ["苯（μg/kg）", "1.9L", "1.9L", "1.9L"],
        ["苯并[a]芘（mg/kg）", "0.1L", "0.1L", "0.32"],
        ["石油烃（C10-C40）（mg/kg）", "56", "6L", "88"],
        ["锌（mg/kg）", "86", "71", "152"]]
table(doc, rows, "备注：执行《土壤环境质量 建设用地土壤污染风险管控标准（试行）》（GB 36600-2018）第二类用地筛选值。")
doc.save("样例_土壤_模拟.docx")
print("ok")
