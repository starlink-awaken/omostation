"""
cockpit.domain.fuzzy_matcher — 智能命令拼写纠错建议引擎 (Did You Mean...)

基于快速 Levenshtein 距离与前缀重合度，对未知输入命令提供相近合法命令建议。
无第三方依赖，执行耗时 < 1ms。
"""

from __future__ import annotations

from typing import Iterable


def levenshtein_distance(s1: str, s2: str) -> int:
    """计算两个字符串的 Levenshtein 编辑距离"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def similarity_ratio(s1: str, s2: str) -> float:
    """计算相似度比例 (0.0 ~ 1.0)"""
    s1 = s1.lower().strip()
    s2 = s2.lower().strip()
    if s1 == s2:
        return 1.0
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    dist = levenshtein_distance(s1, s2)
    # 若包含前缀或子串，给予一定加权
    bonus = 0.0
    if s1 in s2 or s2 in s1:
        bonus = 0.15
    ratio = (1.0 - (dist / max_len)) + bonus
    return min(1.0, max(0.0, ratio))


def find_closest_commands(
    target: str,
    candidates: Iterable[str] | None = None,
    max_results: int = 3,
    min_similarity: float = 0.55,
) -> list[str]:
    """寻找与 target 最接近的命令候选列表，按相似度降序排列"""
    if not target:
        return []

    target = target.lower().strip()

    if candidates is None:
        try:
            from cockpit.commands.registry import COMMAND_CATALOG, ORTHOGONAL_DOMAINS
            pool = set(COMMAND_CATALOG.keys()) | set(ORTHOGONAL_DOMAINS.keys())
        except Exception:
            pool = set()
    else:
        pool = set(candidates)

    scored: list[tuple[float, int, str]] = []
    for cmd in pool:
        score = similarity_ratio(target, cmd)
        dist = levenshtein_distance(target, cmd.lower())
        # 仅保留编辑距离 <= 3 且相似度达到阈值的候选
        if (dist <= 3 or target in cmd or cmd in target) and score >= min_similarity:
            scored.append((score, -dist, cmd))

    # 相似度高的排前面，距离小的排前面
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [item[2] for item in scored[:max_results]]
