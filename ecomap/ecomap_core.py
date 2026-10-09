# -*- coding: utf-8 -*-
"""生态制图核心：数据读入、坐标系、裁剪、面积统计、植被覆盖度（不依赖 arcpy）。

依据：《环境影响评价技术导则 生态影响》（HJ 19—2022）
  7.4.1、7.4.2  现状评价图件
  8.2.1、8.2.2  图形叠置法（工程占用类型、面积及比例）
  9.1.1         生态保护措施平面布置图
  附录 C.8.1    植被覆盖度 FVC = (NDVI-NDVIs)/(NDVIv-NDVIs)（式 C.5）
  附录 D        图件规范与要求（D.2 比例尺，D.3 图面辅助要素）
"""
import copy
import datetime
import json
import math
import os

import numpy as np

VERSION = "0.1"
VERSION_DATE = "2026-10-09"
STD = "《环境影响评价技术导则 生态影响》（HJ 19—2022）"

LEVELS = ["一级", "二级", "三级"]
STANDARD_SCALES = [2000, 5000, 10000, 25000, 50000, 100000, 250000, 500000, 1000000]
PAGES = {  # 宽, 高 (mm)
    "A4竖": (210, 297),
    "A4横": (297, 210),
    "A3竖": (297, 420),
    "A3横": (420, 297),
}

# 图层槽位：key, 名称, 需要的字段, 默认数据源说明
LAYER_SLOTS = [
    ("project", "项目占地范围（必填）", [], "建设单位提供的用地红线"),
    ("eval_range", "评价范围", [], "按 HJ 19—2022 6.2 确定"),
    ("admin", "行政区划", ["label"], "行政区划数据"),
    ("water", "地表水系", ["label"], "水系数据"),
    ("landuse", "土地利用现状", ["field"], "第三次全国国土调查成果及现场核查"),
    ("vegetation", "植被类型", ["field"], "现场样方调查及遥感解译"),
    ("ecosystem", "生态系统类型", ["field"], "遥感解译（HJ 1166 分类体系）及现场核查"),
    ("targets", "生态保护目标", ["field", "label"], "现场调查"),
    ("habitat", "重要物种及重要生境", ["field", "label"], "现场调查及资料收集"),
    ("migration", "物种迁徙、洄游路线", ["field", "label"], "资料收集"),
    ("samples", "调查样方、样线、点位", ["field", "label", "elev"], "现场调查"),
    ("measures", "生态保护措施", ["field", "label"], "生态保护措施设计"),
    ("monitor", "生态监测点位", ["field", "label"], "生态监测计划"),
]
SLOT_NAMES = {k: n for k, n, _, _ in LAYER_SLOTS}

