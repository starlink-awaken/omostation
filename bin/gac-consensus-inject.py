#!/usr/bin/env python3
# bin/gac-consensus-inject.py — KOS 避坑共识跨会话基因注入特权代理
# Phase A (2026-07-03): 升级为 RAG Top-2 按需注入，替代全量追加模式
# 降低 CLAUDE.md Token 膨胀，实现 Epigenetic Memory 按需激活

import os
import sys
import sqlite3
import re
import json
import math
import datetime
import urllib.request
import urllib.error
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
db_path = WORKSPACE / "kos/kos-index.sqlite"
claude_md_path = WORKSPACE / "CLAUDE.md"

# omlx 统一网关 (Tailscale MBP)
OMLX_GATEWAY = "http://100.96.126.35:4000"
EMBED_MODEL = "embed-bge"  # omlx embed-bge 模型 (MBP 本机)
OMLX_API_KEY = "sk-omlx-admin"
TOP_K = 2  # 每次只注入最相关的 Top-2 Consensus，极限节省 Token


def local_tfidf_similarity(query: str, doc: str) -> float:
    """Pure-Python TF-IDF 余弦相似度 — 无下载 embed 模型时的高质量 Fallback"""
    def tokenize(text: str) -> list[str]:
        return re.findall(r'[\w\u4e00-\u9fff]+', text.lower())

    def tf(tokens: list[str]) -> dict[str, float]:
        freq: dict[str, float] = {}
        for t in tokens:
            freq[t] = freq.get(t, 0.0) + 1.0
        total = len(tokens) or 1
        return {t: c / total for t, c in freq.items()}

    q_tokens = tokenize(query)
    d_tokens = tokenize(doc)
    q_tf = tf(q_tokens)
    d_tf = tf(d_tokens)
    vocab = set(q_tf) | set(d_tf)
    dot = sum(q_tf.get(w, 0.0) * d_tf.get(w, 0.0) for w in vocab)
    norm_q = math.sqrt(sum(v * v for v in q_tf.values()))
    norm_d = math.sqrt(sum(v * v for v in d_tf.values()))
    if norm_q == 0 or norm_d == 0:
        return 0.0
    return dot / (norm_q * norm_d)


