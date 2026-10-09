# -*- coding: utf-8 -*-
"""制图核心校验：纯计算函数与手算比对，示例项目全流程出图。python ecomap/tests/test_core.py"""
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import numpy as np  # noqa: E402

import ecomap_core as C  # noqa: E402


def test_pure():
    # CGCS2000 3 度带：118.6°E→中央经线 120°E（4549），117.9°E→117°E（4548）
    assert C.cgcs2000_3deg_epsg(118.6) == 4549
    assert C.cgcs2000_3deg_epsg(117.9) == 4548
    assert C.cgcs2000_3deg_epsg(75.0) == 4534 and C.cgcs2000_3deg_epsg(135.0) == 4554
    # 比例尺：3000 m×3000 m 放入 180 mm×200 mm 图框，需 1:18000 → 标准比例尺 1:25000
    assert C.choose_scale(3000, 3000, 180, 200) == 25000
    assert C.choose_scale(500, 400, 180, 200) == 5000
    assert C.nice_bar_length(2500) == 500
    # 式 C.5：NDVI 0..1 均匀，5%/95% 分位 → 0.05、0.95；NDVI=0.5 → FVC=0.5
    ndvi = np.linspace(0, 1, 101)
    fvc, ns, nv = C.fvc_from_ndvi(ndvi, 5, 95)
    assert abs(ns - 0.05) < 1e-9 and abs(nv - 0.95) < 1e-9
    assert abs(fvc[50] - 0.5) < 1e-9 and fvc[0] == 0 and fvc[-1] == 1
    cls = C.classify(np.array([0.1, 0.3, 0.5, 0.7, 0.9, np.nan]), [0.3, 0.45, 0.6, 0.75])
    assert cls.tolist() == [1, 2, 3, 4, 5, 0]
    # NDVI=(NIR-Red)/(NIR+Red)：Red=0.1，NIR=0.5 → 0.6667
    assert abs(C.ndvi_from_bands([1000], [5000], 0.0001, 0)[0] - 0.4 / 0.6) < 1e-9
    t = C.area_table({"林地": 30000.0, "耕地": 10000.0})
    assert t == [("林地", 3.0, 75.0), ("耕地", 1.0, 25.0), ("合计", 4.0, 100.0)]
    # GCJ-02 往返
    lon, lat = C.gcj02_to_wgs84(*C.wgs84_to_gcj02(118.55, 25.05))
    assert abs(lon - 118.55) < 1e-7 and abs(lat - 25.05) < 1e-7
    print("纯计算校验：通过")


def test_sample():
    import ecomap_sample
    import ecomap_run
    d = tempfile.mkdtemp(prefix="ecomap_test_")
    cfg = C.load_config(ecomap_sample.make_sample(d))
    out, files, warns = ecomap_run.run(cfg, log=lambda m: None)
    assert len(files) == 36, len(files)
    assert not [w for w in warns if "生成失败" in w], warns
    ctx = C.Context(cfg, log=lambda m: None)
    # 评价范围内各地类面积合计应等于评价范围面积（示例土地利用数据完全覆盖评价范围）
    tab = ctx.stats["评价范围内土地利用现状面积"]
    assert math.isclose(tab[-1][1], ctx.eval_geom.area / 1e4, rel_tol=1e-6), (tab[-1], ctx.eval_geom.area)
    occ = ctx.stats["工程占用土地利用现状面积"]
    assert math.isclose(occ[-1][1], ctx.project_geom.area / 1e4, rel_tol=1e-6)
    print("示例项目出图：通过（%d 个文件）" % len(files))


if __name__ == "__main__":
    test_pure()
    test_sample()
