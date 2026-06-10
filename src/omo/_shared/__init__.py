"""omo._shared — 跨仓可复用抽象 (Round 24 P0).

定位 (§12 跨仓契约配套):
  - §12 描述"跨仓必须满足的 4 不变量" (物理 SSOT / 写时 Pydantic / Z-suffix / sort_keys)
  - 本包 = "不变量 1 (物理 SSOT) 的 SSOT 实现", 让其他仓 (kairon/gbrain/runtime/metaos)
    真能直接 import 同一份 `AppendOnlyLog` + `fcntl_lock`, 而非各自 copy

§12 跨仓接入 (Round 24 P0):
  其他仓接入模式时, 走 `from omo._shared.append_only_log import AppendOnlyLog, fcntl_lock`
  即可 (前提: omo 是 installable package; 当前 omo 是 submodule, 跨仓需先把 omostation
  根 pip install -e . 或显式 git submodule 引用)

Round 24 P0 子集:
  - §12.2.1 Step 1: AppendOnlyLog + fcntl_lock (本包, ~280 lines)
  - §12.2.1 Step 2: ZTimestampModel (留 §12.8 后续轮, 因 omo_io_schemas 依赖重)
"""
