# -*- coding: utf-8 -*-
"""
生态影响评价图件批量制图脚本（ArcGIS Pro 3.0 及以上，arcpy）

依据：《环境影响评价技术导则 生态影响》（HJ 19—2022）
  - 7.4.1、7.4.2  现状评价图件
  - 8.2.1、8.2.2  图形叠置法预测（工程占用类型、面积及比例）
  - 9.1.1         生态保护措施平面布置图
  - 附录 C.8.1    植被覆盖度 FVC = (NDVI-NDVIs)/(NDVIv-NDVIs)  （式 C.5）
  - 附录 D        图件规范与要求（D.2 比例尺、D.3 图面辅助要素）

用法：
  1. 修改下方 CONFIG（只需填有数据的项，没有的保持 None，对应图件自动跳过）。
  2. 在 ArcGIS Pro 中打开工程 → “分析”选项卡 → Python 窗口，执行：
         exec(open(r"D:\\生态图件\\eco_maps.py", encoding="utf-8").read())
     或在 Pro 外运行（CONFIG["aprx"] 须填 .aprx 路径）：
         "C:\\Program Files\\ArcGIS\\Pro\\bin\\Python\\scripts\\propy.bat" eco_maps.py
  3. 输出：out_dir 下的 PDF/JPG 图件、面积统计 CSV、处理后数据 gdb，
     以及工程中新建的地图与布局（可继续手工精修）。

不需要 Spatial Analyst 许可（植被覆盖度用 numpy 计算）。
"""
import csv
import datetime
import os

try:
    import arcpy
except ImportError:  # 允许在无 arcpy 的环境中测试纯计算函数
    arcpy = None

try:
    import numpy as np
except ImportError:
    np = None