# 图件清单：按 HJ 19—2022 正文条款归纳（见 生态图件清单与制图说明.md）
# req: ●应编制 ○涉及时编制 △可选 —未要求
MAP_SPECS = [
    dict(id="location", title="项目地理位置图", req={"一级": "●", "二级": "●", "三级": "●"},
         basis="表D.1（通用基础图件，归类为推断）", theme=None, needs=["project"], extent="admin"),
    dict(id="water", title="地表水系图", req={"一级": "●", "二级": "●", "三级": "●"},
         basis="表D.1（通用基础图件，归类为推断）", theme="water", needs=["water"], extent="eval"),
    dict(id="landuse", title="土地利用现状图", req={"一级": "●", "二级": "●", "三级": "●"},
         basis="7.4.1 b）、7.4.2、表D.1", theme="landuse", needs=["landuse"], extent="eval"),
    dict(id="vegetation", title="植被类型图", req={"一级": "●", "二级": "●", "三级": "●"},
         basis="7.4.1 a）、7.4.2、表D.1", theme="vegetation", needs=["vegetation"], extent="eval"),
    dict(id="fvc", title="植被覆盖度空间分布图", req={"一级": "△", "二级": "△", "三级": "—"},
         basis="7.4.1 a）、附录C.8.1", theme="fvc", needs=["fvc"], extent="eval"),
    dict(id="ecosystem", title="生态系统类型图", req={"一级": "●", "二级": "●", "三级": "—"},
         basis="7.4.1 d）、表D.1", theme="ecosystem", needs=["ecosystem"], extent="eval"),
    dict(id="targets", title="生态保护目标空间分布图", req={"一级": "●", "二级": "●", "三级": "●"},
         basis="7.4.2、表D.1", theme="targets", needs=["targets"], extent="eval"),
    dict(id="sensitive", title="生态敏感区分布图", req={"一级": "○", "二级": "○", "三级": "○"},
         basis="7.4.1 e）、D.2、表D.1（每处单独成图）", theme="sensitive", needs=["sensitive"], extent="sensitive"),
    dict(id="habitat", title="重要物种及重要生境分布图", req={"一级": "○", "二级": "○", "三级": "—"},
         basis="7.4.1 c）", theme="habitat", needs=["habitat"], extent="eval"),
    dict(id="migration", title="物种迁徙、洄游路线图", req={"一级": "○", "二级": "○", "三级": "—"},
         basis="7.4.1 c）、表D.1", theme="migration", needs=["migration"], extent="eval"),
    dict(id="samples", title="调查样方、样线、点位布设图", req={"一级": "●", "二级": "●", "三级": "△"},
         basis="7.3.4～7.3.6、表D.1、D.2", theme="samples", needs=["samples"], extent="eval", max_scale=10000),
    dict(id="occ_landuse", title="工程占用土地利用类型叠置图", req={"一级": "●", "二级": "●", "三级": "△"},
         basis="8.2.1 a）d）、8.2.2、附录C.2", theme="landuse", needs=["landuse"], extent="project", occupy=True),
    dict(id="occ_vegetation", title="工程占用植被类型叠置图", req={"一级": "●", "二级": "●", "三级": "△"},
         basis="8.2.1 a）d）、8.2.2、附录C.2", theme="vegetation", needs=["vegetation"], extent="project", occupy=True),
    dict(id="occ_ecosystem", title="工程占用生态系统类型叠置图", req={"一级": "●", "二级": "●", "三级": "△"},
         basis="8.2.1 a）d）、8.2.2、附录C.2", theme="ecosystem", needs=["ecosystem"], extent="project", occupy=True),
    dict(id="measures", title="生态保护措施平面布置图", req={"一级": "●", "二级": "●", "三级": "●"},
         basis="9.1.1、D.2", theme="measures", needs=["measures"], extent="project", max_scale=10000),
    dict(id="monitor", title="生态监测布点图", req={"一级": "○", "二级": "○", "三级": "○"},
         basis="9.3.2、表D.1、D.2", theme="monitor", needs=["monitor"], extent="eval", max_scale=10000),
]
SPEC_BY_ID = {s["id"]: s for s in MAP_SPECS}

FVC_DEFAULT = {
    "ndvi": "", "red": "", "nir": "",
    "scale": 1.0, "offset": 0.0,
    "s_pct": 5.0, "v_pct": 95.0,
    "breaks": [0.30, 0.45, 0.60, 0.75],
    "labels": ["低覆盖度（<30%）", "中低覆盖度（30%～45%）", "中覆盖度（45%～60%）",
               "中高覆盖度（60%～75%）", "高覆盖度（≥75%）"],
    "source": "Sentinel-2 L2A 影像（成像日期请填写），分辨率 10 m",
}


def default_config():
    layers = {}
    for key, _, _, src in LAYER_SLOTS:
        layers[key] = {"path": "", "layer": "", "field": "", "label": "", "elev": "",
                       "source": src, "x": "", "y": "", "epsg": "4490", "gcj02": False}
    return {
        "app": "ecomap", "version": VERSION,
        "project_name": "XX建设项目",
        "eval_level": "三级",
        "mapper": "XX环境科技有限公司",
        "page": "A4竖",
        "scale_mode": "标准比例尺",   # 标准比例尺 / 充满图幅
        "dpi": 300,
        "formats": ["pdf", "jpg"],
        "epsg": "",               # 空 = 按项目中心经度自动选 CGCS2000 3 度带
        "buffer_m": "",           # 无评价范围时按占地外扩
        "height_datum": "1985国家高程基准",
        "out_dir": "",
        "basemap": {"path": "", "source": "", "tianditu_key": "", "tianditu_type": "不使用"},
        "layers": layers,
        "sensitive": [],          # [{"path","layer","name","field","source"}]
        "fvc": copy.deepcopy(FVC_DEFAULT),
        "colors": {},             # {图层key: {类别: "#rrggbb"}}
        "maps": [s["id"] for s in MAP_SPECS],
    }


