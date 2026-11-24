# 轨迹、接头与判损字段

A、B 的 CSV 必填 `event,distance,unit,loss_db`，设计清单必填 `joint,distance,unit,limit_db`。字段可换列序，UTF-8 首行 BOM 会清理。ID 为原形字符串，按来源和 ID 分键。同键比较归一距离与损耗，完全相同保留首行，冲突整组隔离。记录保留起始物理行和原值。空白单元格、哨兵及 JSON null 分别校验。空文件、全空行、仅表头分别为 `EMPTY_FILE`、`BLANK_FILE`、`HEADER_ONLY`。每源最多 350 个正文记录、250,000 字符。

距离单位可为 mm、m 或 km，归一成整数毫米。采集损耗 dB 支持有符号值，精确到毫 dB。配置 `length_m` 为光路总长，`zero_a_m/zero_b_m` 为两向测量偏置。统一链程 A = A 原读数减 A 起偏，B = 全长减去 B 原读数扣掉 B 起偏的结果。校准有效范围是闭区间 `[0,L]`。出界测量归隔离，出界设计仍在清单中并标缺证。设计本来就在 A 端坐标系。

双端事件按链程和 ID 排序。一对一单调配对先最大化数量，再最小化距离差总和，最后依照同状态优先配对、保留较早 A 端、再保留较早 B 端的固定遍历作稳定裁决。容差 `pair_tol_m` 含等号。配对中点的分辨率为半毫米。配对双方的读数取带符号平均作为净损耗，保留单向负值和原行。通过阈值含等号，净值为负记录无效净增益。

设计点与配对中点再次按相同优化目标一对一对齐，使用 `design_tol_m`。每接头以自己的 `limit_db` 判定，损耗模块的 `reference_limit_db` 用于单独预览。单端或孤配均保留。运行清单含源 SHA-256、校准参数、时间 UTC、耗时、版本、证据。快照摘要可用排序键、紧凑 JSON 和 UTF-8 重算。

## 波长与双波长签发

A、B 的 CSV 可带 `wavelength` 列（整数 nm，800–1700，非法值按 `BAD_WAVELENGTH` 隔离）；不带列的原件视为未标波长。设置可带 `wavelengths_nm`（逗号分隔或整数数组），声明后规则版本为 `splice-2.0`，轨迹带标签却未声明时报 `WAVELENGTH_UNDECLARED`，标签超出声明集合的读数归隔离。声明波长后：配对、判损、对账按波长分组，同一接头不同波长的读数不能凑对；同一事件号在不同波长是两条测量，不算冲突；未标波长的读数只在无标签组内处理，不进任何波长的证据。

双波长记录派生 `line_id`（全长、两端起偏、设计清单摘要），同一物理线路的多次归档按归档顺序汇入线路证据池，以最新记录的校准参数重算。签发结论按池计算：

- `wavelengths`：各声明波长的接头数、通过、超限、缺证与状态（`DUAL_END_PASS` / `INCOMPLETE` / `OVER_LIMIT` / `NO_DESIGN`）。
- `trial_pass`（试通件）：`released` 仅当无超限证据且至少一个波长双端达标；`wavelengths` 为覆盖波长，`withheld` 逐波长给出未覆盖原因（`MISSING_DUAL_END_EVIDENCE` / `OVER_LIMIT`）。未列波长不视为验收合格。
- `suspension`：任一历史前缀证据池证实任一波长超限（设计接头超限或孤配超参考限）即留痕，`released` 归假；已留痕的超限不随后续冲突撤出。冲突补测（同事件同波长异值）整组撤出并列入 `conflicts`，同时阻塞正式交工（`CONFLICTING_SUPPLEMENT`）。
- `approved`（正式交工）：须全部声明波长双端达标且无停放行证据、无冲突、设计清单已核验；阻塞码为 `MISSING_DUAL_END`、`LOSS_OVER_LIMIT`、`CONFLICTING_SUPPLEMENT`、`EMPTY_DESIGN`、`UNVERIFIED_DESIGN_ROWS`。

旧留档未标波长，规则版本保持 `splice-1.0`，原签发件仍可核验；旧读数不进双波长线路的证据池，不作试通凭据。
