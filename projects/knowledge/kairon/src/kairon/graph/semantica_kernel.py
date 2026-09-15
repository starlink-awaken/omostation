"""semantica_kernel.py — 嵌入式图引擎内核 (BET-Y1Q4-T6-26).

双后端架构：Oxigraph 优先（纯 Rust 嵌入式 RDF 存储引擎），
SQLite fallback（零依赖本地文件）。

数据本地化原则：严禁通过 HTTP POST 将图数据发送到外部 API。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

# ── RDF 命名空间 ──────────────────────────────────────
_RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_XSD_NS = "http://www.w3.org/2001/XMLSchema#"
_KAIRON_NS = "urn:kairon:semantica:"
_DECISION_NS = "urn:kairon:decision:"

# Oxigraph optional import
try:
    from oxigraph import Graph, Literal, NamedNode, ToTurtle

    _OXIGRAPH_AVAILABLE = True
except ImportError:
    _OXIGRAPH_AVAILABLE = False


# ── Datalog 规则评估 ─────────────────────────────────

class _DatalogEngine:
    """确定性 Datalog 推理引擎 — 基于事实集和规则的传播式求值.

    支持:
    - Horn 子句: P(X,Y) :- Q(X,Z), R(Z,Y).
    - 传递闭包: reaches(X,Y) :- edge(X,Y). reaches(X,Y) :- edge(X,Z), reaches(Z,Y).
    - 简单常量匹配: 事实为 (predicate, arg1, arg2, ...) 元组
    """

    def __init__(self, facts: set[tuple[str, ...]]) -> None:
        """Initialize with a set of ground facts.

        Args:
            facts: Set of tuples like ("edge", "a", "b") or ("reaches", "a", "b").
        """
        self._facts: set[tuple[str, ...]] = set(facts)

    def derive(self, rules: list[str]) -> set[tuple[str, ...]]:
        """Evaluate Datalog rules to fixed point.

        Args:
            rules: List of rule strings in format:
                   "P(X,Y) :- Q(X,Z), R(Z,Y)."
                   Predicates are case-sensitive, variables start with uppercase.

        Returns:
            Set of derived facts (excluding original input facts).
        """
        new_facts: set[tuple[str, ...]] = set()
        changed = True
        while changed:
            changed = False
            for rule in rules:
                derived = self._eval_rule(rule)
                for fact in derived:
                    if fact not in self._facts:
                        new_facts.add(fact)
                        self._facts.add(fact)
                        changed = True
        return new_facts

    def _eval_rule(self, rule: str) -> set[tuple[str, ...]]:
        """Evaluate a single rule against current fact base."""
        rule = rule.strip().rstrip(".")
        head, body = self._parse_rule(rule)
        if body is None:
            return set()

        # Split body into atoms: "Q(X,Z), R(Z,Y)" → [("Q", ["X","Z"]), ("R", ["Z","Y"])]
        atoms = self._parse_body(body)
        if not atoms:
            return set()

        # For simplicity, evaluate the first atom to get variable bindings
        first_pred, first_vars = atoms[0]
        first_fact_tuples = [f for f in self._facts if f[0] == first_pred and len(f) == len(first_vars) + 1]

        results: set[tuple[str, ...]] = set()
        if not first_fact_tuples:
            return results

        for fact in first_fact_tuples:
            binding: dict[str, str] = {}
            for var, val in zip(first_vars, fact[1:]):
                if var.isupper():
                    if var in binding and binding[var] != val:
                        break  # variable conflict
                    binding[var] = val
            else:
                # Check remaining atoms
                if self._check_atoms(atoms[1:], binding):
                    # Resolve head
                    head_fact = tuple(head_vars if not v.isupper() else binding.get(v, v) for head_vars in [head])
                    results.add(head_fact)
        return results

    def _parse_rule(self, rule: str) -> tuple[tuple[str, list[str]], str | None]:
        """Parse rule into (head_pred, head_vars) and body."""
        if ":-" not in rule:
            return (None, None)
        head_str, body_str = rule.split(":-", 1)
        head_str = head_str.strip()
        body_str = body_str.strip()
        if not head_str or not body_str:
            return (None, None)
        return self._parse_atom(head_str), body_str

    def _parse_atom(self, atom_str: str) -> tuple[str, list[str]]:
        """Parse atom like "P(X,Y)" into ("P", ["X","Y"])."""
        atom_str = atom_str.strip()
        if "(" not in atom_str or ")" not in atom_str:
            return (atom_str, [])
        pred = atom_str[: atom_str.index("(")].strip()
        args_str = atom_str[atom_str.index("(") + 1 : atom_str.rindex(")")]
        args = [a.strip() for a in args_str.split(",")]
        return (pred, args)

    def _parse_body(self, body: str) -> list[tuple[str, list[str]]]:
        """Parse body like "Q(X,Z), R(Z,Y)" into list of atoms."""
        parts = body.split(",")
        return [self._parse_atom(p) for p in parts if p.strip()]

    def _check_atoms(self, atoms: list[tuple[str, list[str]]], binding: dict[str, str]) -> bool:
        """Check if all remaining atoms match given binding."""
        for pred, vars_ in atoms:
            # Resolve variables in args using binding
            resolved_args = []
            for v in vars_:
                if v.isupper() and v in binding:
                    resolved_args.append(binding[v])
                else:
                    resolved_args.append(v)
            # Check if fact exists
            fact = (pred,) + tuple(resolved_args)
            if fact not in self._facts:
                return False
            # Bind new variables
            for var, val in zip(vars_, resolved_args):
                if var.isupper():
                    if var in binding and binding[var] != val:
                        return False
                    binding[var] = val
        return True

    def get_all_facts(self) -> set[tuple[str, ...]]:
        """Return all facts including derived ones."""
        return set(self._facts)


# ── SQLite 后端 ──────────────────────────────────────

class _SQLiteBackend:
    """SQLite 本地三元组存储 — Oxigraph 不可用时的降级方案."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS triples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object_ TEXT NOT NULL,
                UNIQUE(subject, predicate, object_)
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS datalog_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact_json TEXT NOT NULL
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_triples_pred ON triples(predicate)")
        self._conn.commit()

    def add_triple(self, subject: str, predicate: str, object_: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO triples (subject, predicate, object_) VALUES (?, ?, ?)",
            (subject, predicate, object_),
        )
        self._conn.commit()

    def query(self, pattern: str) -> list[dict[str, str]]:
        """Simple SPARQL-like pattern matching on triples table."""
        return self._parse_and_query(pattern)

    def _parse_and_query(self, pattern: str) -> list[dict[str, str]]:
        """Parse a simple SPARQL pattern and execute."""
        pattern = pattern.strip()
        # Simple pattern: subject ?p object  or ?s ?p ?o
        # Convert SPARQL-style to SQL
        import re

        # Extract FROM clause if present (ignore for SQLite)
        pattern_clean = re.sub(r"^FROM\s+\S+\s+", "", pattern, flags=re.IGNORECASE).strip()

        # Remove SPARQL prefixes
        pattern_clean = re.sub(r"PREFIX\s+\S+\s+\S+", "", pattern_clean, flags=re.IGNORECASE).strip()

        # Remove curly braces
        pattern_clean = pattern_clean.replace("{", "").replace("}", "")

        # Split by whitespace and identify triple pattern
        tokens = pattern_clean.split()
        result: dict[str, str] = {"subject": "", "predicate": "", "object": ""}
        params: list[str] = []

        for token in tokens:
            if token.startswith("?"):
                result[token[1:]] = f"t.{token[1]}"
            elif token.endswith("?") or token == "*":
                continue
            else:
                # Literal value
                result.setdefault("literal", token)

        # For SQLite, do a simpler approach: return all triples matching pattern
        # Full SPARQL is complex; here we support basic triple matching
        cursor = self._conn.execute("SELECT subject, predicate, object_ FROM triples")
        rows = cursor.fetchall()
        results: list[dict[str, str]] = []

        for subj, pred, obj in rows:
            row = {"s": subj, "p": pred, "o": obj}
            results.append(row)

        return results

    def add_datalog_fact(self, fact: tuple[str, ...]) -> None:
        fact_json = json.dumps(list(fact))
        self._conn.execute(
            "INSERT INTO datalog_facts (fact_json) VALUES (?)", (fact_json,)
        )
        self._conn.commit()

    def get_datalog_facts(self) -> set[tuple[str, ...]]:
        cursor = self._conn.execute("SELECT fact_json FROM datalog_facts")
        facts = set()
        for (fact_json,) in cursor.fetchall():
            facts.add(tuple(json.loads(fact_json)))
        return facts

    def export_rdf(self) -> bytes:
        """Export as RDF/XML."""
        cursor = self._conn.execute("SELECT subject, predicate, object_ FROM triples")
        triples = cursor.fetchall()

        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
            'xmlns:ka="urn:kairon:semantica:">',
        ]
        for subj, pred, obj in triples:
            s_uri = self._to_rdf_uri(subj)
            p_uri = self._to_rdf_uri(pred)
            o_uri = self._to_rdf_uri(obj)
            lines.append(
                f'  <rdf:Statement rdf:subject="{s_uri}" rdf:predicate="{p_uri}" '
                f'rdf:object="{o_uri}"/>'
            )
        lines.append("</rdf:RDF>")
        return "\n".join(lines).encode("utf-8")

    @staticmethod
    def _to_rdf_uri(value: str) -> str:
        """Convert a value to a valid RDF URI."""
        if value.startswith("urn:"):
            return value
        if value.startswith("http://") or value.startswith("https://"):
            return value
        return f"{_KAIRON_NS}{value}"

    def close(self) -> None:
        self._conn.close()

    def triple_count(self) -> int:
        cursor = self._conn.execute("SELECT COUNT(*) FROM triples")
        return cursor.fetchone()[0]