def merge_config(cfg):
    """把旧版本/不完整配置补齐默认值。"""
    base = default_config()
    for k, v in cfg.items():
        if k == "layers":
            for lk, lv in v.items():
                base["layers"].setdefault(lk, {}).update(lv)
        elif isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k].update(v)
        else:
            base[k] = v
    return base


def save_config(cfg, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return merge_config(json.load(f))


# ============================================================ 纯计算函数
def cgcs2000_3deg_epsg(lon):
    """CGCS2000 3 度带高斯-克吕格（不带带号）EPSG：中央经线 75°E→4534，每 3° 加 1。"""
    cm = int(round(lon / 3.0)) * 3
    if not 75 <= cm <= 135:
        raise ValueError("经度 %.4f 超出 CGCS2000 3 度带（75°E～135°E）范围" % lon)
    return 4534 + (cm - 75) // 3


def choose_scale(extent_w_m, extent_h_m, frame_w_mm, frame_h_mm, margin=1.08):
    """返回能完整容纳范围的最小标准比例尺分母（图面尽量大）。"""
    need = max(extent_w_m / frame_w_mm, extent_h_m / frame_h_mm) * 1000.0 * margin
    for s in STANDARD_SCALES:
        if s >= need:
            return s
    return int(math.ceil(need / 1e5) * 1e5)


def nice_bar_length(ground_w_m, frac=0.22):
    """比例尺线段总长：取地面宽度约 frac 倍，圆整到 1/2/5×10^n 米。"""
    target = ground_w_m * frac
    p = 10 ** math.floor(math.log10(target))
    for m in (5, 2, 1):
        if m * p <= target:
            return m * p
    return p


def fvc_from_ndvi(ndvi, s_pct, v_pct):
    """式 C.5：FVC=(NDVI-NDVIs)/(NDVIv-NDVIs)。NDVIs/NDVIv 取有效像元百分位，结果截断到 [0,1]。
    返回 (fvc, NDVIs, NDVIv)，无效像元为 NaN。"""
    ndvi = np.asarray(ndvi, dtype="float64")
    valid = np.isfinite(ndvi)
    if valid.sum() < 10:
        raise ValueError("评价范围内有效 NDVI 像元不足 10 个，请检查影像范围")
    ns, nv = np.percentile(ndvi[valid], [s_pct, v_pct])
    if nv <= ns:
        raise ValueError("NDVIv（%.4f）不大于 NDVIs（%.4f），请检查影像" % (nv, ns))
    fvc = np.clip((ndvi - ns) / (nv - ns), 0.0, 1.0)
    fvc[~valid] = np.nan
    return fvc, float(ns), float(nv)


def ndvi_from_bands(red, nir, scale=1.0, offset=0.0):
    """NDVI=(ρNIR-ρRed)/(ρNIR+ρRed)，ρ=DN×scale+offset。"""
    r = np.asarray(red, dtype="float64") * scale + offset
    n = np.asarray(nir, dtype="float64") * scale + offset
    with np.errstate(divide="ignore", invalid="ignore"):
        v = (n - r) / (n + r)
    v[~np.isfinite(v)] = np.nan
    return np.clip(v, -1, 1)


def classify(values, breaks):
    """按断点分级：返回 1..len(breaks)+1，NaN→0。"""
    values = np.asarray(values, dtype="float64")
    out = np.digitize(np.nan_to_num(values, nan=-1.0), breaks) + 1
    out[~np.isfinite(values)] = 0
    return out.astype("uint8")


def area_table(rows, total=None):
    """rows: {类型: 面积 m²} → [(类型, 面积 hm², 比例 %)]，面积降序，末行合计。"""
    s = sum(rows.values())
    tot = total if total else s
    out = []
    for k, a in sorted(rows.items(), key=lambda kv: -kv[1]):
        out.append((str(k), round(a / 1e4, 4), round(a / tot * 100, 2) if tot else 0.0))
    out.append(("合计", round(s / 1e4, 4), round(s / tot * 100, 2) if tot else 0.0))
    return out


# GCJ-02 → WGS-84（逆变换迭代，精度优于 0.5 m）
_A = 6378245.0
_EE = 0.00669342162296594323


def _out_of_china(lon, lat):
    return not (72.004 <= lon <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _tlat(x, y):
    r = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    r += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    r += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    r += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return r


def _tlon(x, y):
    r = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    r += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    r += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    r += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return r


def wgs84_to_gcj02(lon, lat):
    if _out_of_china(lon, lat):
        return lon, lat
    dlat = _tlat(lon - 105.0, lat - 35.0)
    dlon = _tlon(lon - 105.0, lat - 35.0)
    rad = lat / 180.0 * math.pi
    magic = 1 - _EE * math.sin(rad) ** 2
    sq = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sq) * math.pi)
    dlon = (dlon * 180.0) / (_A / sq * math.cos(rad) * math.pi)
    return lon + dlon, lat + dlat


