---
schema_version: specification/v1
spec_version: 1.0.0
title: OpenHuman 本地桥接器升级与多源健康生物标记物 Schema 归一化设计
bet_id: BET-Y1Q4-T6-25
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-12
value_indicator_policy: false
---

# T6-25 — OpenHuman Local Bridge & Biometric Normalizer 设计

## 1. 问题

OpenHumanConnector (`connector.py`) 是 Kairon/Iris 对 Apple Health、Garmin、
Fitbit 等健康数据源的唯一入口，但当前实现存在三个核心缺陷：

1. **无容错**：本地 JSON-RPC 7788 端口不可达时直接抛异常，无看门狗、无重试、
   无 fallback，导致 Resident Daemon 巡检链路断裂。
2. **数据膨胀**：从 Apple Health 导出的 XML/JSON 体积大（单日 CGM 数据
   可达 500KB+），无压缩管道，网络传输与存储成本浪费 70%+ 冗余。
3. **Schema 碎片化**：Apple Health XML、CGM JSON、Garmin CSV、Fitbit API
   各自格式独立，无统一归一化层，下游 Family-Hub 与 `bos://persona/health-profile/*`
   需为每个数据源写独立解析器。

## 2. 非目标（与 ledger non_goals 一致）

- 不引入任何第三方云端托管中继（坚持 Local-First 与零凭据泄露）。
- 不修改外部硬件厂商固件。

## 3. 设计

### 3.1 本地桥接器加固（`connector.py` 重构）

在现有 `OpenHumanConnector` 上新增三个能力层：

```python
class OpenHumanConnector:
    # ── 新增: 看门狗 ──
    def _watchdog(self) -> WatchdogStatus:
        """探测 JSON-RPC 7788 端口可达性, 返回 alive/degraded/dead 三态"""
        ...

    # ── 新增: 指数退避重试 ──
    def call_with_retry(self, method: str, params: dict,
                        max_retries: int = 3, base_delay: float = 1.0) -> dict:
        """指数退避重试 (1s → 2s → 4s), 全部失败后 fallback 到 SQLite 缓存"""
        ...

    # ── 新增: SQLite fallback ──
    def _fallback_to_sqlite(self, method: str, params: dict) -> dict:
        """降级为本地 SQLite 事务存储, 保证核心流程不阻塞"""
        ...
```

**看门狗状态机**: `alive → degraded (3 次超时) → dead (5 次超时) → revive (连续 2 次成功)`

### 3.2 TokenJuice 轻量数据压缩器（`token_juice.py` 新建）

```python
class TokenJuice:
    """HTML/JSON 高密 Markdown 压缩管道, 目标平均降噪 ≥60% 冗余剔除"""

    def compress(self, data: bytes, source_type: str) -> bytes:
        """
        source_type: "html" | "json" | "xml" | "text"
        - html: 去除空白/注释/属性冗余 → Markdown 近似
        - json: 去除键名重复路径 → 紧凑 JSON Lines
        - xml: 去除命名空间冗余 → 最小 XML
        """
        ...

    def decompress(self, data: bytes, source_type: str) -> bytes:
        """逆操作, 保证无损还原"""
        ...

    @staticmethod
    def compression_ratio(data: bytes, source_type: str) -> float:
        """返回压缩比 (0.0 = 无压缩, 1.0 = 全部冗余)"""
        ...
```

**测试指标**: 长文本/HTML/JSON 三类样本平均压缩率 ≥60%（测试中硬断言）。

### 3.3 BiomarkerNormalizer 多源归一化解析器（`biomarkers.py` 新建）

```python
@dataclass
class NormalizedBiomarker:
    """统一生物标记物记录"""
    timestamp: datetime
    source: str           # "apple_health" | "cgm" | "garmin" | "fitbit"
    category: str         # "glucose" | "heart_rate" | "steps" | "sleep" | ...
    value: float
    unit: str             # "mg/dL" | "bpm" | "steps" | "hours" | ...
    confidence: float     # 0.0 ~ 1.0

class BiomarkerNormalizer:
    """多源健康数据归一化管道"""

    def normalize(self, raw_data: bytes, source_type: str) -> list[NormalizedBiomarker]:
        """
        source_type:
        - "apple_health_xml": 解析 Apple Health 导出 XML
        - "cgm_json": 解析 CGM 连续血糖 JSON
        - "garmin_csv": 解析 Garmin 导出 CSV
        - "fitbit_json": 解析 Fitbit API JSON
        """
        ...

    def merge(self, records: list[NormalizedBiomarker]) -> list[NormalizedBiomarker]:
        """多源融合: 按 (category, timestamp) 去重, 取最高 confidence"""
        ...
```

**支持的标记物类别** (首期):
- `glucose` (CGM + Apple Health) — mg/dL
- `heart_rate` (Garmin + Fitbit + Apple Health) — bpm
- `steps` (Garmin + Fitbit) — steps
- `sleep` (All) — hours

### 3.4 Family-Hub 健康导入器（`health_importer.py` 新建）

```python
class HealthImporter:
    """将 NormalizedBiomarker 批量写入 Family-Hub 文档 + BOS 投影"""

    def import_batch(self, records: list[NormalizedBiomarker]) -> ImportResult:
        """
        1. 写入 Family-Hub documents (health_profile/{date}/{category}.md)
        2. 发布到 bos://persona/health-profile/ingest
        3. 返回 ImportResult(success_count, failed_count, bos_receipt)
        """
        ...
```

### 3.5 BOS 路由注册

在 `bos-services.yaml` 追加:
- `bos://persona/health-profile/ingest` — 健康数据批量写入

### 3.6 测试

- `projects/knowledge/kairon/packages/iris/tests/test_openhuman_bridge.py`:
  - 看门狗状态机转移 (alive → degraded → dead → revive)
  - 重试容错 (模拟 3 次失败后 fallback)
  - TokenJuice 压缩率 ≥60% (HTML/JSON/长文本三类样本)
  - BiomarkerNormalizer 各 source_type 解析正确性
  - 多源融合去重逻辑
  - Family-Hub 导入端到端 (mock BOS endpoint)

## 4. 完成判据映射

| done_when | 落点 |
|---|---|
| 本地进程可用性探测、自愈心跳与安全 fallback | §3.1 看门狗 + 重试 + SQLite fallback |
| TokenJuice 压缩率 ≥60% | §3.2 压缩管道 + 测试硬断言 |
| BiomarkerNormalizer 多源归一化 | §3.3 四类 source_type + 融合 |
| Family-Hub 与 health-profile 渲染 | §3.4 HealthImporter + §3.5 BOS 路由 |

## 5. 风险与回滚

- 所有新增模块均为新增文件，回滚 = revert 单 PR。
- `connector.py` 重构保持向后兼容（现有接口签名不变，仅新增方法）。
- TokenJuice 压缩为可选层（默认不启用，显式调用才压缩）。
- BiomarkerNormalizer 不修改任何现有数据格式，仅新增归一化入口。
- Family-Hub 导入为新增模块，不修改现有 Family-Hub 接口。

## 6. 关键约束

- **数据本地化**: 所有健康数据仅在本地处理，TokenJuice 压缩在本地完成，
  BiomarkerNormalizer 在本地解析，Family-Hub 写入本地文件系统。
- **无云端泄露**: 严禁通过 HTTP POST 将原始健康数据发送到外部 API。
- **熔断降级**: Oxigraph 初始化失败时自动降级 SQLite（与 T6-26 共享降级模式）。
