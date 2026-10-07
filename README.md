# HJ 169 风险计算器（桌面版）

按《建设项目环境风险评价技术导则》（HJ 169-2018）附录C、D、F、G 进行环境风险潜势判定、事故源强核算与大气预测模型筛选的 Windows 桌面程序（Python + tkinter）。

- 物质库约 3200 种：表B.1／B.2 临界量、表H.1 及 3146 种终点浓度、理化燃爆与毒理参数（均附来源），可按中文名、英文名、CAS 检索，选中后参数自动带入各计算模块。
- 不做扩散浓度预测；大气风险预测须采用 SLAB、AFTOX 等推荐模型。

## 目录

- `app/hj169calc.py`：计算核心（纯函数，公式编号对应导则）
- `app/hj169_gui.py`：桌面界面；`python app/hj169_gui.py --selftest out.txt` 运行无人值守自检
- `app/selfcheck.py`、`tests/test_calc.py`：与独立手算比对的校验算例
- `app/data/substances.json`：物质库，由 `tools/build_data.py` 生成
- `.github/workflows/build-windows.yml`：在 windows-latest 上用 PyInstaller 打包、自检并发布到 Releases

## 本地运行

```
python app/hj169_gui.py
```