def gcj02_to_wgs84(lon, lat):
    if _out_of_china(lon, lat):
        return lon, lat
    wl, wa = lon, lat
    for _ in range(30):
        gl, ga = wgs84_to_gcj02(wl, wa)
        dl, da = gl - lon, ga - lat
        wl, wa = wl - dl, wa - da
        if abs(dl) < 1e-9 and abs(da) < 1e-9:
            break
    return wl, wa


# ============================================================ 数据读入（geopandas）
class DataError(Exception):
    pass


def _gpd():
    import geopandas as gpd
    return gpd


def shp_encoding(path):
    """无 .cpg 的 shp：DBF 文本不是合法 UTF-8 而可按 GBK 解码时返回 "gbk"，否则 None（交 GDAL 判断）。"""
    if not path.lower().endswith(".shp"):
        return None
    base = os.path.splitext(path)[0]
    if any(os.path.exists(base + e) for e in (".cpg", ".CPG")):
        return None
    dbf = next((base + e for e in (".dbf", ".DBF") if os.path.exists(base + e)), None)
    if not dbf:
        return None
    with open(dbf, "rb") as f:
        raw = f.read(262144)
    if len(raw) > 29 and raw[29] == 0x4D:      # LDID 936（GBK），GDAL 可识别
        return None
    if not any(b > 0x7F for b in raw):
        return None
    try:
        raw.decode("utf-8")
        return None
    except UnicodeDecodeError as e:
        if e.start > len(raw) - 4:              # 截断处的半个字符
            return None
    try:
        raw.decode("gbk", errors="strict")
    except UnicodeDecodeError as e:
        if e.start <= len(raw) - 2:
            return None
    return "gbk"


def list_layers(path):
    """多图层数据源（gpkg、gdb、dxf、kml）返回图层名列表。"""
    import pyogrio
    try:
        return [str(x[0]) for x in pyogrio.list_layers(path)]
    except Exception:
        return []


def list_fields(path, layer=""):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".csv", ".txt"):
        return [str(c) for c in _read_table(path).columns]
    if ext in (".xlsx", ".xls"):
        return [str(c) for c in _read_table(path).columns]
    import pyogrio
    info = pyogrio.read_info(path, layer=layer or None, encoding=shp_encoding(path))
    return [str(f) for f in info["fields"]]