# =============================================================================
# 一、配置（按项目修改）
# =============================================================================
CONFIG = {
    # "CURRENT" 表示在 Pro 的 Python 窗口中运行；Pro 外运行填 .aprx 完整路径
    "aprx": "CURRENT",
    "out_dir": r"D:\生态图件\输出",
    "project_name": "XX建设项目",
    "eval_level": "三级",            # 一级 / 二级 / 三级（HJ 19—2022 6.1）
    "mapper": "XX环境科技有限公司",   # 制图单位
    # 目标坐标系：None 时按项目中心经度自动选 CGCS2000 3 度带高斯-克吕格
    # （泉州东部多为中央经线 120°E，WKID 4549；安溪、永春、德化等西部多为 117°E，WKID 4548）
    "target_wkid": None,
    "page": "A4竖",                   # A4竖 / A4横 / A3横
    "dpi": 300,

    # ---- 必填 ----
    # 项目占地范围面（永久+临时占地，含施工场地），CGCS2000 或任意已定义坐标系
    "project_boundary": None,
    # 评价范围面；None 时以项目占地外扩 buffer_m 生成。
    # HJ 19—2022 6.2 对一般项目未给固定外扩距离，须按 6.2.1～6.2.8 自行论证后填写
    "eval_range": None,
    "buffer_m": None,

    # ---- 专题数据（无则 None）----
    # field：分类字段；lyrx：可选，标准配色图层文件（如 GB/T 21010 二级类配色）
    "landuse":    {"path": None, "field": "DLMC", "lyrx": None,
                   "source": "XX县第三次全国国土调查成果及现场核查"},
    "vegetation": {"path": None, "field": "植被类型", "lyrx": None,
                   "source": "现场样方调查及遥感解译"},
    "ecosystem":  {"path": None, "field": "II级类型", "lyrx": None,
                   "source": "遥感解译（HJ 1166 分类体系）及现场核查"},
    "water":      {"path": None, "label": "名称",
                   "source": "XX市水系数据"},
    "admin":      {"path": None, "label": "名称",              # 行政区划面，用于地理位置图
                   "source": "XX市行政区划数据"},
    # 生态敏感区：每个敏感区单独成图（附录 D.2），叠加其官方功能分区
    "sensitive": [
        # {"path": r"D:\数据\XX自然保护区功能区.shp", "name": "XX自然保护区",
        #  "field": "功能区", "source": "XX自然保护区总体规划功能区划图"},
    ],
    # 生态保护目标（重要物种点位、古树名木、重要生境等）
    "targets":    {"path": None, "field": "类型", "label": "名称",
                   "source": "现场调查"},
    # 调查样方、样线、点位布设（附录 D 表 D.1 要求注明海拔）
    "samples":    {"path": None, "field": "类型", "label": "编号", "elev": "海拔",
                   "source": "现场调查"},
    "monitor":    {"path": None, "field": "类型", "label": "编号",
                   "source": "生态监测计划"},
    "measures":   {"path": None, "field": "措施类型", "label": None,
                   "source": "生态保护措施设计"},
    # 工作底图（标准地形图，附录 D.2）：.lyrx / 栅格 / 矢量路径，None 则不加
    "basemap": None,

    # ---- 植被覆盖度（附录 C.8.1）----
    # 方式一：已有 NDVI 栅格 {"ndvi": path}
    # 方式二：红/近红外波段 {"red": path, "nir": path}，多波段文件可写 path + r"\Band_4"
    #   Sentinel-2 L2A：red=B4, nir=B8；Landsat 8/9：red=B4, nir=B5
    # scale/offset：反射率换算 ρ = DN*scale + offset（Landsat C2 L2：0.0000275, -0.2；
    #   Sentinel-2 L2A 基线 04.00 起：0.0001, -0.1）。仅比值时 offset 会影响 NDVI，务必填对。
    "ndvi": None,
    "reflectance_scale": 1.0,
    "reflectance_offset": 0.0,
    "image_source": "Sentinel-2 L2A，成像日期 XXXX-XX-XX，分辨率 10 m",
    # NDVIs、NDVIv 取评价范围内 NDVI 累积频率的百分位（经验取值，导则未规定，报告中须说明）
    "ndvi_s_pct": 5,
    "ndvi_v_pct": 95,
    # FVC 分级断点（导则未规定；默认参照 SL 190—2007 林草覆盖度分级 30%/45%/60%/75%，报告中须说明）
    "fvc_breaks": [0.30, 0.45, 0.60, 0.75],
    "fvc_labels": ["低覆盖度(<30%)", "中低覆盖度(30%~45%)", "中覆盖度(45%~60%)",
                   "中高覆盖度(60%~75%)", "高覆盖度(≥75%)"],
}


# =============================================================================
# 二、纯计算函数（无 arcpy 依赖，可单独测试）
# =============================================================================
STANDARD_SCALES = [2000, 5000, 10000, 25000, 50000, 100000, 250000, 500000]

PAGES = {  # 宽, 高 (mm)
    "A4竖": (210, 297),
    "A4横": (297, 210),
    "A3横": (420, 297),
}


def cgcs2000_3deg_wkid(lon):
    """CGCS2000 3 度带高斯-克吕格（不带带号）WKID：中央经线 75°E→4534，每 3° 加 1。"""
    cm = int(round(lon / 3.0)) * 3
    if not 75 <= cm <= 135:
        raise ValueError("经度 %.4f 超出 CGCS2000 3 度带范围" % lon)
    return 4534 + (cm - 75) // 3


def choose_scale(extent_w_m, extent_h_m, frame_w_mm, frame_h_mm, margin=1.08):
    """返回能完整容纳范围的最大标准比例尺分母。"""
    need = max(extent_w_m / frame_w_mm, extent_h_m / frame_h_mm) * 1000.0 * margin
    for s in STANDARD_SCALES:
        if s >= need:
            return s
    return int(round(need, -3))


