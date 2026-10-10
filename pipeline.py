# -*- coding: utf-8 -*-
"""判定流程封装：读取 → 判定 → 汇总 → 导出。供界面（app.py）与命令行（run.py）共用。"""
import judge
import gw_judge
import air_judge
import noise_judge
import soil_judge
import marine_judge
import emission_judge
import emission_parser
import export_emission
from emission_judge import WASTEWATER, STACK, FUGITIVE, BNOISE, EMISSION
from parser import read_report
from export import to_excel, to_word, gw_to_excel, gw_to_word
import export_more

SURFACE, GROUNDWATER, AIR, NOISE, SOIL = "surface", "groundwater", "air", "noise", "soil"
SEDIMENT, BIOTA = "sediment", "biota"
MORE = (AIR, NOISE, SOIL, SEDIMENT, BIOTA)


def load(path, kind):
    """返回 (records, warnings)。records 为长表：station, date, item, value, unit, report_limit, raw, src_note"""
    if kind in EMISSION:
        return emission_parser.read_emission(path, kind)
    return read_report(path, kind)


def assess(records, kind, target="III", water_body="river", drink=False, tn_ref=False,
           level=2, phase="transition", noise_cls="2", land="build2", marine_cls=1, **ep):
    """返回 dict(detail, summary, overall, stats)；排放标准各页的参数经 ep 传入"""
    if kind in EMISSION:
        detail = emission_judge.evaluate(records, kind, ep)
        for d, r in zip(detail, records):
            if r.get("src_note"):
                d["note"] = "；".join(x for x in (d["note"], r["src_note"]) if x)
        return dict(detail=detail, summary=emission_judge.summarize(detail, kind), overall=[], stats=[])
    if kind == AIR:
        detail = air_judge.evaluate(air_judge.infer_periods(records), level, phase)
        return dict(detail=detail, summary=air_judge.summarize(detail), overall=[], stats=[])
    if kind == NOISE:
        detail = noise_judge.evaluate(records, noise_cls)
        return dict(detail=detail, summary=noise_judge.summarize(detail), overall=[], stats=[])
    if kind in (SEDIMENT, BIOTA):
        detail = marine_judge.evaluate(records, kind, marine_cls)
    elif kind == SOIL:
        detail = soil_judge.evaluate(records, land)
    elif kind == GROUNDWATER:
        detail = gw_judge.evaluate(records, target)
    else:
        detail = judge.evaluate(records, target, water_body, drink, tn_ref)
    for d, r in zip(detail, records):
        if r.get("src_note"):
            d["note"] = "；".join(x for x in (d["note"], r["src_note"]) if x)
    if kind == SOIL:
        return dict(detail=detail, summary=soil_judge.summarize(detail), overall=[], stats=[])
    if kind in (SEDIMENT, BIOTA):
        return dict(detail=detail, summary=marine_judge.summarize(detail), overall=[], stats=[])
    if kind == GROUNDWATER:
        return dict(detail=detail, summary=gw_judge.summarize(detail),
                    overall=gw_judge.overall(detail), stats=gw_judge.statistics(detail))
    return dict(detail=detail, summary=judge.summarize(detail), overall=[], stats=[])


def export_word(path, res, kind, target="III", water_body="river", **p):
    if kind in EMISSION:
        export_emission.export(path, res, kind, p)
    elif kind in MORE:
        export_more.export(path, res, kind, p)
    elif kind == GROUNDWATER:
        gw_to_word(path, res["summary"], res["overall"], target, res["stats"])
    else:
        to_word(path, res["summary"], target, water_body)


def export_excel(path, res, kind, target="III", water_body="river", **p):
    if kind in EMISSION:
        export_emission.export(path, res, kind, p)
    elif kind in MORE:
        export_more.export(path, res, kind, p)
    elif kind == GROUNDWATER:
        gw_to_excel(path, res["summary"], res["detail"], res["overall"], target, res["stats"])
    else:
        to_excel(path, res["summary"], res["detail"], target, water_body)
