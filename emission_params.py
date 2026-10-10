# -*- coding: utf-8 -*-
"""排放标准各页（GB 8978、GB 16297 有组织/无组织、GB 13271、GB 12348）左侧"评价参数"控件"""
from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QLabel, QWidget, QFormLayout

import emission_judge as E
import gb8978_limits as W
import gb16297_limits as A
import gb13271_gb12348_limits as BN
import gb14554_limits as O


def _combo(items, cur=0):
    c = QComboBox()
    for v, t in items:
        c.addItem(t, v)
    c.setCurrentIndex(cur)
    return c


def build(page, form):
    """在 form 中加入参数控件，控件挂在 page 上并登记到 page._pwidgets；返回标准说明文字"""
    k = page.kind
    pw = page._pwidgets
    if k == E.WASTEWATER:
        page.ww_grade = _combo([(1, "一级标准"), (2, "二级标准"), (3, "三级标准")])
        page.ww_grade.setToolTip("第4.1条：排入GB 3838 Ⅲ类水域（保护区、游泳区除外）和GB 3097二类海域→一级；\n"
                                 "排入Ⅳ、Ⅴ类水域和三类海域→二级；排入设置二级污水处理厂的城镇排水系统→三级")
        form.addRow("标准级别：", page.ww_grade)
        page.ww_ind = _combo(W.INDUSTRIES)
        page.ww_ind.setMaxVisibleItems(25)
        form.addRow("行业：", page.ww_ind)
        page.ww_lowf = QCheckBox("低氟地区（水体含氟量＜0.5 mg/L）")
        form.addRow(page.ww_lowf)
        pw += [page.ww_grade, page.ww_ind, page.ww_lowf]
        return ("执行标准：GB 8978-1996《污水综合排放标准》\n"
                "第一类污染物：表1\n（车间或车间处理设施排放口采样）\n"
                "第二类污染物：表4\n（1998年1月1日后建设的单位）\n"
                "1997年底前建设单位的表2、表3未录入\n"
                "有行业排放标准或福建地方标准\n（DB35）的应优先执行，须核实")
    if k == E.STACK:
        page.st_grade = _combo([(2, "二级（二类区）"), (3, "三级（三类区）")])
        form.addRow("速率级别：", page.st_grade)
        page.st_h = QLineEdit()
        page.st_h.setPlaceholderText("报告未注明时填写，m")
        form.addRow("排气筒高度：", page.st_h)
        page.st_bldg = QCheckBox("排气筒高出周围200 m半径建筑5 m以上")
        page.st_bldg.setChecked(True)
        page.st_bldg.setToolTip("不满足时排放速率按表列值严格50%执行（GB 16297-1996 第7.1条）")
        form.addRow(page.st_bldg)
        page.st_subs = {}
        for it in A.TABLE2:
            if len(it["subs"]) > 1:
                c = _combo([(i, s["scope"]) for i, s in enumerate(it["subs"])], len(it["subs"]) - 1)
                c.setToolTip(f"{it['name']}最高允许排放浓度按生产类型分档")
                c.setMinimumContentsLength(8)
                page.st_subs[it["name"]] = c
                form.addRow(f"{it['name']}：", c)
                pw.append(c)
        page.st_h.editingFinished.connect(page.on_params_changed)
        pw += [page.st_grade, page.st_bldg]
        return ("执行标准：GB 16297-1996\n《大气污染物综合排放标准》表2\n（新污染源，有组织排放）\n"
                "浓度按实测浓度判定；排放速率按\n排气筒高度内插或外推（附录B）\n"
                "锅炉废气请在“GB 13271-2014”页判定\n恶臭项目请在“GB 14554-93”页判定\n"
                "有行业排放标准或福建地方标准\n（DB35）的应优先执行，须核实")
    if k == E.BOILER:
        page.bo_fuel = _combo(BN.FUELS)
        page.bo_fuel.setToolTip("点位名称含\"燃气/天然气\"\"燃油/柴油\"\"燃煤/生物质\"的按名称识别")
        form.addRow("锅炉燃料：", page.bo_fuel)
        page.bo_table = _combo(BN.BOILER_TABLES)
        form.addRow("限值表：", page.bo_table)
        pw += [page.bo_fuel, page.bo_table]
        return ("执行标准：GB 13271-2014\n《锅炉大气污染物排放标准》\n"
                "实测浓度按第5.2条式(1)折算为\n基准氧含量（燃煤9%，燃油、燃气3.5%）\n"
                "报告已给出折算浓度的以折算浓度判定\n未规定排放速率限值\n"
                "福建地方标准（DB35）有规定的\n应优先执行，须核实")
    if k == E.ODOR_STACK:
        page.od_h = QLineEdit()
        page.od_h.setPlaceholderText("报告未注明时填写，m")
        form.addRow("排气筒高度：", page.od_h)
        page.od_h.editingFinished.connect(page.on_params_changed)
        return ("执行标准：GB 14554-93\n《恶臭污染物排放标准》表2\n（排气筒排放，第4.2.2条）\n"
                "八种恶臭污染物按排放量（kg/h）判定，\n臭气浓度按无量纲标准值判定\n"
                "排气筒高度介于表列高度之间的，\n按第6.1.2条四舍五入取表列高度\n"
                "排气筒不得低于 15 m（第6.1.1条）\n"
                "有行业排放标准或福建地方标准\n（DB35）的应优先执行，须核实")
    if k == E.ODOR_FENCE:
        page.od_grade = _combo(O.FENCE_GRADES, 1)
        page.od_grade.setToolTip("第4.1条：排入GB 3095一类区执行一级，二类区执行二级，三类区执行三级；\n"
                                 "第4.2.1条：1994年6月1日起立项的新、扩、改建设项目执行\"新扩改建\"值")
        page.od_grade.setMinimumContentsLength(10)
        form.addRow("标准分级：", page.od_grade)
        pw.append(page.od_grade)
        return ("执行标准：GB 14554-93\n《恶臭污染物排放标准》表1\n恶臭污染物厂界标准值\n（无组织排放源）\n"
                "厂界监测点一次最大监测值\n（含臭气浓度）须≤厂界标准值（第5.1条）\n"
                "有行业排放标准或福建地方标准\n（DB35）的应优先执行，须核实")
    if k == E.FUGITIVE:
        it = next(x for x in A.TABLE2 if x["name"] == "颗粒物")
        page.fu_pm = _combo([(i, s["scope"]) for i, s in enumerate(it["subs"])], 2)
        page.fu_pm.setMinimumContentsLength(8)
        form.addRow("颗粒物类别：", page.fu_pm)
        pw.append(page.fu_pm)
        return ("执行标准：GB 16297-1996 表2\n无组织排放监控浓度限值\n（监控点：周界外浓度最高点）\n"
                "臭气浓度、氨、硫化氢等恶臭项目\n请在“GB 14554-93”页判定")
    page.bn_cls = _combo([(c, f"{c}类") for c in BN.BOUNDARY], 3)
    form.addRow("厂界外功能区：", page.bn_cls)
    page.bn_freq = QCheckBox("夜间最大声级按频发噪声（+10 dB(A)）")
    page.bn_freq.setToolTip("不勾选按偶发噪声（+15 dB(A)）；监测项目名称注明\"频发/偶发\"的以名称为准")
    form.addRow(page.bn_freq)
    page.bn_indoor = QCheckBox("厂界距敏感建筑物＜1 m，室内测量（限值减10）")
    form.addRow(page.bn_indoor)
    pw += [page.bn_cls, page.bn_freq, page.bn_indoor]
    return "执行标准：GB 12348-2008\n《工业企业厂界环境噪声排放标准》\n表1，各测点单独评价（第6.1条）"