def fvc_from_ndvi(ndvi, s_pct, v_pct):
    """式 C.5：FVC = (NDVI-NDVIs)/(NDVIv-NDVIs)，NDVIs/NDVIv 取百分位，结果截断到 [0,1]。
    返回 (fvc 数组, NDVIs, NDVIv)，无效像元为 NaN。"""
    valid = np.isfinite(ndvi)
    ns, nv = np.percentile(ndvi[valid], [s_pct, v_pct])
    if nv <= ns:
        raise ValueError("NDVIv(%.4f) 不大于 NDVIs(%.4f)，请检查影像" % (nv, ns))
    fvc = (ndvi - ns) / (nv - ns)
    fvc = np.clip(fvc, 0.0, 1.0)
    fvc[~valid] = np.nan
    return fvc, float(ns), float(nv)


def classify(values, breaks):
    """按断点分级，返回 1..len(breaks)+1 的整数数组，NaN→0。"""
    out = np.digitize(np.nan_to_num(values, nan=-1.0), breaks) + 1
    out[~np.isfinite(values)] = 0
    return out.astype("uint8")


def area_table(rows, total=None):
    """rows: {类型: 面积_m2} → [(类型, 面积hm2, 比例%)]，按面积降序，末行合计。"""
    tot = total if total else sum(rows.values())
    out = []
    for k, a in sorted(rows.items(), key=lambda kv: -kv[1]):
        out.append((k, round(a / 1e4, 4), round(a / tot * 100, 2) if tot else 0.0))
    out.append(("合计", round(sum(rows.values()) / 1e4, 4),
                round(sum(rows.values()) / tot * 100, 2) if tot else 0.0))
    return out


# =============================================================================
# 三、arcpy 处理
# =============================================================================
LOG = []


def log(msg):
    LOG.append(msg)
    print(msg)
    if arcpy:
        arcpy.AddMessage(msg)


def _gdb():
    gdb = os.path.join(CONFIG["out_dir"], "生态制图.gdb")
    if not arcpy.Exists(gdb):
        arcpy.management.CreateFileGDB(CONFIG["out_dir"], "生态制图.gdb")
    return gdb


def _check_fields(path, *fields):
    names = [f.name for f in arcpy.ListFields(path)]
    for f in fields:
        if f and f not in names:
            raise ValueError("%s 中找不到字段“%s”，现有字段：%s" % (path, f, "、".join(names)))


def target_sr():
    if CONFIG["target_wkid"]:
        return arcpy.SpatialReference(CONFIG["target_wkid"])
    ext = arcpy.Describe(CONFIG["project_boundary"]).extent
    cen = arcpy.PointGeometry(
        arcpy.Point((ext.XMin + ext.XMax) / 2, (ext.YMin + ext.YMax) / 2),
        ext.spatialReference).projectAs(arcpy.SpatialReference(4490))
    wkid = cgcs2000_3deg_wkid(cen.firstPoint.X)
    log("项目中心经度 %.4f°E，采用 CGCS2000 3 度带高斯-克吕格 WKID %d" % (cen.firstPoint.X, wkid))
    return arcpy.SpatialReference(wkid)


def to_gdb(src, name, sr):
    """投影到目标坐标系并存入 gdb。"""
    out = os.path.join(_gdb(), name)
    if arcpy.Exists(out):
        arcpy.management.Delete(out)
    if arcpy.Describe(src).spatialReference.name in ("Unknown", ""):
        raise ValueError("%s 未定义坐标系，请先“定义投影”" % src)
    arcpy.management.Project(src, out, sr)
    return out


def clip_to_range(fc, rng, name):
    out = os.path.join(_gdb(), name)
    if arcpy.Exists(out):
        arcpy.management.Delete(out)
    arcpy.analysis.PairwiseClip(fc, rng, out)
    return out


def sum_area(fc, field):
    rows = {}
    with arcpy.da.SearchCursor(fc, [field, "SHAPE@AREA"]) as cur:
        for k, a in cur:
            k = "未分类" if k in (None, "") else str(k)
            rows[k] = rows.get(k, 0.0) + a
    return rows


def write_csv(name, header, rows):
    path = os.path.join(CONFIG["out_dir"], name)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    log("已输出统计表：%s" % path)
    return path


