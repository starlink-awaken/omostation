"""基础设施层 — 类型系统/数据模型/常量/工具/配置/契约"""

from ontoderive.foundation.config import Config
from ontoderive.foundation.constants import (
    CONFIDENCE_MAP,
    RE_ENTITY_ID,
    RE_FACT_ID,
    V2_ID_PATTERNS,
)
from ontoderive.foundation.models import (
    CheckResult,
    DeriveSnapshot,
    Entity,
    Fact,
    Inference,
    Scheme,
)
from ontoderive.foundation.ontology_map import (
    TYPE_MAPPINGS,
    OntologyMapper,
    RDFTriple,
)
from ontoderive.foundation.protocols import (
    AnalysisResult,
    DeriveInterface,
    PipelineObservable,
    ToolForgeInterface,
)
from ontoderive.foundation.rule_loader import RuleLoader
from ontoderive.foundation.semantic import SemanticMatcher
from ontoderive.foundation.typesystem import (
    META_TYPES,
    PREFIX_TO_META,
    TypeValidator,
)
from ontoderive.foundation.utils import (
    CachedReader,
    all_md,
    detect_cycles,
    load_json,
    rf,
    save_json,
    wf,
)