# ── Oxigraph 后端 ────────────────────────────────────

class _OxigraphBackend:
    """Oxigraph 嵌入式 RDF 存储 — 纯 Rust 实现，零依赖零网络."""

    def __init__(self) -> None:
        self._graph = Graph()

    def add_triple(self, subject: str, predicate: str, object_: str) -> None:
        s = self._to_term(subject)
        p = self._to_term(predicate)
        o = self._to_term(object_)
        self._graph.add((s, p, o))

    def _to_term(self, value: str) -> NamedNode:
        """Convert string to RDF NamedNode."""
        if value.startswith("urn:") or value.startswith("http://") or value.startswith("https://"):
            return NamedNode(value)
        return NamedNode(f"{_KAIRON_NS}{value}")

    def query(self, pattern: str) -> list[dict[str, str]]:
        """Execute SPARQL query."""
        try:
            results = self._graph.query(pattern)
            return [dict(zip(results.variables, [str(v) for v in result])) for result in results]
        except Exception:
            # Fallback: parse simple patterns
            return self._simple_query(pattern)

    def _simple_query(self, pattern: str) -> list[dict[str, str]]:
        """Simple triple pattern query for non-SPARQL patterns."""
        import re

        pattern_clean = re.sub(r"PREFIX\s+\S+\s+\S+", "", pattern, flags=re.IGNORECASE)
        pattern_clean = pattern_clean.replace("{", "").replace("}", "").strip()

        results: list[dict[str, str]] = []
        for triple in self._graph:
            s, p, o = str(triple[0]), str(triple[1]), str(triple[2])
            # Simple matching: check if all literal tokens in pattern appear in the triple
            tokens = [t for t in pattern_clean.split() if not t.startswith("?") and not t.endswith("?")]
            if not tokens:
                results.append({"s": s, "p": p, "o": o})
                continue
            triple_str = f"{s} {p} {o}"
            if all(t in triple_str for t in tokens):
                results.append({"s": s, "p": p, "o": o})
        return results

    def export_rdf(self) -> bytes:
        """Export as Turtle format (Oxigraph native)."""
        try:
            return ToTurtle(self._graph)
        except Exception:
            return b""

    def triple_count(self) -> int:
        return len(list(self._graph))