def prepare(sr):
    """项目占地、评价范围入库。"""
    if not CONFIG["project_boundary"]:
        raise ValueError("CONFIG['project_boundary'] 必须填写项目占地范围")
    proj = to_gdb(CONFIG["project_boundary"], "项目占地范围", sr)
    if CONFIG["eval_range"]:
        rng = to_gdb(CONFIG["eval_range"], "评价范围", sr)
    elif CONFIG["buffer_m"]:
        rng = os.path.join(_gdb(), "评价范围")
        if arcpy.Exists(rng):
            arcpy.management.Delete(rng)
        arcpy.analysis.PairwiseBuffer(proj, rng, "%s Meters" % CONFIG["buffer_m"],
                                      dissolve_option="ALL")
        log("评价范围按占地外扩 %s m 生成（须在报告中说明依据）" % CONFIG["buffer_m"])
    else:
        raise ValueError("eval_range 与 buffer_m 至少填一项（HJ 19—2022 6.2）")
    rng_area = sum(r[0] for r in arcpy.da.SearchCursor(rng, ["SHAPE@AREA"]))
    proj_area = sum(r[0] for r in arcpy.da.SearchCursor(proj, ["SHAPE@AREA"]))
    log("评价范围面积 %.4f km²；项目占地面积 %.4f hm²" % (rng_area / 1e6, proj_area / 1e4))
    return proj, rng, rng_area


def theme_stats(key, label, proj, rng, rng_area, sr):
    """专题数据裁剪 + 评价范围内面积统计 + 工程占用叠置统计（图形叠置法，8.2.1 a/d）。"""
    cfg = CONFIG.get(key)
    if not cfg or not cfg.get("path"):
        return None
    _check_fields(cfg["path"], cfg["field"])
    fc = clip_to_range(to_gdb(cfg["path"], key + "_原始", sr), rng, label)
    write_csv("%s_评价范围面积统计.csv" % label, ["类型", "面积(hm²)", "占评价范围比例(%)"],
              area_table(sum_area(fc, cfg["field"]), rng_area))
    occ = os.path.join(_gdb(), label + "_工程占用")
    if arcpy.Exists(occ):
        arcpy.management.Delete(occ)
    arcpy.analysis.PairwiseIntersect([fc, proj], occ)
    write_csv("%s_工程占用面积统计.csv" % label, ["类型", "占用面积(hm²)", "占工程占地比例(%)"],
              area_table(sum_area(occ, cfg["field"])))
    return fc