def _read_table(path):
    import pandas as pd
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    for enc in ("utf-8-sig", "gbk"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise DataError("无法识别 %s 的编码（请另存为 UTF-8 或 GBK 的 CSV）" % path)


def read_layer(spec, name=""):
    """按槽位配置读入矢量；点位表（csv/xlsx）按 X/Y 字段建点。返回 GeoDataFrame。"""
    gpd = _gpd()
    path = (spec or {}).get("path", "")
    if not path:
        return None
    if not os.path.exists(path):
        raise DataError("%s：文件不存在 %s" % (name, path))
    ext = os.path.splitext(path)[1].lower()
    if ext in (".csv", ".txt", ".xlsx", ".xls"):
        df = _read_table(path)
        xf, yf = spec.get("x") or "", spec.get("y") or ""
        if xf not in df.columns or yf not in df.columns:
            raise DataError("%s：点位表须指定 X（经度/东坐标）与 Y（纬度/北坐标）字段，现有字段：%s"
                            % (name, "、".join(map(str, df.columns))))
        xs = df[xf].astype(float).to_numpy()
        ys = df[yf].astype(float).to_numpy()
        epsg = int(spec.get("epsg") or 4490)
        if spec.get("gcj02"):
            if epsg not in (4326, 4490):
                raise DataError("%s：GCJ-02 纠偏只适用于经纬度坐标（EPSG 4326/4490）" % name)
            pts = [gcj02_to_wgs84(x, y) for x, y in zip(xs, ys)]
            xs = np.array([p[0] for p in pts])
            ys = np.array([p[1] for p in pts])
        gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(xs, ys), crs="EPSG:%d" % epsg)
    else:
        try:
            enc = shp_encoding(path)
            kw = {"encoding": enc} if enc else {}
            gdf = gpd.read_file(path, layer=spec.get("layer") or None, **kw)
        except Exception as e:
            raise DataError("%s：读取失败（%s）" % (name, e))
        if gdf.crs is None:
            raise DataError("%s：数据未定义坐标系（缺 .prj），请先在 GIS 软件中定义投影" % name)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    if gdf.empty:
        raise DataError("%s：没有有效要素" % name)
    for k in ("field", "label", "elev"):
        f = spec.get(k)
        if f and f not in gdf.columns:
            raise DataError("%s：找不到字段“%s”，现有字段：%s" % (name, f, "、".join(map(str, gdf.columns))))
    return gdf


def target_crs(cfg, project_gdf):
    from pyproj import CRS
    if str(cfg.get("epsg") or "").strip():
        return CRS.from_epsg(int(cfg["epsg"]))
    c = project_gdf.to_crs(4490).union_all().centroid
    return CRS.from_epsg(cgcs2000_3deg_epsg(c.x))


def crs_desc(crs):
    """图面注记用坐标系说明。"""
    name = crs.name
    if "Gauss-Kruger CM" in name:
        cm = name.split("CM")[-1].strip().rstrip("E")
        return "2000国家大地坐标系（CGCS2000），高斯-克吕格投影 3 度带，中央经线 %s°E" % cm
    return "%s（EPSG:%s）" % (name, crs.to_epsg())


def _fix(gdf):
    if gdf is None:
        return None
    if gdf.geom_type.isin(["Polygon", "MultiPolygon"]).any():
        gdf = gdf.copy()
        gdf["geometry"] = gdf.geometry.make_valid()
    return gdf


def dissolve_area(gdf, field):
    """按字段统计面积（m²），只计面要素。"""
    poly = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon", "GeometryCollection"])]
    rows = {}
    for k, g in poly.groupby(poly[field].astype(str)):
        rows[k] = float(g.geometry.area.sum())
    return rows


def clip(gdf, mask_geom):
    gpd = _gpd()
    if gdf is None:
        return None
    out = gpd.clip(gdf, mask_geom)
    out = out[~out.geometry.is_empty]
    return out


