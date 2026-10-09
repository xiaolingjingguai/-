# 生态影响评价制图（桌面版）

按《环境影响评价技术导则 生态影响》（HJ 19—2022）批量编制生态影响评价图件的 Windows 桌面程序，不依赖 ArcGIS。
开源库：geopandas、shapely、pyproj、pyogrio、rasterio（均自带 GDAL/PROJ）、matplotlib、tkinter。

- 图件：地理位置图、水系图、土地利用现状图、植被类型图、植被覆盖度图（式 C.5）、生态系统类型图、生态保护目标分布图、
  生态敏感区分布图（每处单独成图 + 总图）、重要物种及生境分布图、迁徙洄游路线图、样方样线布设图、
  工程占用叠置图（土地利用/植被/生态系统）、生态保护措施平面布置图、生态监测布点图。
- 图面要素按附录 D.3；比例尺按 D.2 取标准比例尺，超出范围时提示分幅；公里网、图廓自动绘制。
- 面积统计（评价范围内、工程占用）与按评价等级的图件清单导出为 Excel。

## 目录

- `ecomap_core.py`：数据读入、坐标系、裁剪、面积统计、植被覆盖度、图件清单
- `ecomap_render.py`：图面绘制
- `ecomap_run.py`：批量出图与导出
- `ecomap_gui.py`：桌面界面；`--selftest 结果.txt` 无人值守自检，`--batch 配置.json` 命令行出图
- `ecomap_sample.py`：虚构示例项目数据
- `tests/test_core.py`：纯计算与示例全流程校验
- `../.github/workflows/build-ecomap.yml`：windows-latest 上 PyInstaller 打包、自检并发布到 Releases

## 本地运行

```
pip install -r ecomap/requirements.txt
python ecomap/ecomap_gui.py
```
