"""Domain cartridge packages for omostation workspace.

`domain` is the import root for domain-cartridge capabilities.  Each subpackage
(`research`, `health`, `health_gov`, ...) is a self-contained cartridge that can
be run via `uv run python -m domain.<name>.<entry>`.

Health-gov cartridge: 卫健公文全周期拟办、批阅与会议督办闭环
(register → draft → approve → dispatch → redhead export → supervise).
Fully deterministic local computation. 涉密公文拒绝入库；版式要素缺失阻止导出；
无署名批阅/办结拒绝落盘 — never fabricated, never silently degraded.
PDF 导出需 reportlab（workspace .venv 已装），缺失时显式抛错。
"""

__version__ = "0.1.0"