def get_embedding(text: str) -> list[float] | None:
    """调用 omlx embed-bge 模型获取文本向量，超时则返回 None"""
    try:
        payload = json.dumps({"model": EMBED_MODEL, "input": text[:2000]}).encode("utf-8")
        req = urllib.request.Request(
            f"{OMLX_GATEWAY}/v1/embeddings",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OMLX_API_KEY}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["data"][0]["embedding"]
    except Exception:
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算余弦相似度"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def get_or_build_consensus_vector(conn: sqlite3.Connection, entity_id: str, label: str, source_file: str) -> list[float] | None:
    """从缓存表读取或重新计算 Consensus 向量"""
    # 确保向量缓存表存在
    conn.execute("""
        CREATE TABLE IF NOT EXISTS consensus_vectors (
            entity_id TEXT PRIMARY KEY,
            vector_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()

    # 读取缓存
    row = conn.execute(
        "SELECT vector_json FROM consensus_vectors WHERE entity_id = ?",
        (entity_id,)
    ).fetchone()
    if row:
        return json.loads(row[0])

    # 缓存未命中 → 重新向量化
    # 用 label + 文件首 300 字符作为嵌入文本
    embed_text = label
    try:
        src_content = Path(source_file).read_text(encoding="utf-8")[:300]
        embed_text = f"{label}: {src_content}"
    except Exception:
        pass

    vec = get_embedding(embed_text)
    if vec:
        conn.execute(
            "INSERT OR REPLACE INTO consensus_vectors (entity_id, vector_json, updated_at) VALUES (?, ?, ?)",
            (entity_id, json.dumps(vec), datetime.datetime.now().isoformat())
        )
        conn.commit()

    return vec


def extract_clean_description(md_path: Path) -> str:
    """提取 markdown 中剔除 frontmatter 和一级标题后的纯文本简介"""
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL)
        lines = content.split("\n")
        desc_lines = []
        for line in lines:
            cleaned = line.strip()
            if not cleaned:
                continue
            if cleaned.startswith("#") or cleaned.startswith(">") or cleaned.startswith("```"):
                continue
            desc_lines.append(cleaned)
            if len(desc_lines) >= 3:
                break
        desc = " ".join(desc_lines)
        return desc[:200] + ("..." if len(desc) > 200 else "")
    except Exception:
        return "Consensus pattern guidelines."


import sys

def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        if not db_path.is_file():
            print(f"❌ [Consensus Inject Check] KOS SQLite DB missing at: {db_path}")
            return 1
        if not claude_md_path.is_file():
            print(f"❌ [Consensus Inject Check] CLAUDE.md missing at: {claude_md_path}")
            return 1
        try:
            db_conn = sqlite3.connect(str(db_path))
            consensuses = db_conn.execute(
                "SELECT entity_id FROM kos_entities WHERE entity_type='Consensus'"
            ).fetchall()
            db_conn.close()
            print(f"✅ [Consensus Inject Check] KOS DB accessible, found {len(consensuses)} consensus entities.")
            return 0
        except Exception as e:
            print(f"❌ [Consensus Inject Check] KOS DB query failed: {e}")
            return 1

    if not db_path.is_file() or not claude_md_path.is_file():
        return 0

    try:
        db_conn = sqlite3.connect(str(db_path))
        db_conn.row_factory = sqlite3.Row

        # 1. 从 KOS 读取所有 Consensus 实体
        consensuses = db_conn.execute(
            "SELECT entity_id, label, source_file FROM kos_entities WHERE entity_type='Consensus'"
        ).fetchall()

        if not consensuses:
            db_conn.close()
            return 0

        # 2. 读取当前任务上下文用于 RAG 查询（从 git staged 文件名 + 任务目标）
        task_context = ""
        try:
            import subprocess
            staged = subprocess.check_output(
                ["git", "diff", "--name-only", "--cached"],
                cwd=str(WORKSPACE), text=True
            ).strip()
            task_context += staged + "\n"
        except Exception:
            pass

        # 若无 staged 上下文，使用当前工作目录变更文件作为参考
        if not task_context.strip():
            try:
                import subprocess
                changed = subprocess.check_output(
                    ["git", "diff", "--name-only"],
                    cwd=str(WORKSPACE), text=True
                ).strip()
                task_context += changed
            except Exception:
                pass

        # 3. RAG 模式: 使用本地 TF-IDF 余弦相似度检索 Top-K 最相关 Consensus
        # 优先尝试 embed-bge 向量；embed 不可用时无缝降级为 TF-IDF (零延迟)
        selected_consensuses = list(consensuses)  # 默认全量 fallback
        rag_mode = False

        if task_context.strip():
            # 先构建每个 Consensus 的文本表示（label + 文件首段）
            consensus_texts: list[str] = []
            for item in consensuses:
                src_file = item["source_file"]
                label = item["label"]
                try:
                    src_content = Path(src_file).read_text(encoding="utf-8")[:400]
                    consensus_texts.append(f"{label}: {src_content}")
                except Exception:
                    consensus_texts.append(label)

            # 尝试 embed-bge 向量化
            query_vec = get_embedding(task_context[:1000])
            if query_vec:
                # 向量路径：embed-bge 余弦相似度
                rag_mode = True
                scored: list[tuple[float, sqlite3.Row]] = []
                for i, item in enumerate(consensuses):
                    eid = item["entity_id"]
                    label = item["label"]
                    src = item["source_file"]
                    c_vec = get_or_build_consensus_vector(db_conn, eid, label, src)
                    if c_vec:
                        score = cosine_similarity(query_vec, c_vec)
                        scored.append((score, item))
                if scored:
                    scored.sort(key=lambda x: x[0], reverse=True)
                    selected_consensuses = [item for _, item in scored[:TOP_K]]
                    top_labels = [item["label"][:40] for item in selected_consensuses]
                    print(f"[RAG/embed] 向量检索命中 Top-{TOP_K}: {top_labels}")
            else:
                # TF-IDF 路径：纯本地零依赖余弦相似度
                rag_mode = True
                tfidf_scored: list[tuple[float, sqlite3.Row]] = []
                for i, item in enumerate(consensuses):
                    score = local_tfidf_similarity(task_context, consensus_texts[i])
                    tfidf_scored.append((score, item))
                tfidf_scored.sort(key=lambda x: x[0], reverse=True)
                selected_consensuses = [item for _, item in tfidf_scored[:TOP_K]]
                top_labels = [item["label"][:40] for item in selected_consensuses]
                print(f"[RAG/tfidf] TF-IDF 检索命中 Top-{TOP_K}: {top_labels}")

        db_conn.close()

        # 4. 拼接共识基因 MD 内容
        mode_tag = "RAG Top-2 按需激活" if rag_mode else "全量注入"
        consensus_lines = [
            "## 🧬 Onboarding Consensus (🧬 历史演进避坑基因)",
            "",
            f"> **自动刷新时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 模式: {mode_tag}",
            "> 新进 Agent 必须通读并深度对齐以下前人沉淀的历史避坑基因，严禁在同一坑中二次栽倒：",
            "",
        ]

        for item in selected_consensuses:
            eid = item["entity_id"]
            label = item["label"]
            src_file = item["source_file"]
            relative_path = Path(src_file).relative_to(WORKSPACE)
            clean_desc = extract_clean_description(Path(src_file))
            consensus_lines.append(f"- **{label}** ([{relative_path.name}](file://{src_file}))")
            consensus_lines.append(f"  > {clean_desc}")
            consensus_lines.append("")

        # 5. 读取当前 CLAUDE.md 并替换/追加基因章节
        with open(claude_md_path, "r", encoding="utf-8") as f:
            claude_content = f.read()

        split_token = "## 🧬 Onboarding Consensus"
        if split_token in claude_content:
            parts = claude_content.split(split_token)
            base_content = parts[0].strip()
        else:
            base_content = claude_content.strip()

        new_claude_content = base_content + "\n\n" + "\n".join(consensus_lines)

        # 6. 合规重写 CLAUDE.md (gac- 特权脚本，允许直接写文件)
        # audit-exempt: non-atomic-write — 特权代理原子性豁免 (gac- 前缀白名单)
        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(new_claude_content)

        injected_count = len(selected_consensuses)
        total_count = len(consensuses)
        saved_pct = int((1 - injected_count / max(total_count, 1)) * 100)
        print(
            f"🧬 KOS RAG Consensus Injection: injected {injected_count}/{total_count} genes "
            f"into CLAUDE.md (Token saved ~{saved_pct}%, mode={mode_tag})"
        )
        return 0

    except Exception as e:
        print(f"❌ KOS Consensus Injection Failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
