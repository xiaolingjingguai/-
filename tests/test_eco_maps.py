"""运行：python tests/test_eco_maps.py（无需 arcpy，校验生态制图脚本的纯计算函数）"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "eco_mapping"))
import eco_maps as e  # noqa: E402


def main():
    # CGCS2000 3 度带：泉州鲤城区约 118.59°E → 中央经线 120°E (4549)；安溪约 118.19°E → 117°E (4548)
    assert e.cgcs2000_3deg_wkid(118.59) == 4549
    assert e.cgcs2000_3deg_wkid(118.19) == 4548
    assert e.cgcs2000_3deg_wkid(75.0) == 4534 and e.cgcs2000_3deg_wkid(135.0) == 4554

    # 3 km × 2 km 范围、190 mm × 227 mm 图框：需 ≥1:17053 → 取 1:25000
    assert e.choose_scale(3000, 2000, 190, 227) == 25000
    assert e.choose_scale(800, 600, 190, 227) == 5000

    # 式 C.5：有效 NDVI 为 0.01~1.00，5%/95% 分位（线性插值）→ 0.0595/0.9505
    ndvi = np.linspace(0, 1, 101)
    ndvi[0] = np.nan
    fvc, ns, nv = e.fvc_from_ndvi(ndvi, 5, 95)
    assert abs(ns - 0.0595) < 1e-9 and abs(nv - 0.9505) < 1e-9, (ns, nv)
    assert np.isnan(fvc[0]) and fvc[1] == 0.0 and fvc[-1] == 1.0
    assert abs(fvc[51] - (0.51 - 0.0595) / 0.891) < 1e-9

    g = e.classify(np.array([np.nan, 0.1, 0.30, 0.5, 0.74, 0.75, 1.0]), [0.30, 0.45, 0.60, 0.75])
    assert g.tolist() == [0, 1, 2, 3, 4, 5, 5], g.tolist()

    t = e.area_table({"乔木林地": 30000.0, "旱地": 10000.0}, total=80000.0)
    assert t == [("乔木林地", 3.0, 37.5), ("旱地", 1.0, 12.5), ("合计", 4.0, 50.0)], t
    print("eco_maps 纯计算函数校验通过")


if __name__ == "__main__":
    main()