class Context:
    """一次制图任务的已读入、已投影数据。"""

    def __init__(self, cfg, log=print):
        self.cfg = merge_config(cfg)
        self.log = log
        self.layers = {}
        self.sensitive = []
        self.notes = []
        self.stats = {}        # 表名 → [(类型, hm², %)]
        self.fvc = None        # dict(arr, extent, ns, nv, classes)
        self.load()

    def load(self):
        gpd = _gpd()
        cfg = self.cfg
        L = cfg["layers"]
        proj = read_layer(L["project"], SLOT_NAMES["project"])
        if proj is None:
            raise DataError("必须提供“项目占地范围”数据")
        self.crs = target_crs(cfg, proj)
        self.log("目标坐标系：%s" % crs_desc(self.crs))
        self.layers["project"] = _fix(proj.to_crs(self.crs))
        self.project_geom = self.layers["project"].union_all()
        er = read_layer(L["eval_range"], SLOT_NAMES["eval_range"])
        if er is not None:
            self.eval_geom = _fix(er.to_crs(self.crs)).union_all()
            self.log("评价范围：采用提供的评价范围数据")
        else:
            b = str(cfg.get("buffer_m") or "").strip()
            if not b:
                raise DataError("须提供“评价范围”数据，或在“项目信息”中填写外扩距离（HJ 19—2022 6.2）")
            self.eval_geom = self.project_geom.buffer(float(b))
            self.log("评价范围：项目占地外扩 %s m 生成（外扩距离须按 HJ 19—2022 6.2 论证）" % b)
        self.layers["eval_range"] = gpd.GeoDataFrame(geometry=[self.eval_geom], crs=self.crs)
        self.log("项目占地面积 %.4f hm²，评价范围面积 %.4f hm²"
                 % (self.project_geom.area / 1e4, self.eval_geom.area / 1e4))
        for key, name, _, _ in LAYER_SLOTS:
            if key in ("project", "eval_range"):
                continue
            g = read_layer(L[key], name)
            if g is not None:
                self.layers[key] = _fix(g.to_crs(self.crs))
                self.log("已读入 %s：%d 个要素" % (name, len(g)))
        for i, s in enumerate(cfg.get("sensitive") or []):
            if not s.get("path"):
                continue
            nm = s.get("name") or "生态敏感区%d" % (i + 1)
            g = read_layer(s, nm)
            self.sensitive.append((s, _fix(g.to_crs(self.crs))))
            self.log("已读入生态敏感区 %s：%d 个要素" % (nm, len(g)))
        self._stats()
        f = cfg.get("fvc") or {}
        if f.get("ndvi") or (f.get("red") and f.get("nir")):
            self.fvc = compute_fvc(f, self.crs, self.eval_geom, self.log)
            t = area_table({lab: a for lab, a in zip(f["labels"], self.fvc["class_area"])})
            self.stats["植被覆盖度分级面积"] = t

    def has(self, key):
        if key == "sensitive":
            return bool(self.sensitive)
        if key == "fvc":
            return self.fvc is not None
        return key in self.layers

    def _stats(self):
        L = self.cfg["layers"]
        for key in ("landuse", "vegetation", "ecosystem"):
            if key not in self.layers:
                continue
            fld = L[key].get("field")
            if not fld:
                self.log("提示：%s 未指定分类字段，跳过面积统计" % SLOT_NAMES[key])
                continue
            g = self.layers[key]
            inside = clip(g, self.eval_geom)
            self.stats["评价范围内%s面积" % SLOT_NAMES[key]] = area_table(dissolve_area(inside, fld))
            occ = clip(g, self.project_geom)
            rows = dissolve_area(occ, fld)
            self.stats["工程占用%s面积" % SLOT_NAMES[key]] = area_table(rows, total=None)
            covered = sum(rows.values())
            if covered < self.project_geom.area * 0.99:
                self.log("提示：%s 数据未完全覆盖项目占地（覆盖 %.1f%%），占用统计可能偏小"
                         % (SLOT_NAMES[key], covered / self.project_geom.area * 100))


# ============================================================ 栅格
def _read_window(path, crs, geom, band=1, pad=0.02):
    import rasterio
    from rasterio.warp import transform_bounds, reproject, Resampling, calculate_default_transform
    from rasterio.windows import from_bounds
    with rasterio.open(path) as src:
        if src.crs is None:
            raise DataError("影像 %s 未定义坐标系" % path)
        b = geom.bounds
        dx, dy = (b[2] - b[0]) * pad, (b[3] - b[1]) * pad
        sb = transform_bounds(crs, src.crs, b[0] - dx, b[1] - dy, b[2] + dx, b[3] + dy, densify_pts=21)
        win = from_bounds(*sb, transform=src.transform).round_offsets().round_lengths()
        arr = src.read(band, window=win, boundless=True, fill_value=src.nodata if src.nodata is not None else 0,
                       masked=False).astype("float64")
        if src.nodata is not None:
            arr[arr == src.nodata] = np.nan
        wt = src.window_transform(win)
        h, w = arr.shape
        dt, dw, dh = calculate_default_transform(src.crs, crs, w, h, *rasterio.transform.array_bounds(h, w, wt))
        out = np.full((dh, dw), np.nan)
        reproject(arr, out, src_transform=wt, src_crs=src.crs, dst_transform=dt, dst_crs=crs,
                  resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan)
        return out, dt


