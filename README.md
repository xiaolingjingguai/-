# HJ 169 风险计算器（桌面版）

按《建设项目环境风险评价技术导则》（HJ 169-2018）附录C、D、F、G 进行环境风险潜势判定、事故源强核算与大气预测模型筛选的 Windows 桌面程序（Python + tkinter）。

- 物质库约 3200 种：表B.1／B.2 临界量、表H.1 及 3146 种终点浓度、理化燃爆与毒理参数（均附来源），可按中文名、英文名、CAS 检索，选中后参数自动带入各计算模块。
- 计算书可导出 Word（三线表，可直接放入环评报告）、Excel 或纯文字；顶部“当前物质”下拉点选；输入有误（相态与模型不符、负值、单位异常）时标红并停止计算；“评价等级判定”页给出各要素潜势、评价工作等级、评价范围（4.5）与判定表。
- 不做扩散浓度预测；大气风险预测须采用 SLAB、AFTOX 等推荐模型。

## 软件授权（只给指定用户使用）

内置“机器绑定 + 离线授权”机制：程序启动时校验与本机绑定、由作者用私钥签发的 `license.key`。
未授权时允许首次试用 30 分钟（`TRIAL_MINUTES`），到时弹窗显示机器码并锁定。作者用 `tools/license_issuer.py` 为指定机器签发授权（默认一年有效期，也可设为永久或指定到期日）。
完整说明见 [`packaging/软件授权说明.md`](packaging/软件授权说明.md)。

- `app/license_verify.py`：程序内置校验（内置公钥、机器码、启动门禁）；`app/_ed25519_pure.py`：纯 Python Ed25519 验证（零额外依赖）。
- `tools/make_keys.py`：生成作者密钥对；`tools/license_issuer.py`：授权码生成器（GUI + 命令行）。
- `tests/test_license.py`：许可机制自测。

> 安全边界：该机制可阻止普通用户私自传播/换机/改期，但 Python 打包程序可被专业逆向；
> 需更强保护请叠加 PyArmor 等代码混淆，详见授权说明。

## 目录

- `app/hj169calc.py`：计算核心（纯函数，公式编号对应导则）
- `app/hj169_gui.py`：桌面界面；`python app/hj169_gui.py --selftest out.txt` 运行无人值守自检
- `app/report_export.py`：计算书导出（文字、Word、Excel；依赖 python-docx、openpyxl）
- `app/selfcheck.py`、`tests/test_calc.py`：与独立手算比对的校验算例
- `app/data/substances.json`：物质库，由 `tools/build_data.py` 生成
- `.github/workflows/build-windows.yml`：在 windows-latest 上用 PyInstaller 打包、自检并发布到 Releases

## 本地运行

```
python app/hj169_gui.py
```
