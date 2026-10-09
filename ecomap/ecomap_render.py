# -*- coding: utf-8 -*-
"""图件绘制：按 HJ 19—2022 附录 D.3 加主图、图名、图例、比例尺、方向标、注记、
制图数据源、成图时间，另加公里网与图廓。仅用 matplotlib（不经 pyplot 窗口）。"""
import colorsys
import hashlib
import math
import os

import matplotlib

matplotlib.use("Agg")
from matplotlib import font_manager  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Polygon as MPoly, Rectangle  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
import matplotlib.patheffects as pe  # noqa: E402
import numpy as np  # noqa: E402

import ecomap_core as C  # noqa: E402

CJK_CANDIDATES = ["SimHei", "Microsoft YaHei", "SimSun", "DengXian", "Noto Sans CJK SC", "Source Han Sans SC",
                  "WenQuanYi Zen Hei", "WenQuanYi Micro Hei", "PingFang SC"]


def setup_fonts():
    have = {f.name for f in font_manager.fontManager.ttflist}
    found = [n for n in CJK_CANDIDATES if n in have]
    matplotlib.rcParams["font.sans-serif"] = found + ["DejaVu Sans"]
    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["axes.unicode_minus"] = False
    matplotlib.rcParams["pdf.fonttype"] = 42
    return found


FONTS = setup_fonts()

# 参考配色（按类别名称关键词，非 TD/T 1055 等标准规定色值；可在界面中逐类修改）
KEYWORD_COLORS = [
    (("水田",), "#c9e4a6"), (("水浇地",), "#e6e69a"), (("旱地", "耕地"), "#f6e9a5"),
    (("果园", "茶园", "园地", "橡胶", "经济林"), "#f0c27a"),
    (("竹",), "#7fbf6a"), (("灌木林", "灌丛"), "#8fc98a"),
    (("针叶", "马尾松", "杉木", "松林"), "#2f7d4f"), (("阔叶", "常绿"), "#3e9a5a"),
    (("乔木林", "有林地", "林地", "森林"), "#3a8f55"),
    (("草地", "草丛", "草本", "草"), "#bfe0a0"),
    (("湿地", "沼泽", "滩涂", "红树"), "#7fd0c8"),
    (("河流", "水库", "湖泊", "坑塘", "沟渠", "水面", "水域", "水体"), "#8ec5ec"),
    (("农田", "农业"), "#f3e39a"),
    (("交通", "公路", "铁路", "道路", "农村道路"), "#b0b0b0"),
    (("城镇", "村庄", "住宅", "建设", "工业", "工矿", "商服", "公共", "聚落", "建筑", "人工表面"), "#e7a39c"),
    (("裸", "未利用", "沙地", "裸岩", "裸土"), "#d9c7a7"),
]
STYLE = {
    "project": dict(edge="#e60000", lw=1.6, ls="-", label="项目占地范围"),
    "eval_range": dict(edge="#000000", lw=1.2, ls=(0, (6, 3)), label="评价范围"),
}
FVC_COLORS = ["#d7a86e", "#f1e48a", "#b8de7a", "#5fb85a", "#1d7a3a"]
POINT_MARKERS = ["o", "^", "s", "D", "v", "P", "*", "X", "h", "p"]
SENS_LS = ["-", (0, (8, 3)), (0, (4, 2, 1, 2)), (0, (1, 2)), (0, (10, 2, 2, 2, 2, 2))]
SENS_COLORS = ["#008040", "#8000ff", "#ff7f00", "#0060c0", "#c00060"]
POINT_COLORS = ["#e41a1c", "#ff7f00", "#4daf4a", "#984ea3", "#a65628", "#f781bf", "#666666", "#000000", "#e6ab02"]
ZONE_COLORS = ["#1b7837", "#5aae61", "#a6dba0", "#d9f0d3", "#c2a5cf", "#9970ab", "#fee08b", "#fdae61"]


def auto_color(name, i):
    s = str(name)
    for kws, c in KEYWORD_COLORS:
        if any(k in s for k in kws):
            # 同组多类时略调明度，便于区分
            h = int(hashlib.md5(s.encode("utf-8")).hexdigest()[:4], 16) / 65535.0
            r, g, b = matplotlib.colors.to_rgb(c)
            hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
            ll = min(0.92, max(0.18, ll + (h - 0.5) * 0.16))
            return matplotlib.colors.to_hex(colorsys.hls_to_rgb(hh, ll, ss))
    pal = matplotlib.colormaps["tab20"].colors
    return matplotlib.colors.to_hex(pal[i % 20])


