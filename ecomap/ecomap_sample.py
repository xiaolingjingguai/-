# -*- coding: utf-8 -*-
"""生成虚构示例项目数据（仅用于熟悉软件和自检，非真实数据）。"""
import os

import numpy as np

import ecomap_core as C

EPSG = 4549  # CGCS2000 3 度带 CM 120E


def _voronoi_polys(rng, bounds, n):
    from shapely.geometry import MultiPoint, box
    from shapely.ops import voronoi_diagram
    x0, y0, x1, y1 = bounds
    pts = MultiPoint(list(zip(rng.uniform(x0, x1, n), rng.uniform(y0, y1, n))))
    frame = box(*bounds)
    return [p.intersection(frame) for p in voronoi_diagram(pts, envelope=frame).geoms]


def make_sample(out_dir, seed=20221):
    import geopandas as gpd
    import pandas as pd
    import rasterio
    from pyproj import Transformer
    from rasterio.transform import from_origin
    from shapely.geometry import LineString, Point, Polygon, box

    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(seed)
    tf = Transformer.from_crs(4490, EPSG, always_xy=True)
    cx, cy = tf.transform(118.55, 25.05)
    cx, cy = round(cx, -1), round(cy, -1)
    crs = "EPSG:%d" % EPSG
    P = os.path.join

    proj = gpd.GeoDataFrame({"类型": ["永久占地", "临时占地"]}, geometry=[
        Polygon([(cx - 320, cy - 180), (cx + 260, cy - 220), (cx + 330, cy + 150), (cx - 100, cy + 240),
                 (cx - 350, cy + 60)]),
        Polygon([(cx + 330, cy + 150), (cx + 520, cy + 120), (cx + 540, cy + 300), (cx + 350, cy + 320)]),
    ], crs=crs)
    proj.to_file(P(out_dir, "项目占地范围.shp"), encoding="utf-8")

    area = (cx - 2200, cy - 2000, cx + 2200, cy + 2000)
    lu_names = ["水田", "旱地", "果园", "茶园", "乔木林地", "乔木林地", "乔木林地", "竹林地", "灌木林地", "其他草地",
                "农村宅基地", "公路用地", "坑塘水面"]
    polys = _voronoi_polys(rng, area, 140)
    gpd.GeoDataFrame({"DLMC": rng.choice(lu_names, len(polys))}, geometry=polys, crs=crs).to_file(
        P(out_dir, "土地利用现状.shp"), encoding="utf-8")

    veg_names = ["马尾松林", "杉木林", "毛竹林", "桉树林", "芒萁灌草丛", "檵木灌丛", "农作物（水稻）", "经济林（茶）", "无植被区"]
    polys = _voronoi_polys(rng, area, 90)
    gpd.GeoDataFrame({"植被型": rng.choice(veg_names, len(polys))}, geometry=polys, crs=crs).to_file(
        P(out_dir, "植被类型.shp"), encoding="utf-8")

    eco_names = ["森林生态系统", "森林生态系统", "灌丛生态系统", "草地生态系统", "农田生态系统", "城镇生态系统", "湿地生态系统"]
    polys = _voronoi_polys(rng, area, 60)
    gpd.GeoDataFrame({"类型": rng.choice(eco_names, len(polys))}, geometry=polys, crs=crs).to_file(
        P(out_dir, "生态系统类型.shp"), encoding="utf-8")

    xs = np.linspace(cx - 4000, cx + 4000, 60)
    river = LineString([(x, cy - 900 + 380 * np.sin((x - cx) / 900.0)) for x in xs])
    trib = LineString([(cx + 600, cy - 650), (cx + 800, cy + 200), (cx + 1300, cy + 1500), (cx + 1500, cy + 2600)])
    pond = Point(cx - 1300, cy + 700).buffer(160)
    gpd.GeoDataFrame({"名称": ["示例溪", "示例支流", "示例水库"]}, geometry=[river, trib, pond], crs=crs).to_file(
        P(out_dir, "地表水系.shp"), encoding="utf-8")

    adm = []
    names = ["示例镇甲", "示例镇乙", "示例镇丙", "示例乡丁"]
    for i, (dx, dy) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
        adm.append(box(cx + min(0, dx) * 9000 + dx * 300, cy + min(0, dy) * 8000 + dy * 300,
                       cx + max(0, dx) * 9000 + dx * 300, cy + max(0, dy) * 8000 + dy * 300).buffer(300, join_style=2))
    gpd.GeoDataFrame({"名称": names}, geometry=adm, crs=crs).to_file(P(out_dir, "行政区划.shp"), encoding="utf-8")

    tg = gpd.GeoDataFrame({"类型": ["古树名木", "古树名木", "重点保护野生植物", "重要生境"],
                           "名称": ["樟树（树龄约300年）", "榕树（树龄约150年）", "金毛狗", "示例溪滨岸带"]},
                          geometry=[Point(cx - 900, cy + 500), Point(cx + 1100, cy - 300), Point(cx - 300, cy - 1300),
                                    river.buffer(60).intersection(box(cx - 1800, cy - 1600, cx - 600, cy - 300))],
                          crs=crs)
    tg.to_file(P(out_dir, "生态保护目标.gpkg"), layer="保护目标", driver="GPKG")

    hb = gpd.GeoDataFrame({"类型": ["重要生境", "重点保护野生动物活动区"], "名称": ["溪流湿地生境", "鸟类觅食区"]},
                          geometry=[river.buffer(120).intersection(box(*area)), Point(cx + 1400, cy + 1200).buffer(350)],
                          crs=crs)
    hb.to_file(P(out_dir, "重要物种及生境.gpkg"), layer="生境", driver="GPKG")

    mg = gpd.GeoDataFrame({"类型": ["鸟类迁飞路线（示意）", "鱼类洄游路线（示意）"], "名称": ["春季迁飞", "示例溪洄游"]},
                          geometry=[LineString([(cx - 2200, cy + 1800), (cx - 300, cy + 600), (cx + 2200, cy - 1500)]),
                                    LineString(list(river.coords)[15:45])], crs=crs)
    mg.to_file(P(out_dir, "迁徙洄游路线.gpkg"), layer="路线", driver="GPKG")

    sm_geom, sm_type, sm_id, sm_h = [], [], [], []
    for i in range(9):
        a = i * 0.7
        sm_geom.append(Point(cx + 1300 * np.cos(a) * (0.5 + i / 12), cy + 1200 * np.sin(a) * (0.5 + i / 12)))
        sm_type.append(["乔木样方", "灌木样方", "草本样方"][i % 3])
        sm_id.append("Y%d" % (i + 1))
        sm_h.append(int(rng.integers(60, 420)))
    sm_geom.append(LineString([(cx - 1500, cy - 1200), (cx - 600, cy - 300), (cx + 200, cy + 500)]))
    sm_type.append("动物调查样线"); sm_id.append("L1"); sm_h.append(None)
    gpd.GeoDataFrame({"类型": sm_type, "编号": sm_id, "海拔": sm_h}, geometry=sm_geom, crs=crs).to_file(
        P(out_dir, "调查样方样线.gpkg"), layer="样方样线", driver="GPKG")

    ms = gpd.GeoDataFrame({"措施类型": ["表土临时堆存场", "截排水沟", "边坡植被恢复区", "临时占地复绿区"],
                           "名称": ["表土堆场", "截水沟", "边坡复绿", "复绿区"]},
                          geometry=[box(cx - 330, cy + 280, cx - 220, cy + 360),
                                    LineString([(cx - 380, cy - 220), (cx + 280, cy - 270), (cx + 370, cy + 160)]),
                                    Polygon([(cx - 350, cy + 60), (cx - 320, cy - 180), (cx - 270, cy - 170), (cx - 300, cy + 60)]),
                                    Polygon([(cx + 330, cy + 150), (cx + 520, cy + 120), (cx + 540, cy + 300), (cx + 350, cy + 320)])],
                          crs=crs)
    ms.to_file(P(out_dir, "生态保护措施.gpkg"), layer="措施", driver="GPKG")

    # 监测点：GCJ-02 经纬度表（模拟从高德地图拾取），测试纠偏路径
    to_ll = Transformer.from_crs(EPSG, 4326, always_xy=True)
    rows = []
    for i, (dx, dy) in enumerate([(-700, 600), (900, -200), (200, 1300)]):
        lon, lat = to_ll.transform(cx + dx, cy + dy)
        glon, glat = C.wgs84_to_gcj02(lon, lat)
        rows.append({"点位编号": "M%d" % (i + 1), "监测内容": ["植物群落", "陆生动物", "水生生物"][i],
                     "经度": round(glon, 7), "纬度": round(glat, 7)})
    pd.DataFrame(rows).to_csv(P(out_dir, "生态监测点位_高德坐标.csv"), index=False, encoding="utf-8-sig")

    sens1 = gpd.GeoDataFrame({"功能区": ["核心保育区", "一般控制区"]}, geometry=[
        Point(cx - 1900, cy + 1900).buffer(900), Point(cx - 1900, cy + 1900).buffer(1700).difference(
            Point(cx - 1900, cy + 1900).buffer(900))], crs=crs)
    sens1.to_file(P(out_dir, "示例森林公园功能区.shp"), encoding="utf-8")
    sens2 = gpd.GeoDataFrame({"名称": ["生态保护红线"]}, geometry=[
        Polygon([(cx + 1200, cy - 2500), (cx + 3600, cy - 2300), (cx + 3300, cy - 700), (cx + 1500, cy - 1100)])],
        crs=crs)
    sens2.to_file(P(out_dir, "示例生态保护红线.shp"), encoding="utf-8")

    # NDVI（10 m，虚构）
    res = 10.0
    x0, y1 = cx - 2600, cy + 2400
    w, h = 520, 480
    yy, xx = np.mgrid[0:h, 0:w]
    ndvi = 0.45 + 0.25 * np.sin(xx / 47.0) * np.cos(yy / 61.0) + rng.normal(0, 0.06, (h, w))
    ndvi[(xx - 260) ** 2 + (yy - 240) ** 2 < 40 ** 2] = 0.08
    with rasterio.open(P(out_dir, "NDVI_示例.tif"), "w", driver="GTiff", width=w, height=h, count=1,
                       dtype="float32", crs=crs, transform=from_origin(x0, y1, res, res), nodata=-9999) as dst:
        dst.write(np.clip(ndvi, -1, 1).astype("float32"), 1)

    cfg = C.default_config()
    cfg.update(project_name="示例项目（虚构数据）", eval_level="二级", mapper="示例单位", buffer_m="500",
               out_dir=P(out_dir, "输出"))
    L = cfg["layers"]
    L["project"].update(path=P(out_dir, "项目占地范围.shp"), source="示例用地红线（虚构）")
    L["admin"].update(path=P(out_dir, "行政区划.shp"), label="名称", source="示例行政区划（虚构）")
    L["water"].update(path=P(out_dir, "地表水系.shp"), label="名称", source="示例水系（虚构）")
    L["landuse"].update(path=P(out_dir, "土地利用现状.shp"), field="DLMC", source="示例土地利用数据（虚构）")
    L["vegetation"].update(path=P(out_dir, "植被类型.shp"), field="植被型", source="示例植被数据（虚构）")
    L["ecosystem"].update(path=P(out_dir, "生态系统类型.shp"), field="类型", source="示例生态系统数据（虚构）")
    L["targets"].update(path=P(out_dir, "生态保护目标.gpkg"), layer="保护目标", field="类型", label="名称")
    L["habitat"].update(path=P(out_dir, "重要物种及生境.gpkg"), layer="生境", field="类型", label="名称")
    L["migration"].update(path=P(out_dir, "迁徙洄游路线.gpkg"), layer="路线", field="类型", label="名称")
    L["samples"].update(path=P(out_dir, "调查样方样线.gpkg"), layer="样方样线", field="类型", label="编号", elev="海拔")
    L["measures"].update(path=P(out_dir, "生态保护措施.gpkg"), layer="措施", field="措施类型", label="名称")
    L["monitor"].update(path=P(out_dir, "生态监测点位_高德坐标.csv"), field="监测内容", label="点位编号",
                        x="经度", y="纬度", epsg="4326", gcj02=True)
    cfg["sensitive"] = [
        {"path": P(out_dir, "示例森林公园功能区.shp"), "layer": "", "name": "示例森林公园", "field": "功能区",
         "source": "示例功能区划（虚构）"},
        {"path": P(out_dir, "示例生态保护红线.shp"), "layer": "", "name": "示例生态保护红线", "field": "",
         "source": "示例生态保护红线（虚构）"},
    ]
    cfg["fvc"].update(ndvi=P(out_dir, "NDVI_示例.tif"), source="示例 NDVI 栅格（虚构），10 m")
    path = P(out_dir, "示例项目.ecomap.json")
    C.save_config(cfg, path)
    return path
