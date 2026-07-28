"""
Knowledge Graph — شبكة المعرفة.

القسم 8 من المواصفة: "Graph Engine: بناء العلاقات والمعرفة المترابطة."

الفرق عن قاعدة البيانات
-----------------------
الجدول يجيب "أين ورد زرارة؟". الشبكة تجيب:

    من روى عن زرارة وروى عنه ابن أبي عمير؟
    هل أدرك الراوي الآخر زمنياً؟
    ما الروايات المعارضة لهذه في الباب نفسه؟

هذه أسئلة **مسارات** لا مطابقات نصية.

التنفيذ في الذاكرة عمداً
------------------------
لا Neo4j في هذه المرحلة. الشبكة تُبنى من PostgreSQL — وهو مصدر
الحقيقة — وتُعاد بناؤها كاملةً متى شئنا. فهي طبقة **مشتقة** لا
مخزناً موازياً، وهو ما تنص عليه المواصفة. والانتقال إلى Neo4j
لاحقاً لا يغيّر الواجهة: `add_node` و`add_edge` و`neighbours`.

schema_version: 1.0.0
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path as FilePath

GRAPH_VERSION = "1.0.0"


class NodeType(str, Enum):
    NARRATOR = "narrator"
    HADITH = "hadith"
    BOOK = "book"
    CHAPTER = "chapter"
    CONCEPT = "concept"
    SCHOLAR = "scholar"
    OPINION = "opinion"


class EdgeType(str, Enum):
    NARRATED_FROM = "narrated_from"      # راوٍ عن راوٍ
    APPEARS_IN = "appears_in"            # رواية في كتاب
    BELONGS_TO_CHAPTER = "in_chapter"
    DISCUSSES = "discusses"              # رواية تخص مفهوماً
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"
    NARROWS = "narrows"                  # مخصِّص
    ABROGATES = "abrogates"              # ناسخ
    EXPLAINS = "explains"                # شرح
    SUBCONCEPT_OF = "subconcept_of"
    CONTEMPORARY_OF = "contemporary_of"


@dataclass(slots=True)
class Node:
    node_id: str
    node_type: NodeType
    label: str
    attrs: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"id": self.node_id, "type": self.node_type.value,
                "label": self.label, **({"attrs": self.attrs} if self.attrs else {})}


@dataclass(slots=True)
class Edge:
    source: str
    target: str
    edge_type: EdgeType
    weight: float = 1.0
    confidence: float = 1.0
    evidence: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"source": self.source, "target": self.target,
                "type": self.edge_type.value, "weight": round(self.weight, 4),
                "confidence": round(self.confidence, 4), "evidence": self.evidence}


@dataclass(slots=True)
class Path:
    """
    مسار بين عقدتين — جواب سؤال متعدد القفزات.

    ملاحظة: pathlib.Path مستورَدة باسم FilePath في هذه الوحدة، لأن
    Path هنا مفهوم الشبكة لا مسار الملف.
    """

    nodes: list[str]
    edges: list[EdgeType]
    confidence: float = 1.0

    @property
    def hops(self) -> int:
        return len(self.edges)

    def as_dict(self) -> dict:
        return {"nodes": self.nodes, "edges": [e.value for e in self.edges],
                "hops": self.hops, "confidence": round(self.confidence, 4)}


class KnowledgeGraph:
    """
    شبكة موجَّهة بأوزان وثقة.

    كل حافة تحمل `evidence`: معرّفات العناصر التي أثبتتها. فلا علاقة
    بلا دليل — وهو مبدأ المواصفة نفسه مطبَّقاً على الشبكة.
    """

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self._out: dict[str, list[Edge]] = defaultdict(list)
        self._in: dict[str, list[Edge]] = defaultdict(list)
        self.version = GRAPH_VERSION

    # -----------------------------------------------------------------
    def add_node(self, node_id: str, node_type: NodeType, label: str,
                 **attrs) -> Node:
        existing = self.nodes.get(node_id)
        if existing is not None:
            existing.attrs.update(attrs)
            return existing
        node = Node(node_id, node_type, label, dict(attrs))
        self.nodes[node_id] = node
        return node

    def add_edge(self, source: str, target: str, edge_type: EdgeType, *,
                 weight: float = 1.0, confidence: float = 1.0,
                 evidence: list[str] | None = None) -> Edge:
        edge = Edge(source, target, edge_type, weight, confidence,
                    list(evidence or []))
        # الحافة المكرّرة تُقوَّى ولا تُضاعَف: تكرار الرواية دليل تعاضد
        for existing in self._out[source]:
            if existing.target == target and existing.edge_type is edge_type:
                existing.weight += weight
                existing.confidence = max(existing.confidence, confidence)
                for ev in edge.evidence:
                    if ev not in existing.evidence:
                        existing.evidence.append(ev)
                return existing
        self._out[source].append(edge)
        self._in[target].append(edge)
        return edge

    # -----------------------------------------------------------------
    def neighbours(self, node_id: str, edge_type: EdgeType | None = None,
                   *, incoming: bool = False) -> list[Edge]:
        edges = self._in[node_id] if incoming else self._out[node_id]
        if edge_type is None:
            return list(edges)
        return [e for e in edges if e.edge_type is edge_type]

    def find_paths(self, source: str, target: str, *, max_hops: int = 4,
                   limit: int = 10) -> list[Path]:
        """
        كل المسارات من عقدة إلى أخرى.

        هذا ما يجيب "من روى عن زرارة وروى عنه ابن أبي عمير": مسار
        من زرارة إلى ابن أبي عمير عبر وسيط واحد.
        """
        if source not in self.nodes or target not in self.nodes:
            return []

        found: list[Path] = []
        queue: deque = deque([(source, [source], [], 1.0)])

        while queue and len(found) < limit:
            current, path_nodes, path_edges, conf = queue.popleft()
            if len(path_edges) >= max_hops:
                continue
            for edge in self._out[current]:
                if edge.target in path_nodes:
                    continue  # لا دورات
                new_conf = conf * edge.confidence
                if edge.target == target:
                    found.append(Path(path_nodes + [target],
                                      path_edges + [edge.edge_type],
                                      round(new_conf, 4)))
                    if len(found) >= limit:
                        break
                else:
                    queue.append((edge.target, path_nodes + [edge.target],
                                  path_edges + [edge.edge_type], new_conf))

        return sorted(found, key=lambda p: (p.hops, -p.confidence))

    def common_neighbours(self, a: str, b: str,
                          edge_type: EdgeType | None = None) -> list[str]:
        """من يصل بين اثنين — أساس أسئلة الطبقات والمعاصرة."""
        na = {e.target for e in self.neighbours(a, edge_type)}
        nb = {e.target for e in self.neighbours(b, edge_type)}
        return sorted(na & nb)

    def subgraph(self, node_id: str, *, depth: int = 2) -> dict:
        """جوار عقدة إلى عمق محدد — لعرضه في التقرير."""
        seen = {node_id}
        frontier = [node_id]
        edges: list[Edge] = []
        for _ in range(depth):
            nxt: list[str] = []
            for current in frontier:
                for edge in self._out[current] + self._in[current]:
                    edges.append(edge)
                    for end in (edge.source, edge.target):
                        if end not in seen:
                            seen.add(end)
                            nxt.append(end)
            frontier = nxt
        return {
            "root": node_id,
            "nodes": [self.nodes[n].as_dict() for n in seen if n in self.nodes],
            "edges": [e.as_dict() for e in edges],
        }

    # -----------------------------------------------------------------
    def stats(self) -> dict:
        by_type: dict[str, int] = defaultdict(int)
        for n in self.nodes.values():
            by_type[n.node_type.value] += 1
        edge_count = sum(len(v) for v in self._out.values())
        return {"nodes": len(self.nodes), "edges": edge_count,
                "by_type": dict(by_type), "version": self.version}

    def save(self, path: str | FilePath) -> None:
        p = FilePath(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "schema_version": self.version,
            "nodes": [n.as_dict() for n in self.nodes.values()],
            "edges": [e.as_dict() for v in self._out.values() for e in v],
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | FilePath) -> "KnowledgeGraph":
        g = cls()
        p = FilePath(path)
        if not p.exists():
            return g
        data = json.loads(p.read_text(encoding="utf-8"))
        for n in data.get("nodes", []):
            g.add_node(n["id"], NodeType(n["type"]), n["label"],
                       **(n.get("attrs") or {}))
        for e in data.get("edges", []):
            g.add_edge(e["source"], e["target"], EdgeType(e["type"]),
                       weight=e.get("weight", 1.0),
                       confidence=e.get("confidence", 1.0),
                       evidence=e.get("evidence", []))
        return g


__all__ = ["GRAPH_VERSION", "Edge", "EdgeType", "KnowledgeGraph", "Node",
           "NodeType", "Path"]