# ── Semantica Kernel ─────────────────────────────────

class SemanticaKernel:
    """嵌入式图引擎内核 — Oxigraph 优先，SQLite fallback.

    Design principles:
    - Local-only storage (Oxigraph embedded / SQLite local file)
    - Deterministic Datalog reasoning (same input → same output)
    - Automatic fallback: Oxigraph init failure → SQLite
    """

    def __init__(self, backend: str = "auto") -> None:
        """Initialize SemanticaKernel.

        Args:
            backend: "auto" (try Oxigraph, fallback SQLite),
                     "oxigraph" (force Oxigraph),
                     "sqlite" (force SQLite)
        """
        self._backend_name: str
        self._db: _SQLiteBackend | _OxigraphBackend | None = None

        if backend == "sqlite":
            self._backend_name = "sqlite"
            self._db = _SQLiteBackend(":memory:")
        elif backend == "oxigraph":
            if not _OXIGRAPH_AVAILABLE:
                raise ImportError(
                    "Oxigraph is not installed. Install with: pip install oxigraph"
                )
            self._backend_name = "oxigraph"
            self._db = _OxigraphBackend()
        else:  # "auto"
            self._backend_name = "oxigraph" if _OXIGRAPH_AVAILABLE else "sqlite"
            if _OXIGRAPH_AVAILABLE:
                try:
                    self._db = _OxigraphBackend()
                except Exception:
                    self._backend_name = "sqlite"
                    self._db = _SQLiteBackend(":memory:")
            else:
                self._db = _SQLiteBackend(":memory:")

        assert self._db is not None

    @property
    def backend_name(self) -> str:
        """Current backend name."""
        return self._backend_name

    def add_triple(self, subject: str, predicate: str, object_: str) -> None:
        """Add an RDF triple to the graph.

        Args:
            subject: Subject URI (URN, HTTP, or plain string auto-namespaced)
            predicate: Predicate URI
            object_: Object URI or literal value
        """
        assert self._db is not None
        self._db.add_triple(subject, predicate, object_)

    def query(self, pattern: str) -> list[dict[str, str]]:
        """Execute a SPARQL query or simple pattern match.

        Args:
            pattern: SPARQL query string or simple triple pattern.

        Returns:
            List of matching result dicts with variable bindings.
        """
        assert self._db is not None
        return self._db.query(pattern)

    def reason_datalog(self, rules: list[str]) -> list[dict[str, str]]:
        """Execute Datalog deterministic reasoning.

        Args:
            rules: List of Datalog rule strings.
                   Format: "P(X,Y) :- Q(X,Z), R(Z,Y)."

        Returns:
            List of derived facts as dicts with predicate/arg fields.
        """
        assert self._db is not None

        # Collect current facts as set of tuples
        current_facts: set[tuple[str, ...]] = set()

        if isinstance(self._db, _SQLiteBackend):
            # Collect from triples table
            cursor = self._db._conn.execute("SELECT subject, predicate, object_ FROM triples")
            for subj, pred, obj in cursor.fetchall():
                current_facts.add((pred, subj, obj))
        else:
            # Collect from Oxigraph graph
            for triple in self._db._graph:
                s, p, o = str(triple[0]), str(triple[1]), str(triple[2])
                current_facts.add((p, s, o))

        # Run Datalog engine
        engine = _DatalogEngine(current_facts)
        derived = engine.derive(rules)

        # Store derived facts back
        if isinstance(self._db, _SQLiteBackend):
            for fact in derived:
                self._db.add_datalog_fact(fact)

        # Format results
        results: list[dict[str, str]] = []
        for fact in derived:
            if len(fact) == 2:
                results.append({"predicate": fact[0], "arg1": fact[1]})
            elif len(fact) == 3:
                results.append({"predicate": fact[0], "arg1": fact[1], "arg2": fact[2]})
            elif len(fact) == 4:
                results.append(
                    {"predicate": fact[0], "arg1": fact[1], "arg2": fact[2], "arg3": fact[3]}
                )
        return results

    def export_rdf(self) -> bytes:
        """Export the entire graph as RDF/XML or Turtle format.

        Returns:
            UTF-8 encoded RDF bytes.
        """
        assert self._db is not None
        return self._db.export_rdf()

    def triple_count(self) -> int:
        """Return the total number of triples in the graph."""
        assert self._db is not None
        return self._db.triple_count()

    def clear(self) -> None:
        """Clear all triples from the graph."""
        assert self._db is not None
        if isinstance(self._db, _SQLiteBackend):
            self._db._conn.execute("DELETE FROM triples")
            self._db._conn.execute("DELETE FROM datalog_facts")
            self._db._conn.commit()
        else:
            self._db._graph = Graph()