def fvc_raster(rng, sr):
    """植被覆盖度（附录 C.8.1，式 C.5），numpy 实现，不需要 Spatial Analyst。"""
    cfg = CONFIG.get("ndvi")
    if not cfg:
        return None, None
    gdb = _gdb()

    def read(path):
        r = arcpy.Raster(path)
        a = arcpy.RasterToNumPyArray(r).astype("float64")
        if r.noDataValue is not None:
            a[a == r.noDataValue] = np.nan
        return a

    def clip(src, name):
        out = os.path.join(gdb, name)
        if arcpy.Exists(out):
            arcpy.management.Delete(out)
        prj = out + "_prj"
        if arcpy.Exists(prj):
            arcpy.management.Delete(prj)
        arcpy.management.ProjectRaster(src, prj, sr, "BILINEAR")
        arcpy.management.Clip(prj, "#", out, rng, "#", "ClippingGeometry")
        arcpy.management.Delete(prj)
        return out

    if cfg.get("ndvi"):
        base = clip(cfg["ndvi"], "NDVI")
        ndvi = read(base)
    else:
        base = clip(cfg["red"], "B_red")
        with arcpy.EnvManager(snapRaster=base, cellSize=base, extent=base):
            nir_r = clip(cfg["nir"], "B_nir")
        k, b = CONFIG["reflectance_scale"], CONFIG["reflectance_offset"]
        red = read(base) * k + b
        nir = read(nir_r) * k + b
        if red.shape != nir.shape:
            raise ValueError("红、近红外波段裁剪后行列数不一致 %s / %s，请先重采样到同一格网"
                             % (red.shape, nir.shape))
        with np.errstate(divide="ignore", invalid="ignore"):
            ndvi = (nir - red) / (nir + red)
        ndvi[~np.isfinite(ndvi)] = np.nan

    fvc, ns, nv = fvc_from_ndvi(ndvi, CONFIG["ndvi_s_pct"], CONFIG["ndvi_v_pct"])
    grade = classify(fvc, CONFIG["fvc_breaks"])

    d = arcpy.Describe(base)
    ll = arcpy.Point(d.extent.XMin, d.extent.YMin)
    cw, chh = d.meanCellWidth, d.meanCellHeight
    out_fvc = os.path.join(gdb, "植被覆盖度")
    out_grd = os.path.join(gdb, "植被覆盖度分级")
    for p in (out_fvc, out_grd):
        if arcpy.Exists(p):
            arcpy.management.Delete(p)
    r1 = arcpy.NumPyArrayToRaster(fvc.astype("float32"), ll, cw, chh, np.nan)
    r1.save(out_fvc)
    r2 = arcpy.NumPyArrayToRaster(grade, ll, cw, chh, 0)
    r2.save(out_grd)
    for p in (out_fvc, out_grd):
        arcpy.management.DefineProjection(p, sr)
    arcpy.management.BuildRasterAttributeTable(out_grd, "Overwrite")
    arcpy.management.AddField(out_grd, "等级", "TEXT", field_length=40)
    labels = CONFIG["fvc_labels"]
    with arcpy.da.UpdateCursor(out_grd, ["Value", "等级"]) as cur:
        for v, _ in cur:
            cur.updateRow([v, labels[v - 1] if 1 <= v <= len(labels) else "无数据"])

    cell = cw * chh
    rows = {labels[i - 1]: float((grade == i).sum()) * cell for i in range(1, len(labels) + 1)}
    tab = area_table(rows)
    tab.append(("参数", "NDVIs=%.4f" % ns, "NDVIv=%.4f" % nv))
    tab.append(("平均植被覆盖度", "%.4f" % float(np.nanmean(fvc)), ""))
    write_csv("植被覆盖度分级面积统计.csv", ["等级", "面积(hm²)", "比例(%)"], tab)
    log("植被覆盖度：NDVIs=%.4f（%s%% 分位），NDVIv=%.4f（%s%% 分位），平均 FVC=%.4f"
        % (ns, CONFIG["ndvi_s_pct"], nv, CONFIG["ndvi_v_pct"], float(np.nanmean(fvc))))
    return out_fvc, out_grd