def _h(page):
    try:
        return float(page.st_h.text().strip()) or None
    except ValueError:
        return None


def params(page):
    k = page.kind
    if k == E.WASTEWATER:
        return dict(grade=page.ww_grade.currentData(), industry=page.ww_ind.currentData(), lowf=page.ww_lowf.isChecked())
    if k == E.STACK:
        return dict(grade=page.st_grade.currentData(), height=_h(page), bldg_ok=page.st_bldg.isChecked(),
                    subs={n: c.currentData() for n, c in page.st_subs.items()})
    if k == E.BOILER:
        return dict(fuel=page.bo_fuel.currentData(), btable=page.bo_table.currentData())
    if k == E.ODOR_STACK:
        try:
            h = float(page.od_h.text().strip()) or None
        except ValueError:
            h = None
        return dict(height=h)
    if k == E.ODOR_FENCE:
        return dict(grade=page.od_grade.currentData())
    if k == E.FUGITIVE:
        return dict(subs={"颗粒物": page.fu_pm.currentData()})
    return dict(bcls=page.bn_cls.currentData(), frequent=page.bn_freq.isChecked(), indoor=page.bn_indoor.isChecked())


def desc(page):
    k = page.kind
    if k == E.WASTEWATER:
        return f"{page.ww_grade.currentText()}，{page.ww_ind.currentText()}"
    if k == E.STACK:
        return f"GB 16297-1996 表2，速率{page.st_grade.currentText()}"
    if k == E.BOILER:
        return f"GB 13271-2014 {page.bo_table.currentText()}，燃料按点位名称识别，识别不到按{page.bo_fuel.currentText()}"
    if k == E.ODOR_STACK:
        return "GB 14554-93 表2"
    if k == E.ODOR_FENCE:
        return f"GB 14554-93 表1 {O.FENCE_CN[page.od_grade.currentData()]}"
    if k == E.FUGITIVE:
        return f"颗粒物：{page.fu_pm.currentText()}"
    return f"厂界外{page.bn_cls.currentText()}"