def compute_fvc(f, crs, eval_geom, log=print):
    from rasterio.features import geometry_mask
    from rasterio.transform import array_bounds
    if f.get("ndvi"):
        ndvi, tr = _read_window(f["ndvi"], crs, eval_geom)
        log("植被覆盖度：读入 NDVI 栅格")
    else:
        red, tr = _read_window(f["red"], crs, eval_geom)
        nir, tr2 = _read_window(f["nir"], crs, eval_geom)
        if red.shape != nir.shape:
            raise DataError("红光与近红外波段范围或分辨率不一致")
        ndvi = ndvi_from_bands(red, nir, float(f.get("scale") or 1), float(f.get("offset") or 0))
        log("植被覆盖度：由红光、近红外波段计算 NDVI（ρ=DN×%s+%s）" % (f.get("scale"), f.get("offset")))
    mask = geometry_mask([eval_geom], out_shape=ndvi.shape, transform=tr, invert=True)
    ndvi[~mask] = np.nan
    fvc, ns, nv = fvc_from_ndvi(ndvi, float(f["s_pct"]), float(f["v_pct"]))
    cls = classify(fvc, f["breaks"])
    px = abs(tr.a * tr.e)
    class_area = [float((cls == i).sum() * px) for i in range(1, len(f["breaks"]) + 2)]
    h, w = ndvi.shape
    l, b, r, t = array_bounds(h, w, tr)
    log("植被覆盖度：NDVIs=%.4f（%s%% 分位），NDVIv=%.4f（%s%% 分位），像元 %.2f m×%.2f m；"
        "百分位取值与分级断点为经验取值，导则未规定，报告中须说明" % (ns, f["s_pct"], nv, f["v_pct"], abs(tr.a), abs(tr.e)))
    return dict(fvc=fvc, cls=cls, extent=(l, r, b, t), ns=ns, nv=nv, class_area=class_area,
                mean=float(np.nanmean(fvc)))


def read_basemap(path, crs, bounds, max_px=3000):
    """读入底图栅格并重投影到目标坐标系、指定范围。返回 (RGB 或灰度数组, extent)。"""
    import rasterio
    from rasterio.warp import reproject, Resampling, transform_bounds
    from rasterio.transform import from_bounds as tfb
    from rasterio.windows import from_bounds
    l, b, r, t = bounds
    w = h = max_px
    if (r - l) > (t - b):
        h = max(1, int(max_px * (t - b) / (r - l)))
    else:
        w = max(1, int(max_px * (r - l) / (t - b)))
    dt = tfb(l, b, r, t, w, h)
    with rasterio.open(path) as src:
        if src.crs is None:
            raise DataError("底图 %s 未定义坐标系" % path)
        n = 3 if src.count >= 3 else 1
        sb = transform_bounds(crs, src.crs, l, b, r, t, densify_pts=21)
        win = from_bounds(*sb, transform=src.transform).round_offsets().round_lengths()
        out = np.zeros((n, h, w), dtype="float64")
        for i in range(n):
            arr = src.read(i + 1, window=win, boundless=True, fill_value=0).astype("float64")
            reproject(arr, out[i], src_transform=src.window_transform(win), src_crs=src.crs,
                      dst_transform=dt, dst_crs=crs, resampling=Resampling.bilinear)
    return _stretch(out), (l, r, b, t)


def _stretch(out):
    """2%～98% 线性拉伸到 0～1。"""
    res = np.zeros_like(out)
    for i in range(out.shape[0]):
        v = out[i][out[i] > 0]
        if v.size == 0:
            continue
        lo, hi = np.percentile(v, [2, 98])
        if hi <= lo:
            hi = lo + 1
        res[i] = np.clip((out[i] - lo) / (hi - lo), 0, 1)
    if res.shape[0] == 1:
        return res[0]
    return np.moveaxis(res, 0, -1)


TIANDITU_TYPES = {"影像（img_w）": ("img", "cia"), "矢量（vec_w）": ("vec", "cva"), "地形晕渲（ter_w）": ("ter", "cta")}