# =============================================================================
# 四、地图与布局（附录 D.3：图名、图例、比例尺、方向标、注记、制图数据源、成图时间）
# =============================================================================
class Mapper(object):
    def __init__(self, sr):
        self.aprx = arcpy.mp.ArcGISProject(CONFIG["aprx"])
        self.sr = sr
        self.W, self.H = PAGES[CONFIG["page"]]
        self.today = datetime.date.today().strftime("%Y年%m月")
        self.outputs = []

    # ---------- 图层符号 ----------
    def _outline(self, lyr, rgb, width, fill=None):
        sym = lyr.symbology
        if hasattr(sym, "renderer"):
            sym.updateRenderer("SimpleRenderer")
            s = sym.renderer.symbol
            s.color = {"RGB": fill if fill else [0, 0, 0, 0]}
            s.outlineColor = {"RGB": rgb + [100]}
            s.outlineWidth = width
            lyr.symbology = sym

    def _unique(self, lyr, field, lyrx=None, ramp="Basic Random"):
        if lyrx:
            arcpy.management.ApplySymbologyFromLayer(lyr, lyrx)
            return
        sym = lyr.symbology
        if hasattr(sym, "renderer"):
            sym.updateRenderer("UniqueValueRenderer")
            sym.renderer.fields = [field]
            ramps = self.aprx.listColorRamps(ramp)
            if ramps:
                sym.renderer.colorRamp = ramps[0]
            lyr.symbology = sym

    def _label(self, lyr, field):
        if not field:
            return
        lc = lyr.listLabelClasses()
        if lc:
            lc[0].expression = '$feature["%s"]' % field
            lyr.showLabels = True

    # ---------- 地图 ----------
    def new_map(self, name):
        for m in self.aprx.listMaps(name):
            self.aprx.deleteItem(m)
        m = self.aprx.createMap(name, "MAP")
        m.spatialReference = self.sr
        for lyr in m.listLayers():  # 去掉默认在线底图
            m.removeLayer(lyr)
        return m

    def add(self, m, path, kind="unique", field=None, label=None, lyrx=None,
            rgb=None, width=1.5, fill=None):
        lyr = m.addDataFromPath(path)
        if kind == "unique":
            self._unique(lyr, field, lyrx)
        elif kind == "outline":
            self._outline(lyr, rgb, width, fill)
        self._label(lyr, label)
        return lyr

    def base_layers(self, m, proj, rng, with_range=True):
        """所有图件统一叠加：工作底图、评价范围、项目占地。图层自上而下添加顺序与显示相反。"""
        if CONFIG["basemap"]:
            m.addDataFromPath(CONFIG["basemap"])
        if with_range:
            self.add(m, rng, "outline", rgb=[0, 112, 255], width=2)
        self.add(m, proj, "outline", rgb=[255, 0, 0], width=2)

    # ---------- 布局 ----------
    def layout(self, m, title, extent_fc, sources, legend=True, scale=None):
        W, H = self.W, self.H
        for l in self.aprx.listLayouts(title):
            self.aprx.deleteItem(l)
        lyt = self.aprx.createLayout(W, H, "MILLIMETER", title)
        mg, bottom, top = 10.0, 48.0, H - 22.0
        mf = lyt.createMapFrame(arcpy.Extent(mg, bottom, W - mg, top), m, "主图")
        ext = arcpy.Describe(extent_fc).extent
        mf.camera.setExtent(ext)
        s = scale or choose_scale(ext.width, ext.height, W - 2 * mg, top - bottom)
        mf.camera.scale = s
        if s > 50000 and not scale:
            log("提示：《%s》需 1:%d 才能完整显示，超过附录 D.2“一般在 1:50000 以上”，"
                "建议分幅成图或复核底图精度" % (title, s))

        t = self.aprx.createTextElement(lyt, arcpy.Point(W / 2, H - 14), "POINT",
                                        "%s%s" % (CONFIG["project_name"], title),
                                        18, "SimHei", "Regular", "图名")
        t.elementPositionX = (W - t.elementWidth) / 2

        na = self.aprx.listStyleItems("ArcGIS 2D", "North_Arrow", "ArcGIS North 1")
        if na:
            lyt.createMapSurroundElement(arcpy.Point(W - mg - 14, top - 22), "North_Arrow",
                                         mf, na[0], "指北针")
        sb = self.aprx.listStyleItems("ArcGIS 2D", "Scale_Bar", "Alternating Scale Bar 1")
        if sb:
            lyt.createMapSurroundElement(arcpy.Extent(W / 2 + 5, 34, W - mg, 44), "Scale_Bar",
                                         mf, sb[0], "比例尺")
        self.aprx.createTextElement(lyt, arcpy.Point(W / 2 + 5, 30), "POINT",
                                    "比例尺 1:%d" % s, 9, "SimSun", "Regular", "数字比例尺")
        if legend:
            lg = self.aprx.listStyleItems("ArcGIS 2D", "Legend", "Legend 1")
            if lg:
                le = lyt.createMapSurroundElement(arcpy.Extent(mg, 6, W / 2 - 2, bottom - 2),
                                                  "Legend", mf, lg[0], "图例")
                le.title = "图  例"
        note = "坐标系：%s\n制图数据源：%s\n制图单位：%s    成图时间：%s" % (
            self.sr.name, "；".join(x for x in sources if x), CONFIG["mapper"], self.today)
        ne = self.aprx.createTextElement(lyt, arcpy.Point(W / 2 + 5, 24), "POINT", note,
                                         7, "SimSun", "Regular", "注记")
        ne.elementPositionY = 6

        base = os.path.join(CONFIG["out_dir"], title)
        lyt.exportToPDF(base + ".pdf", resolution=CONFIG["dpi"])
        lyt.exportToJPEG(base + ".jpg", resolution=CONFIG["dpi"])
        self.outputs.append(base + ".pdf")
        log("已出图：%s（1:%d）" % (base + ".pdf", s))
        return lyt