def category_colors(cfg, key, cats):
    user = (cfg.get("colors") or {}).get(key, {})
    return {c: user.get(str(c)) or auto_color(c, i) for i, c in enumerate(cats)}


# ------------------------------------------------------------ 版式
def page_layout(page, legend_h=24.0):
    W, H = C.PAGES[page]
    m = 12.0                       # 外图廓边距
    title_h = 18.0
    foot_h = 13.0
    frame = (m + 4, m + foot_h + legend_h, W - 2 * m - 8, H - 2 * m - title_h - legend_h - foot_h - 4)
    return dict(W=W, H=H, m=m, frame=frame, title_y=H - m - title_h / 2 - 1,
                legend=(m + 4, m + foot_h, W - 2 * m - 8, legend_h - 3), foot=(m + 4, m + 2, W - 2 * m - 8, foot_h - 3))


def fill_scale(extent_w_m, extent_h_m, frame_w_mm, frame_h_mm, margin=1.06):
    """充满图幅：比例尺分母圆整到 1、1.2、1.5、2、2.5、3、4、5、6、7.5、8×10^n。"""
    need = max(extent_w_m / frame_w_mm, extent_h_m / frame_h_mm) * 1000.0 * margin
    p = 10 ** math.floor(math.log10(need))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 7.5, 8, 10):
        if m * p >= need:
            return int(round(m * p))
    return int(round(10 * p))


def _mm(fig_w, fig_h, x, y, w, h):
    return [x / fig_w, y / fig_h, w / fig_w, h / fig_h]


def _bounds_of(geom_list):
    xs0, ys0, xs1, ys1 = [], [], [], []
    for g in geom_list:
        if g is None or g.is_empty:
            continue
        b = g.bounds
        xs0.append(b[0]); ys0.append(b[1]); xs1.append(b[2]); ys1.append(b[3])
    return min(xs0), min(ys0), max(xs1), max(ys1)


def _km_ticks(lo, hi, n_target=5):
    span = hi - lo
    step = C.nice_bar_length(span, 1.0 / n_target) if span > 0 else 1000
    start = math.ceil(lo / step) * step
    return np.arange(start, hi, step), step


