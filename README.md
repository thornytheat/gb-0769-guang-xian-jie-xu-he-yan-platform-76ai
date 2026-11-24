# 光纤接续核验台

验收员从 A、B 两端 OTDR 事件原件和设计清单复算接续损耗。首页比对双端轨迹帧与设计接头，按 `J`、`K` 或使用跳检按钮定位证据。左侧七个入口分别处理采信、校准、配对、判损、对账、留档和签发。

`docker compose up --build` 后访问 `http://localhost:18468/`。本地先执行 `pip install -r requirements.txt`，再运行 `python -m flask --app app.main run --port=18468`，用 `pytest -q` 验收。`FIBER_DB` 设置 SQLite 文件，Compose 的命名卷保留运行记录。

各预览和留档 API 接收 `{"sample":"dirty"}`、`{"sample":"clean"}`、`{"sample":"dual"}` 或 `{"traces":{"a":"CSV","b":"CSV","design":"CSV"},"settings":{...}}`。参数示例见 `sample_data/dirty/link.json`。从留档页提交，在签发页下载核验包。

## 双波长签发（splice-2.0）

轨迹 CSV 增加可选 `wavelength` 列（nm），设置增加可选 `wavelengths_nm` 声明波长后，线路按双波长规则核验；不声明则保持旧单波长规则，旧留档的签发件仍可原样核验。

- 配对、判损、对账全部按波长分组：同一接头的 1310 与 1550 读数不能凑成双端对账；未标波长的旧读数只在无标签组内处理，不作任何波长的试通凭据。
- 签发页对双端达标的波长出具**试通件**（如样本 `dual`：1310 双端达标即放行 1310，1550 缺 B 端实测则明确列为未覆盖）；**正式交工**须全部声明波长均有双端达标证据。
- 同一物理线路（全长、两端起偏、设计清单一致）的多次归档汇入线路证据池。晚到的补测记录一旦证实任一波长超限（样本 `dual_late`），试通件即停止放行；补测达标（样本 `dual_full`）后正式交工才可签发。冲突补测整组撤出并留痕，已证实的超限不随冲突撤消。

- [模块与独立复算](docs/DEPTH.md)
- [字段与规则](docs/DATA-DICTIONARY.md)