# =============================================================================
# 五、主流程
# =============================================================================
def run_all():
    if arcpy is None or np is None:
        raise RuntimeError("请在 ArcGIS Pro 的 Python 环境中运行")
    ver = arcpy.GetInstallInfo().get("Version", "0")
    if int(ver.split(".")[0]) < 3:
        raise RuntimeError("需要 ArcGIS Pro 3.0 及以上（当前 %s），布局元素创建 API 自 3.0 起提供" % ver)
    os.makedirs(CONFIG["out_dir"], exist_ok=True)
    arcpy.env.overwriteOutput = True

    sr = target_sr()
    proj, rng, rng_area = prepare(sr)
    M = Mapper(sr)
    level = CONFIG["eval_level"]
    hi = level in ("一级", "二级")

    # 1. 项目地理位置图（表 D.1）
    if CONFIG["admin"]["path"]:
        adm = to_gdb(CONFIG["admin"]["path"], "行政区划", sr)
        m = M.new_map("项目地理位置图")
        M.add(m, adm, "outline", label=CONFIG["admin"]["label"], rgb=[110, 110, 110],
              width=1, fill=[245, 240, 225, 100])
        M.base_layers(m, proj, rng, with_range=False)
        M.layout(m, "项目地理位置图", adm, [CONFIG["admin"]["source"]], legend=True)

    # 2. 地表水系图（表 D.1）
    if CONFIG["water"]["path"]:
        wat = to_gdb(CONFIG["water"]["path"], "水系", sr)
        m = M.new_map("地表水系图")
        M.add(m, wat, kind=None, label=CONFIG["water"]["label"])
        M.base_layers(m, proj, rng)
        M.layout(m, "地表水系图", rng, [CONFIG["water"]["source"]])

    # 3. 土地利用现状图、植被类型图、生态系统类型图 + 面积统计 + 工程占用叠置统计
    themes = [("landuse", "土地利用现状图", True),
              ("vegetation", "植被类型图", True),
              ("ecosystem", "生态系统类型图", hi)]
    for key, title, need in themes:
        cfg = CONFIG[key]
        if not cfg["path"]:
            if need:
                log("缺少数据，未生成《%s》（%s评价应编制）" % (title, level))
            continue
        fc = theme_stats(key, title.replace("图", ""), proj, rng, rng_area, sr)
        m = M.new_map(title)
        M.add(m, fc, "unique", field=cfg["field"], lyrx=cfg.get("lyrx"))
        M.base_layers(m, proj, rng)
        M.layout(m, title, rng, [cfg["source"]])

    # 4. 植被覆盖度空间分布图（7.4.1 a；附录 C.8.1）
    if CONFIG["ndvi"]:
        _, grd = fvc_raster(rng, sr)
        m = M.new_map("植被覆盖度空间分布图")
        lyr = m.addDataFromPath(grd)
        sym = lyr.symbology
        if hasattr(sym, "colorizer"):
            sym.updateColorizer("RasterUniqueValueColorizer")
            sym.colorizer.field = "等级"
            ramps = M.aprx.listColorRamps("Yellow-Green (5 Classes)") or M.aprx.listColorRamps("Greens*")
            if ramps:
                sym.colorizer.colorRamp = ramps[0]
            lyr.symbology = sym
        M.base_layers(m, proj, rng)
        M.layout(m, "植被覆盖度空间分布图", rng,
                 [CONFIG["image_source"], "NDVI 像元二分模型（HJ 19—2022 式 C.5）"])
    elif hi:
        log("缺少遥感数据，未生成《植被覆盖度空间分布图》（%s评价 7.4.1 a 可编制）" % level)

    # 5. 生态保护目标空间分布图（表 D.1：不同保护目标分别成图）
    if CONFIG["targets"]["path"]:
        tg = to_gdb(CONFIG["targets"]["path"], "生态保护目标", sr)
        m = M.new_map("生态保护目标空间分布图")
        M.add(m, tg, "unique", field=CONFIG["targets"]["field"], label=CONFIG["targets"]["label"])
        M.base_layers(m, proj, rng)
        M.layout(m, "生态保护目标空间分布图", rng, [CONFIG["targets"]["source"]])

    # 6. 生态敏感区分布图：每个敏感区单独成图，叠加官方功能分区（附录 D.2、表 D.1）
    for i, s in enumerate(CONFIG["sensitive"]):
        _check_fields(s["path"], s.get("field"))
        fc = to_gdb(s["path"], "敏感区_%d" % (i + 1), sr)
        title = "项目与%s位置关系图" % s["name"]
        m = M.new_map(title)
        M.add(m, fc, "unique", field=s.get("field"), lyrx=s.get("lyrx"))
        M.base_layers(m, proj, rng)
        merged = os.path.join(_gdb(), "敏感区_%d_范围" % (i + 1))
        arcpy.management.Merge([fc, proj], merged)
        M.layout(m, title, merged, [s.get("source", "")])

    # 7. 调查样方、样线、点位布设图；8. 生态监测布点图；9. 生态保护措施平面布置图
    #    （附录 D.2：一般 1:10000～1:2000）
    for key, title in (("samples", "调查样方样线布设图"),
                       ("monitor", "生态监测布点图"),
                       ("measures", "生态保护措施平面布置图")):
        cfg = CONFIG[key]
        if not cfg["path"]:
            if key == "samples" and hi:
                log("缺少数据，未生成《%s》（%s评价 7.3.4 要求样方/样线调查）" % (title, level))
            if key == "measures":
                log("缺少数据，未生成《生态保护措施平面布置图》（9.1.1 要求编制）")
            continue
        fc = to_gdb(cfg["path"], title, sr)
        label = cfg.get("label")
        if key == "samples" and cfg.get("elev"):
            _check_fields(fc, cfg["elev"])
            expr = ("str(!%s!) + ' (' + str(!%s!) + 'm)'" % (label, cfg["elev"]) if label
                    else "str(!%s!) + 'm'" % cfg["elev"])
            arcpy.management.CalculateField(fc, "标注", expr, "PYTHON3", field_type="TEXT")
            label = "标注"
        m = M.new_map(title)
        M.add(m, fc, "unique", field=cfg["field"], label=label)
        M.base_layers(m, proj, rng)
        ext_fc = rng if key != "measures" else proj
        s = None
        if key == "measures":  # 措施图按 1:10000～1:2000 取比例尺
            e = arcpy.Describe(ext_fc).extent
            s = min(max(choose_scale(e.width, e.height, M.W - 20, M.H - 70), 2000), 10000)
        M.layout(m, title, ext_fc, [cfg["source"]], scale=s)

    if CONFIG["aprx"] != "CURRENT":
        M.aprx.save()
    log("完成，共输出 %d 幅图件，目录：%s" % (len(M.outputs), CONFIG["out_dir"]))
    with open(os.path.join(CONFIG["out_dir"], "制图日志.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(LOG))
    return M.outputs


if __name__ == "__main__":
    if CONFIG["project_boundary"]:
        run_all()
    else:
        print("请先在 CONFIG 中填写 project_boundary 等数据路径，再重新运行。")