def tianditu_basemap(key, kind, crs, bounds, max_px=2400, log=print):
    """天地图 WMTS（Web 墨卡托）瓦片拼接后重投影到目标坐标系。须用户自行申请的浏览器端/服务端 key。
    天地图并非 HJ 19—2022 D.2 所指“标准地形图”，只作参考底图。"""
    import io
    import urllib.request
    from pyproj import Transformer
    from rasterio.warp import reproject, Resampling
    from rasterio.transform import from_bounds as tfb
    from PIL import Image
    lyr, ann = TIANDITU_TYPES[kind]
    tf = Transformer.from_crs(crs, 3857, always_xy=True)
    l, b, r, t = bounds
    xs, ys = tf.transform([l, r, l, r], [b, b, t, t])
    mx0, mx1, my0, my1 = min(xs), max(xs), min(ys), max(ys)
    R = 20037508.342789244
    z = 18
    while z > 3:
        n = 2 ** z
        span = 2 * R / n
        nx = int((mx1 - mx0) / span) + 2
        ny = int((my1 - my0) / span) + 2
        if nx * 256 <= max_px * 1.5 and ny * 256 <= max_px * 1.5:
            break
        z -= 1
    n = 2 ** z
    span = 2 * R / n
    c0, c1 = int((mx0 + R) / span), int((mx1 + R) / span)
    r0, r1 = int((R - my1) / span), int((R - my0) / span)
    W, H = (c1 - c0 + 1) * 256, (r1 - r0 + 1) * 256
    mosaic = np.zeros((H, W, 3), dtype="float64")
    for layer in (lyr, ann):
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                url = ("https://t%d.tianditu.gov.cn/%s_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
                       "&LAYER=%s&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX=%d&TILEROW=%d&TILECOL=%d&tk=%s"
                       % ((row + col) % 8, layer, layer, z, row, col, key))
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 ecomap"})
                data = urllib.request.urlopen(req, timeout=20).read()
                im = Image.open(io.BytesIO(data)).convert("RGBA")
                a = np.asarray(im, dtype="float64") / 255.0
                y0, x0 = (row - r0) * 256, (col - c0) * 256
                blk = mosaic[y0:y0 + 256, x0:x0 + 256]
                alpha = a[..., 3:4]
                blk[:] = blk * (1 - alpha) + a[..., :3] * alpha
    st = tfb(-R + c0 * span, R - (r1 + 1) * span, -R + (c1 + 1) * span, R - r0 * span, W, H)
    w = h = max_px
    if (r - l) > (t - b):
        h = max(1, int(max_px * (t - b) / (r - l)))
    else:
        w = max(1, int(max_px * (r - l) / (t - b)))
    dt = tfb(l, b, r, t, w, h)
    out = np.zeros((3, h, w))
    for i in range(3):
        reproject(np.ascontiguousarray(mosaic[..., i]), out[i], src_transform=st, src_crs="EPSG:3857",
                  dst_transform=dt, dst_crs=crs, resampling=Resampling.bilinear)
    log("天地图底图：第 %d 级，%d 张瓦片" % (z, (c1 - c0 + 1) * (r1 - r0 + 1) * 2))
    return np.moveaxis(out, 0, -1), (l, r, b, t)


# ============================================================ 图件清单
def checklist(ctx_or_cfg, generated=None):
    """按评价等级列出图件要求与生成情况。返回 [(序号, 图件, 要求, 依据, 情况)]。"""
    generated = generated or {}
    cfg = ctx_or_cfg.cfg if isinstance(ctx_or_cfg, Context) else ctx_or_cfg
    lvl = cfg.get("eval_level") or "三级"
    rows = []
    for i, s in enumerate(MAP_SPECS, 1):
        req = s["req"].get(lvl, "—")
        g = generated.get(s["id"])
        if g:
            st = "已生成 %d 幅" % len(g)
        elif isinstance(ctx_or_cfg, Context) and not all(ctx_or_cfg.has(n) for n in s["needs"]):
            st = "缺资料：%s" % "、".join(SLOT_NAMES.get(n, {"sensitive": "生态敏感区", "fvc": "遥感影像"}.get(n, n))
                                     for n in s["needs"] if not ctx_or_cfg.has(n))
        else:
            st = "未生成"
        rows.append((i, s["title"], req, s["basis"], st))
    rows.append((len(rows) + 1, "项目总平面布置图及施工总布置图", "●", "表D.1", "取自设计文件（CAD），本程序不生成"))
    rows.append((len(rows) + 1, "线性工程平纵断面图", "○", "表D.1", "取自设计文件，本程序不生成"))
    rows.append((len(rows) + 1, "生态保护措施设计图", "●", "9.1.1", "取自设计文件，本程序不生成"))
    return rows


def today_cn():
    d = datetime.date.today()
    return "%d年%d月" % (d.year, d.month)