class MapCanvas:
    """一幅图：负责比例尺定框、绘图辅助要素。"""

    def __init__(self, ctx, title, bounds, max_scale=None, subtitle=None, fill=False):
        cfg = ctx.cfg
        self.ctx, self.cfg, self.title = ctx, cfg, title
        self.max_scale, self.fill = max_scale, fill or cfg.get("scale_mode") == "充满图幅"
        b = list(bounds)
        for i in (0, 1):
            if b[i + 2] - b[i] < 50.0:
                c = (b[i] + b[i + 2]) / 2
                b[i], b[i + 2] = c - 25.0, c + 25.0
        self.bounds = tuple(b)
        W, H = C.PAGES[cfg["page"]]
        self.fig = Figure(figsize=(W / 25.4, H / 25.4))
        self.ax = self.fig.add_axes([0.1, 0.1, 0.8, 0.8])
        self.ax.set_aspect("auto")
        self.ax.set_facecolor("white")
        self._set_frame(24.0)
        self.legend = []        # (handle, label)
        self.sources = []
        self.subtitle = subtitle

    def _set_frame(self, legend_h):
        """按图例区高度布置主图框，取比例尺并设定地图范围（保持中心）。"""
        L = page_layout(self.cfg["page"], legend_h)
        self.L = L
        W, H = L["W"], L["H"]
        fx, fy, fw, fh = L["frame"]
        b = self.bounds
        bw, bh = b[2] - b[0], b[3] - b[1]
        self.scale = (fill_scale if self.fill else C.choose_scale)(bw, bh, fw, fh)
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        gw, gh = fw * self.scale / 1000.0, fh * self.scale / 1000.0
        self.ext = (cx - gw / 2, cx + gw / 2, cy - gh / 2, cy + gh / 2)
        self.ax.set_position(_mm(W, H, fx, fy, fw, fh))
        self.ax.set_xlim(self.ext[0], self.ext[1])
        self.ax.set_ylim(self.ext[2], self.ext[3])

    def _scale_warnings(self):
        w = []
        if self.max_scale and self.scale > self.max_scale:
            w.append("比例尺 1:%d 小于 D.2 要求（一般 1:10000～1:2000），建议分幅成图" % self.scale)
        if self.scale > 50000 and not self.max_scale and self.title != "项目地理位置图":
            w.append("比例尺 1:%d 小于 1:50000（D.2），成图范围过大时可分幅成图" % self.scale)
        return w

    # -------- 图层
    def add_source(self, s):
        s = (s or "").strip()
        if s and s not in self.sources:
            self.sources.append(s)

    def image(self, arr, extent, **kw):
        self.ax.imshow(arr, extent=extent, origin="upper", interpolation="nearest", zorder=1, **kw)
        self.ax.set_xlim(self.ext[0], self.ext[1])
        self.ax.set_ylim(self.ext[2], self.ext[3])
        self.ax.set_aspect("auto")

    def categories(self, gdf, field, key, edge="#707070"):
        cats = sorted(gdf[field].astype(str).unique(), key=lambda s: (len(s) > 8, s))
        colors = category_colors(self.cfg, key, cats)
        for c in cats:
            sub = gdf[gdf[field].astype(str) == c]
            self._plot(sub, facecolor=colors[c], edgecolor=edge, linewidth=0.25, zorder=2)
            self.legend.append((Patch(facecolor=colors[c], edgecolor=edge, linewidth=0.4), c))
        return colors

    def _plot(self, gdf, zorder=2, **kw):
        if gdf is None or gdf.empty:
            return
        polys = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])]
        lines = gdf[gdf.geom_type.isin(["LineString", "MultiLineString"])]
        pts = gdf[gdf.geom_type.isin(["Point", "MultiPoint"])]
        if not polys.empty:
            polys.plot(ax=self.ax, zorder=zorder, **kw)
        if not lines.empty:
            lk = {k: v for k, v in kw.items() if k in ("linewidth", "linestyle")}
            lines.plot(ax=self.ax, zorder=zorder + 0.5, color=kw.get("edgecolor") or kw.get("facecolor"), **lk)
        if not pts.empty:
            pts.plot(ax=self.ax, zorder=zorder + 1, color=kw.get("facecolor") or kw.get("edgecolor"), markersize=18)

    def outline(self, gdf, key=None, edge="#000", lw=1.0, ls="-", label=None, zorder=6):
        if gdf is None or gdf.empty:
            return
        st = STYLE.get(key, {})
        edge, lw, ls = st.get("edge", edge), st.get("lw", lw), st.get("ls", ls)
        label = label or st.get("label")
        gdf.boundary.plot(ax=self.ax, color=edge, linewidth=lw, linestyle=ls, zorder=zorder)
        if label:
            self.legend.append((Line2D([0], [0], color=edge, lw=lw, ls=ls), label))

    def water(self, gdf, label_field=None, legend=True):
        if gdf is None or gdf.empty:
            return
        polys = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])]
        lines = gdf[gdf.geom_type.isin(["LineString", "MultiLineString"])]
        if not polys.empty:
            polys.plot(ax=self.ax, facecolor="#a9d4f5", edgecolor="#3a87c8", linewidth=0.5, zorder=3)
            if legend:
                self.legend.append((Patch(facecolor="#a9d4f5", edgecolor="#3a87c8"), "水域"))
        if not lines.empty:
            lines.plot(ax=self.ax, color="#2b7bd0", linewidth=1.0, zorder=3)
            if legend:
                self.legend.append((Line2D([0], [0], color="#2b7bd0", lw=1.0), "河流、沟渠"))
        if label_field:
            self.labels(gdf, label_field, color="#1b5fa8", style="italic")

    def points(self, gdf, field, key, label_field=None, elev_field=None):
        if gdf is None or gdf.empty:
            return
        if field:
            cats = sorted(gdf[field].astype(str).unique())
        else:
            cats = [C.SLOT_NAMES.get(key, key)]
        colors = category_colors(self.cfg, key, cats)
        for i, c in enumerate(cats):
            sub = gdf if not field else gdf[gdf[field].astype(str) == c]
            col = colors[c] if (self.cfg.get("colors") or {}).get(key, {}).get(c) else \
                POINT_COLORS[i % len(POINT_COLORS)]
            pts = sub[sub.geom_type.isin(["Point", "MultiPoint"])]
            lines = sub[sub.geom_type.isin(["LineString", "MultiLineString"])]
            polys = sub[sub.geom_type.isin(["Polygon", "MultiPolygon"])]
            mk = POINT_MARKERS[i % len(POINT_MARKERS)]
            if not polys.empty:
                polys.plot(ax=self.ax, facecolor=col, alpha=0.45, edgecolor=col, linewidth=1.0, zorder=7)
                self.legend.append((Patch(facecolor=col, alpha=0.45, edgecolor=col), c))
            if not lines.empty:
                lines.plot(ax=self.ax, color=col, linewidth=1.8, zorder=7)
                self.legend.append((Line2D([0], [0], color=col, lw=1.8), c))
            if not pts.empty:
                pts.plot(ax=self.ax, color=col, marker=mk, markersize=34, edgecolor="black", linewidth=0.5, zorder=8)
                self.legend.append((Line2D([0], [0], marker=mk, color="w", markerfacecolor=col,
                                           markeredgecolor="black", markersize=7, lw=0), c))
        if label_field or elev_field:
            def fmt(r):
                s = str(r[label_field]) if label_field else ""
                if elev_field and r[elev_field] == r[elev_field]:
                    try:
                        s += "（海拔 %g m）" % float(r[elev_field])
                    except (TypeError, ValueError):
                        s += "（海拔 %s）" % r[elev_field]
                return s
            self.labels(gdf, None, fmt=fmt)

    def labels(self, gdf, field, fmt=None, color="black", size=6.5, style="normal"):
        x0, x1, y0, y1 = self.ext
        for _, r in gdf.iterrows():
            g = r.geometry
            if g is None or g.is_empty:
                continue
            txt = fmt(r) if fmt else r[field]
            if txt is None or str(txt).strip() in ("", "nan", "None"):
                continue
            if g.geom_type in ("LineString", "MultiLineString"):
                p = g.interpolate(0.5, normalized=True)
            else:
                p = g.representative_point()
            if not (x0 < p.x < x1 and y0 < p.y < y1):
                continue
            dx = 0 if g.geom_type not in ("Point", "MultiPoint") else (x1 - x0) * 0.008
            self.ax.text(p.x + dx, p.y + dx, str(txt), fontsize=size, color=color, style=style, zorder=12, clip_on=True,
                         path_effects=[pe.withStroke(linewidth=2, foreground="white")])

    def standard_overlays(self, water=True):
        ctx, L = self.ctx, self.cfg["layers"]
        if water and "water" in ctx.layers:
            self.water(C.clip(ctx.layers["water"], _box(self.ext)), L["water"].get("label"), legend=True)
            self.add_source(L["water"].get("source"))
        self.outline(ctx.layers["eval_range"], "eval_range")
        self.outline(ctx.layers["project"], "project")
        self.add_source(L["project"].get("source"))

    # -------- 辅助要素
    def finish(self):
        seen, items = set(), []
        for hd, lb in self.legend:
            if lb not in seen:
                seen.add(lb)
                items.append((hd, lb))
        self.items = items
        W = C.PAGES[self.cfg["page"]][0]
        maxlen = max([len(lb) for _, lb in items] or [4])
        col_w = min(W - 40, 14 + maxlen * 2.6)
        ncol = max(1, int((W - 2 * 12 - 8 - 22) // col_w))
        rows = math.ceil(len(items) / ncol) if items else 1
        self._set_frame(min(70.0, max(16.0, rows * 4.3 + 7)))
        self.warn = self._scale_warnings()
        self.ncol = ncol
        L, ax, fig = self.L, self.ax, self.fig
        W, H = L["W"], L["H"]
        # 公里网
        x0, x1, y0, y1 = self.ext
        xt, step = _km_ticks(x0, x1)
        yt = np.arange(math.ceil(y0 / step) * step, y1, step)
        ax.set_xticks(xt)
        ax.set_yticks(yt)
        unit = 1000.0
        def lab(v):
            return ("%.3f" % (v / unit)).rstrip("0").rstrip(".")
        ax.set_xticklabels([lab(v) for v in xt], fontsize=6)
        ax.set_yticklabels([lab(v) for v in yt], fontsize=6, rotation=90, va="center")
        ax.tick_params(direction="in", length=3, top=True, right=True, labeltop=True, labelright=True)
        ax.grid(True, color="#888888", linewidth=0.3, linestyle=(0, (2, 3)), zorder=0.5)
        ax.set_axisbelow(False)
        for s in ax.spines.values():
            s.set_linewidth(0.8)
            s.set_zorder(20)
        ax.text(1.0, -0.035, "公里网（km）", transform=ax.transAxes, fontsize=5.5, ha="right", va="top")
        # 外图廓
        m = L["m"]
        fig.patches.append(Rectangle((m / W, m / H), 1 - 2 * m / W, 1 - 2 * m / H, transform=fig.transFigure,
                                     fill=False, linewidth=1.6, edgecolor="black"))
        fig.patches.append(Rectangle(((m + 1.2) / W, (m + 1.2) / H), 1 - 2 * (m + 1.2) / W, 1 - 2 * (m + 1.2) / H,
                                     transform=fig.transFigure, fill=False, linewidth=0.4, edgecolor="black"))
        # 图名
        fig.text(0.5, L["title_y"] / H, self.title, ha="center", va="center", fontsize=16, weight="bold")
        if self.subtitle:
            fig.text(0.5, (L["title_y"] - 6.5) / H, self.subtitle, ha="center", va="center", fontsize=8.5)
        self._north()
        self._scalebar()
        self._legend()
        self._footer()

    def _north(self):
        ax = self.ax
        x, y, h = 0.94, 0.86, 0.09
        tri_l = MPoly([[x, y + h], [x - 0.022, y], [x, y + h * 0.28]], closed=True, transform=ax.transAxes,
                      facecolor="black", edgecolor="black", lw=0.6, zorder=15)
        tri_r = MPoly([[x, y + h], [x + 0.022, y], [x, y + h * 0.28]], closed=True, transform=ax.transAxes,
                      facecolor="white", edgecolor="black", lw=0.6, zorder=15)
        ax.add_patch(tri_l)
        ax.add_patch(tri_r)
        ax.text(x, y + h + 0.012, "N", transform=ax.transAxes, ha="center", va="bottom", fontsize=11,
                weight="bold", zorder=15, path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])

    def _scalebar(self):
        ax = self.ax
        x0, x1, y0, y1 = self.ext
        gw = x1 - x0
        total = C.nice_bar_length(gw, 0.25)
        seg = total / 4.0
        bx = x0 + gw * 0.04
        by = y0 + (y1 - y0) * 0.05
        hh = (y1 - y0) * 0.008
        ax.add_patch(Rectangle((bx - gw * 0.015, by - hh * 3.8), total + gw * 0.05, hh * 9.0, facecolor="white",
                               edgecolor="#555", lw=0.4, alpha=0.9, zorder=14))
        for i in range(4):
            ax.add_patch(Rectangle((bx + i * seg, by), seg, hh, facecolor="black" if i % 2 == 0 else "white",
                                   edgecolor="black", lw=0.5, zorder=15))
        use_km = total >= 1000
        for i in (0, 2, 4):
            v = seg * i
            s = ("%g" % (v / 1000.0)) if use_km else ("%g" % v)
            ax.text(bx + v, by + hh * 1.6, s, ha="center", va="bottom", fontsize=6, zorder=16)
        ax.text(bx + total + gw * 0.006, by + hh * 0.5, "km" if use_km else "m", ha="left", va="center", fontsize=6,
                zorder=16)
        ax.text(bx + total / 2, by - hh * 1.2, "1:%s" % format(self.scale, ",").replace(",", " "), ha="center",
                va="top", fontsize=7, zorder=16)

    def _legend(self):
        L, fig = self.L, self.fig
        W, H = L["W"], L["H"]
        x, y, w, h = L["legend"]
        lax = fig.add_axes(_mm(W, H, x, y, w, h))
        lax.set_xticks([])
        lax.set_yticks([])
        for s in lax.spines.values():
            s.set_linewidth(0.6)
        lax.text(0.008, 0.5, "图\n\n例", transform=lax.transAxes, fontsize=8.5, weight="bold", va="center")
        items = self.items
        if not items:
            return
        if len(items) > 60:
            self.warn.append("图例类别 %d 个，仅显示前 60 个，请合并类别或分幅" % len(items))
            items = items[:60]
        lax.legend([i[0] for i in items], [i[1] for i in items], loc="upper left", bbox_to_anchor=(22.0 / w, 1.0),
                   ncol=self.ncol, fontsize=6.5, frameon=False, handlelength=2.2, handleheight=1.0,
                   columnspacing=1.4, borderaxespad=0.5, labelspacing=0.35)

    def _footer(self):
        L, fig, cfg = self.L, self.fig, self.cfg
        W, H = L["W"], L["H"]
        x, y, w, h = L["foot"]
        src = "；".join(self.sources) if self.sources else "（请填写）"
        lines = [
            "坐标系：%s；高程基准：%s" % (C.crs_desc(self.ctx.crs), cfg.get("height_datum") or "—"),
            "制图数据源：%s" % src,
            "制图单位：%s    成图时间：%s    比例尺：1:%d" % (cfg.get("mapper") or "", C.today_cn(), self.scale),
        ]
        fs = 6.2
        maxchars = max(len(s) for s in lines)
        if maxchars * fs * 0.36 > w:
            fs = max(4.2, w / (maxchars * 0.36))
        for i, s in enumerate(lines):
            fig.text(x / W, (y + h - i * (h / 3.0)) / H, s, ha="left", va="top", fontsize=fs)

    def save(self, base, formats, dpi):
        out = []
        for f in formats:
            p = "%s.%s" % (base, f)
            kw = {}
            if f in ("jpg", "jpeg"):
                kw["pil_kwargs"] = {"quality": 92}
            self.fig.savefig(p, dpi=dpi if f != "pdf" else 300, facecolor="white", **kw)
            out.append(p)
        return out


def _box(ext):
    from shapely.geometry import box
    return box(ext[0], ext[2], ext[1], ext[3])


# ------------------------------------------------------------ 各图件
def _extent_bounds(ctx, mode, extra=None):
    if mode == "project":
        gs = [ctx.project_geom] + ([extra] if extra is not None else [])
        b = _bounds_of(gs)
        pad = max(b[2] - b[0], b[3] - b[1]) * 0.08
        return (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)
    if mode == "admin" and "admin" in ctx.layers:
        return ctx.layers["admin"].total_bounds
    if mode == "admin":
        b = ctx.eval_geom.bounds
        w = max(b[2] - b[0], b[3] - b[1])
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        return (cx - w * 2.5, cy - w * 2.5, cx + w * 2.5, cy + w * 2.5)
    return ctx.eval_geom.bounds


def _basemap(cv, ctx):
    bm = ctx.cfg.get("basemap") or {}
    ext = cv.ext
    dx, dy = (ext[1] - ext[0]) * 0.1, (ext[3] - ext[2]) * 0.35   # 图例区调整后主图框可能变高，底图多取一些
    bounds = (ext[0] - dx, ext[2] - dy, ext[1] + dx, ext[3] + dy)
    try:
        if bm.get("path"):
            arr, e = C.read_basemap(bm["path"], ctx.crs, bounds)
            cv.image(arr, e, cmap="gray" if arr.ndim == 2 else None, alpha=0.85)
            cv.add_source(bm.get("source") or "工作底图")
            return True
        if bm.get("tianditu_key") and bm.get("tianditu_type") in C.TIANDITU_TYPES:
            arr, e = C.tianditu_basemap(bm["tianditu_key"], bm["tianditu_type"], ctx.crs, bounds, log=ctx.log)
            cv.image(arr, e, alpha=0.9)
            cv.add_source("天地图（参考底图）")
            return True
    except Exception as ex:  # 底图失败不影响专题图
        ctx.log("提示：底图未能加载（%s），本图不加底图" % ex)
    return False


def render(ctx, spec_id, sensitive_index=None):
    """生成一幅图，返回 MapCanvas；数据不足时返回 None。"""
    spec = C.SPEC_BY_ID[spec_id]
    cfg, L = ctx.cfg, ctx.cfg["layers"]
    if not all(ctx.has(n) for n in spec["needs"]):
        return None
    title = spec["title"]
    theme = spec["theme"]

    if spec_id == "location":
        bounds = _extent_bounds(ctx, "admin")
        cv = MapCanvas(ctx, title, bounds, fill=True)
        _basemap(cv, ctx)
        if "admin" in ctx.layers:
            ad = ctx.layers["admin"]
            ad.plot(ax=cv.ax, facecolor="#f7f3e8", edgecolor="#7a6a55", linewidth=0.7, zorder=2, alpha=0.9)
            cv.legend.append((Patch(facecolor="#f7f3e8", edgecolor="#7a6a55"), "行政区划"))
            if L["admin"].get("label"):
                cv.labels(ad, L["admin"]["label"], size=7.5)
            cv.add_source(L["admin"].get("source"))
        if "water" in ctx.layers:
            cv.water(C.clip(ctx.layers["water"], _box(cv.ext)), None)
            cv.add_source(L["water"].get("source"))
        c = ctx.project_geom.centroid
        cv.ax.plot([c.x], [c.y], marker="*", color="#e60000", markersize=16, markeredgecolor="black",
                   markeredgewidth=0.6, zorder=13)
        cv.ax.text(c.x, c.y + (cv.ext[3] - cv.ext[2]) * 0.03, cfg["project_name"], ha="center", fontsize=8,
                   color="#c00000", weight="bold", zorder=13,
                   path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])
        cv.legend.append((Line2D([0], [0], marker="*", color="w", markerfacecolor="#e60000", markeredgecolor="black",
                                 markersize=11, lw=0), "项目位置"))
        cv.outline(ctx.layers["project"], "project")
        cv.add_source(L["project"].get("source"))
        cv.finish()
        return cv

    if theme == "sensitive":
        if sensitive_index is None:
            # 总图：各敏感区以不同线型区分（表D.1）
            gs = [ctx.project_geom] + [g.union_all() for _, g in ctx.sensitive]
            cv = MapCanvas(ctx, "生态敏感区分布图", _pad(_bounds_of(gs)))
            _basemap(cv, ctx)
            for i, (s, g) in enumerate(ctx.sensitive):
                col, ls = SENS_COLORS[i % 5], SENS_LS[i % 5]
                g.plot(ax=cv.ax, facecolor=col, alpha=0.12, edgecolor="none", zorder=2)
                g.dissolve().boundary.plot(ax=cv.ax, color=col, linewidth=1.4, linestyle=ls, zorder=5)
                cv.legend.append((Line2D([0], [0], color=col, lw=1.4, ls=ls), s.get("name") or "生态敏感区%d" % (i + 1)))
                cv.add_source(s.get("source"))
            if "water" in ctx.layers:
                cv.water(C.clip(ctx.layers["water"], _box(cv.ext)), None)
            cv.outline(ctx.layers["project"], "project")
            cv.add_source(L["project"].get("source"))
            cv.finish()
            return cv
        s, g = ctx.sensitive[sensitive_index]
        name = s.get("name") or "生态敏感区%d" % (sensitive_index + 1)
        cv = MapCanvas(ctx, "%s与项目位置关系图" % name, _pad(_bounds_of([ctx.project_geom, g.union_all()])),
                       subtitle="（生态敏感区分布图之%d）" % (sensitive_index + 1))
        _basemap(cv, ctx)
        if s.get("field"):
            key = "sensitive_%d" % sensitive_index
            cats = sorted(g[s["field"]].astype(str).unique())
            user = (cfg.get("colors") or {}).get(key, {})
            for j, c in enumerate(cats):
                col = user.get(c) or ZONE_COLORS[j % len(ZONE_COLORS)]
                g[g[s["field"]].astype(str) == c].plot(ax=cv.ax, facecolor=col, alpha=0.75, edgecolor="#555555",
                                                       linewidth=0.4, zorder=2)
                cv.legend.append((Patch(facecolor=col, alpha=0.75, edgecolor="#555555"), c))
        else:
            g.plot(ax=cv.ax, facecolor="#9fd59a", alpha=0.6, edgecolor="none", zorder=2)
            cv.legend.append((Patch(facecolor="#9fd59a", alpha=0.6), name))
        g.dissolve().boundary.plot(ax=cv.ax, color="#008040", linewidth=1.3, zorder=5)
        cv.legend.append((Line2D([0], [0], color="#008040", lw=1.3), "%s边界" % name))
        cv.add_source(s.get("source"))
        cv.outline(ctx.layers["project"], "project")
        cv.add_source(L["project"].get("source"))
        cv.finish()
        return cv

    extent_mode = spec["extent"]
    extra = None
    if theme in ("measures",) and theme in ctx.layers:
        extra = ctx.layers[theme].union_all()
    bounds = _extent_bounds(ctx, extent_mode, extra)
    cv = MapCanvas(ctx, title, bounds, max_scale=spec.get("max_scale"))
    if theme in ("water", "targets", "habitat", "migration", "samples", "measures", "monitor"):
        _basemap(cv, ctx)

    if theme in ("landuse", "vegetation", "ecosystem"):
        lay, fld = ctx.layers[theme], L[theme].get("field")
        if not fld:
            ctx.log("提示：%s 未指定分类字段，无法成图" % C.SLOT_NAMES[theme])
            return None
        if spec.get("occupy"):
            shown = C.clip(lay, _box(cv.ext))
            cv.categories(shown, fld, theme)
            # 叠置：工程占用部分加斜线
            occ = C.clip(lay, ctx.project_geom)
            if not occ.empty:
                occ.plot(ax=cv.ax, facecolor="none", edgecolor="#c00000", hatch="////", linewidth=0, zorder=4)
                cv.legend.append((Patch(facecolor="white", edgecolor="#c00000", hatch="////"), "工程占用区域"))
        else:
            cv.categories(C.clip(lay, ctx.eval_geom), fld, theme)
        cv.add_source(L[theme].get("source"))
        cv.standard_overlays(water=False)
    elif theme == "fvc":
        f = ctx.fvc
        cmap = ListedColormap(["#ffffff00"] + FVC_COLORS[:len(cfg["fvc"]["labels"])])
        arr = np.ma.masked_where(f["cls"] == 0, f["cls"])
        cv.ax.imshow(arr, extent=f["extent"], origin="upper", cmap=ListedColormap(FVC_COLORS[:len(cfg["fvc"]["labels"])]),
                     vmin=1, vmax=len(cfg["fvc"]["labels"]), interpolation="nearest", zorder=2)
        cv.ax.set_xlim(cv.ext[0], cv.ext[1])
        cv.ax.set_ylim(cv.ext[2], cv.ext[3])
        cv.ax.set_aspect("auto")
        for c, lb in zip(FVC_COLORS, cfg["fvc"]["labels"]):
            cv.legend.append((Patch(facecolor=c, edgecolor="#777"), lb))
        cv.add_source(cfg["fvc"].get("source"))
        cv.subtitle = "FVC=(NDVI-NDVIs)/(NDVIv-NDVIs)，NDVIs=%.3f，NDVIv=%.3f，平均覆盖度 %.1f%%" % (
            f["ns"], f["nv"], f["mean"] * 100)
        cv.standard_overlays(water=False)
    elif theme == "water":
        cv.water(C.clip(ctx.layers["water"], _box(cv.ext)), L["water"].get("label"))
        cv.add_source(L["water"].get("source"))
        cv.outline(ctx.layers["eval_range"], "eval_range")
        cv.outline(ctx.layers["project"], "project")
        cv.add_source(L["project"].get("source"))
    else:
        lay = C.clip(ctx.layers[theme], _box(cv.ext))
        sl = L[theme]
        cv.standard_overlays(water=True)
        cv.points(lay, sl.get("field"), theme, sl.get("label"), sl.get("elev") if theme == "samples" else None)
        cv.add_source(sl.get("source"))
    cv.finish()
    return cv


def _pad(b, f=0.08):
    pad = max(b[2] - b[0], b[3] - b[1]) * f
    return (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)


def jobs(ctx, ids=None):
    """要生成的图件 [(spec_id, sensitive_index, 文件名)]。"""
    ids = ids or ctx.cfg.get("maps") or [s["id"] for s in C.MAP_SPECS]
    out = []
    n = 0
    for s in C.MAP_SPECS:
        if s["id"] not in ids:
            continue
        if not all(ctx.has(k) for k in s["needs"]):
            continue
        n += 1
        if s["id"] == "sensitive":
            out.append((s["id"], None, "%02d_生态敏感区分布图" % n))
            for i, (sp, _) in enumerate(ctx.sensitive):
                nm = sp.get("name") or "生态敏感区%d" % (i + 1)
                out.append((s["id"], i, "%02d-%d_%s与项目位置关系图" % (n, i + 1, _safe(nm))))
        else:
            out.append((s["id"], None, "%02d_%s" % (n, s["title"])))
    return out


def _safe(s):
    for ch in '\\/:*?"<>|':
        s = s.replace(ch, "_")
    return s
