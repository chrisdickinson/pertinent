#!/usr/bin/env python3
"""Visually simplify Graphviz DOT graphs without losing information.

Parses DOT with the standard library, applies simplification passes, and
writes DOT. Text removed from visible labels moves into tooltips, so an SVG
render still shows it on hover.

    simplify_dot.py stats IN.dot
    simplify_dot.py simplify IN.dot -o OUT.dot [--preset tidy|overview|none] ...

Passes, in the order they run:
    hoist           move edges written inside a cluster body, whose endpoint is
                    declared in another cluster, to the root graph (graphviz
                    otherwise draws that endpoint inside the wrong cluster)
    focus           keep only nodes within --depth hops of --focus nodes
    collapse        replace --collapse clusters with one summary node each
    drop-undirected drop dir=none association edges
    merge-parallel  merge edges that share tail, head, dir and style
    detail          strip monospace / smaller-than-base <font> runs from HTML
                    node labels (monospace only for graph and cluster labels)
    label-lines     cap node labels at --label-lines lines
    edge-labels     shorten edge labels to the first line (--edge-label-max)
    chains          merge runs of 1-in/1-out nodes in one cluster into one node
    tred            drop unlabeled edges implied by another path
"""
from __future__ import annotations

import argparse
import difflib
import html
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

PASS_ORDER = [
    "hoist", "focus", "collapse", "drop-undirected", "merge-parallel",
    "detail", "label-lines", "edge-labels", "chains", "tred",
]
PRESETS = {
    "none": [],
    "tidy": ["hoist", "detail", "merge-parallel", "edge-labels"],
    "overview": ["hoist", "drop-undirected", "merge-parallel", "detail",
                 "label-lines", "edge-labels", "chains", "tred"],
}
PRESET_DEFAULTS = {
    "none": {},
    "tidy": {"edge_label_max": 40},
    "overview": {"edge_label_max": 24, "label_lines": 3},
}

KEYWORDS = {"strict", "graph", "digraph", "subgraph", "node", "edge"}
ID_RE = re.compile(r"[A-Za-z_\u0080-\uffff][A-Za-z0-9_\u0080-\uffff]*|-?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)")


class DotError(Exception):
    pass


# --------------------------------------------------------------------------- AST
#
# eq=False everywhere: statements are compared by identity, so removing one
# statement from a list never removes an identical-looking sibling.


@dataclass(eq=False)
class Val:
    kind: str  # "id" | "q" (quoted; escapes kept raw) | "html" (no outer <>)
    raw: str

    def emit(self) -> str:
        if self.kind == "html":
            return f"<{self.raw}>"
        if self.kind == "q":
            return f'"{self.raw}"'
        return self.raw


@dataclass(eq=False)
class Attrs:
    items: list = field(default_factory=list)  # [(key, Val)]

    def get(self, key: str) -> Optional[Val]:
        for k, v in reversed(self.items):
            if k == key:
                return v
        return None

    def set(self, key: str, val: Val) -> None:
        """Replace the first `key` in place (dropping duplicates), else append."""
        pos = next((i for i, (k, _) in enumerate(self.items) if k == key), None)
        self.pop(key)
        if pos is None:
            self.items.append((key, val))
        else:
            self.items.insert(pos, (key, val))

    def pop(self, key: str) -> None:
        self.items = [(k, v) for k, v in self.items if k != key]

    def copy(self) -> "Attrs":
        return Attrs(list(self.items))


@dataclass(eq=False)
class AttrStmt:
    kind: str  # graph | node | edge
    attrs: Attrs


@dataclass(eq=False)
class Assign:
    key: str
    val: Val


@dataclass(eq=False)
class End:
    id: str
    port: Optional[str]
    idval: Val


@dataclass(eq=False)
class NodeStmt:
    id: str
    port: Optional[str]
    attrs: Attrs
    idval: Val


@dataclass(eq=False)
class EdgeStmt:
    tail: End
    head: End
    attrs: Attrs


@dataclass(eq=False)
class Subgraph:
    name: Optional[str]
    stmts: list
    keyword: bool
    nameval: Optional[Val]


@dataclass(eq=False)
class Graph:
    strict: bool
    directed: bool
    name: Optional[Val]
    stmts: list


# ------------------------------------------------------------------ tokenizer

TOKEN_RE = re.compile(
    r"(?P<ws>\s+)|(?P<lcomment>//[^\n]*)|(?P<bcomment>/\*.*?\*/)"
    r"|(?P<edgeop>->|--)|(?P<punct>[{}\[\]=;,:+])|(?P<id>" + ID_RE.pattern + ")",
    re.S,
)


def tokenize(src: str) -> list:
    toks, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            if j >= n:
                raise DotError(f"line {src.count(chr(10), 0, i) + 1}: unterminated string")
            toks.append(("q", src[i + 1:j], i))
            i = j + 1
            continue
        if c == "<":
            depth, j = 0, i
            while j < n:
                if src[j] == "<":
                    depth += 1
                elif src[j] == ">":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if j >= n:
                raise DotError(f"line {src.count(chr(10), 0, i) + 1}: unterminated HTML string")
            toks.append(("html", src[i + 1:j], i))
            i = j + 1
            continue
        if c == "#" and (i == 0 or src[i - 1] == "\n"):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        m = TOKEN_RE.match(src, i)
        if not m:
            raise DotError(f"line {src.count(chr(10), 0, i) + 1}: unexpected {c!r}")
        if m.lastgroup not in ("ws", "lcomment", "bcomment"):
            toks.append((m.lastgroup, m.group(), i))
        i = m.end()
    return toks


# --------------------------------------------------------------------- parser


class Parser:
    def __init__(self, src: str):
        self.src = src
        self.toks = tokenize(src)
        self.i = 0

    def peek(self, k: int = 0) -> tuple:
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else ("eof", "", len(self.src))

    def next(self) -> tuple:
        t = self.peek()
        self.i += 1
        return t

    def at(self, kind: str, text: Optional[str] = None, k: int = 0) -> bool:
        t = self.peek(k)
        return t[0] == kind and (text is None or t[1] == text)

    def accept(self, kind: str, text: Optional[str] = None) -> bool:
        if self.at(kind, text):
            self.i += 1
            return True
        return False

    def expect(self, kind: str, text: str) -> None:
        if not self.accept(kind, text):
            self.error(f"expected {text!r}")

    def at_kw(self, *words: str, k: int = 0) -> bool:
        t = self.peek(k)
        return t[0] == "id" and t[1].lower() in words

    def error(self, msg: str):
        t = self.peek()
        raise DotError(f"line {self.src.count(chr(10), 0, t[2]) + 1}: {msg}, got {t[1]!r}")

    def parse(self) -> Graph:
        strict = False
        if self.at_kw("strict"):
            self.next()
            strict = True
        if not self.at_kw("graph", "digraph"):
            self.error("expected graph or digraph")
        directed = self.next()[1].lower() == "digraph"
        name = self.value() if self.peek()[0] in ("id", "q", "html") else None
        self.expect("punct", "{")
        stmts = self.stmt_list()
        self.expect("punct", "}")
        return Graph(strict, directed, name, stmts)

    def value(self) -> Val:
        t = self.next()
        if t[0] == "id":
            return Val("id", t[1])
        if t[0] == "html":
            return Val("html", t[1])
        if t[0] == "q":
            raw = t[1]
            while self.at("punct", "+") and self.at("q", k=1):
                self.next()
                raw += self.next()[1]
            return Val("q", raw)
        self.i -= 1
        self.error("expected a value")

    def stmt_list(self) -> list:
        stmts = []
        while not self.at("punct", "}") and not self.at("eof"):
            stmts.extend(self.stmt())
            self.accept("punct", ";")
        return stmts

    def attr_list(self) -> Attrs:
        attrs = Attrs()
        while self.accept("punct", "["):
            while not self.accept("punct", "]"):
                key = self.value()
                val = self.value() if self.accept("punct", "=") else Val("id", "true")
                attrs.items.append((key.raw, val))
                if not self.accept("punct", ","):
                    self.accept("punct", ";")
        return attrs

    def stmt(self) -> list:
        if self.at_kw("graph", "node", "edge") and self.at("punct", "[", k=1):
            return [AttrStmt(self.next()[1].lower(), self.attr_list())]
        if self.at_kw("subgraph") or self.at("punct", "{"):
            sub = self.subgraph()
            return self.edge_rest(sub) if self.at("edgeop") else [sub]
        if self.peek()[0] in ("id", "q", "html"):
            if self.at("punct", "=", k=1):
                key = self.value()
                self.next()
                return [Assign(key.raw, self.value())]
            end = self.node_id()
            if self.at("edgeop"):
                return self.edge_rest(end)
            return [NodeStmt(end.id, end.port, self.attr_list(), end.idval)]
        self.error("expected a statement")

    def node_id(self) -> End:
        v = self.value()
        port = None
        if self.accept("punct", ":"):
            port = self.value().raw
            if self.accept("punct", ":"):
                port += ":" + self.value().raw
        return End(v.raw, port, v)

    def subgraph(self) -> Subgraph:
        keyword, nameval = False, None
        if self.at_kw("subgraph"):
            self.next()
            keyword = True
            if self.peek()[0] in ("id", "q"):
                nameval = self.value()
        self.expect("punct", "{")
        stmts = self.stmt_list()
        self.expect("punct", "}")
        return Subgraph(nameval.raw if nameval else None, stmts, keyword, nameval)

    def edge_rest(self, first) -> list:
        ends = [first]
        while self.accept("edgeop"):
            if self.at_kw("subgraph") or self.at("punct", "{"):
                ends.append(self.subgraph())
            else:
                ends.append(self.node_id())
        attrs = self.attr_list()
        out = [e for e in ends if isinstance(e, Subgraph)]
        for a, b in zip(ends, ends[1:]):
            for x in _members(a):
                for y in _members(b):
                    out.append(EdgeStmt(x, y, attrs.copy()))
        return out


def _members(end) -> list:
    if isinstance(end, End):
        return [end]
    return [End(s.id, s.port, s.idval) for s in end.stmts if isinstance(s, NodeStmt)]


def parse(src: str) -> Graph:
    return Parser(src).parse()


# -------------------------------------------------------------------- emitter


def emit_attrs(attrs: Attrs, indent: int) -> str:
    if not attrs.items:
        return ""
    parts = [f"{k}={v.emit()}" for k, v in attrs.items]
    one = " [" + ", ".join(parts) + "]"
    if len(one) <= 100 and "\n" not in one:
        return one
    pad = "  " * (indent + 1)
    return " [\n" + ",\n".join(pad + p for p in parts) + "\n" + "  " * indent + "]"


def emit_end(e: End) -> str:
    return e.idval.emit() + (f":{e.port}" if e.port else "")


def emit_stmts(stmts: list, indent: int, out: list, op: str) -> None:
    pad = "  " * indent
    for s in stmts:
        if isinstance(s, AttrStmt):
            out.append(f"{pad}{s.kind}{emit_attrs(s.attrs, indent)};")
        elif isinstance(s, Assign):
            out.append(f"{pad}{s.key}={s.val.emit()};")
        elif isinstance(s, NodeStmt):
            port = f":{s.port}" if s.port else ""
            out.append(f"{pad}{s.idval.emit()}{port}{emit_attrs(s.attrs, indent)};")
        elif isinstance(s, EdgeStmt):
            out.append(f"{pad}{emit_end(s.tail)} {op} {emit_end(s.head)}{emit_attrs(s.attrs, indent)};")
        elif isinstance(s, Subgraph):
            head = "subgraph " if s.keyword else ""
            name = s.nameval.emit() + " " if s.nameval else ""
            out.append(f"{pad}{head}{name}{{")
            emit_stmts(s.stmts, indent + 1, out, op)
            out.append(f"{pad}}}")


def emit(g: Graph, comment: Optional[str] = None) -> str:
    out = [f"// {line}" for line in (comment or "").splitlines()]
    kw = ("strict " if g.strict else "") + ("digraph" if g.directed else "graph")
    out.append(f"{kw} {g.name.emit() + ' ' if g.name else ''}{{")
    emit_stmts(g.stmts, 1, out, "->" if g.directed else "--")
    out.append("}")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- traversal


@dataclass
class Ctx:
    path: tuple  # enclosing Subgraphs, outermost first
    ndefs: dict  # node defaults in effect
    edefs_local: dict  # edge defaults set by non-root scopes


def walk(stmts: list, path: tuple = (), ndefs=None, edefs_local=None) -> Iterator[tuple]:
    """Yield (stmt, containing list, Ctx) in document order."""
    ndefs = dict(ndefs or {})
    edefs_local = dict(edefs_local or {})
    for s in list(stmts):
        if isinstance(s, AttrStmt) and s.kind == "node":
            ndefs.update(dict(s.attrs.items))
        elif isinstance(s, AttrStmt) and s.kind == "edge" and path:
            edefs_local.update(dict(s.attrs.items))
        yield s, stmts, Ctx(path, ndefs, edefs_local)
        if isinstance(s, Subgraph):
            yield from walk(s.stmts, path + (s,), ndefs, edefs_local)


def is_cluster(sg: Subgraph) -> bool:
    if sg.name and sg.name.startswith("cluster"):
        return True
    return any(isinstance(s, Assign) and s.key == "cluster" and s.val.raw == "true" for s in sg.stmts)


def innermost_cluster(path: tuple) -> Optional[Subgraph]:
    for sg in reversed(path):
        if is_cluster(sg):
            return sg
    return None


class Index:
    def __init__(self, g: Graph):
        self.home: dict = {}   # node id -> path of its first node statement
        self.first: dict = {}  # node id -> path of its first mention
        self.decls: dict = defaultdict(list)
        self.nodes: list = []
        self.edges: list = []
        self.subgraphs: list = []
        for s, lst, ctx in walk(g.stmts):
            if isinstance(s, NodeStmt):
                self.nodes.append((s, lst, ctx))
                self.decls[s.id].append(s)
                self.home.setdefault(s.id, ctx.path)
                self.first.setdefault(s.id, ctx.path)
            elif isinstance(s, EdgeStmt):
                self.edges.append((s, lst, ctx))
                for e in (s.tail, s.head):
                    self.first.setdefault(e.id, ctx.path)
            elif isinstance(s, Subgraph):
                self.subgraphs.append((s, lst, ctx))

    def home_of(self, nid: str) -> tuple:
        return self.home.get(nid, self.first.get(nid, ()))

    def ids(self) -> list:
        return list(self.first)


def remove(lst: list, stmt) -> None:
    for i, s in enumerate(lst):
        if s is stmt:
            del lst[i]
            return


# --------------------------------------------------------------- label text

Q_BREAK = re.compile(r"\\[nlr]")
HTML_TOK = re.compile(r"<[^<>]*>|[^<]+")
TAG_RE = re.compile(r"<\s*(/)?\s*([A-Za-z][A-Za-z0-9]*)([^>]*?)(/)?\s*>", re.S)
SELF_CLOSING = {"br", "hr", "vr", "img"}
MONO_RE = re.compile(r"mono|menlo|courier|consolas|monaco|typewriter", re.I)


def escape_q(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def unescape_q(s: str) -> str:
    return re.sub(r'\\(["\\])', r"\1", s)


def q_val(text: str) -> Val:
    return Val("q", escape_q(text))


def id_val(s: str) -> Val:
    if ID_RE.fullmatch(s) and s.lower() not in KEYWORDS:
        return Val("id", s)
    return q_val(s)


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class Tag:
    name: str
    closing: bool
    selfclosing: bool
    attrs: dict


def tag_info(tok: str) -> Optional[Tag]:
    if not tok.startswith("<"):
        return None
    m = TAG_RE.fullmatch(tok)
    if not m:
        return None
    name = m.group(2).lower()
    attrs = {k.lower(): v for k, v in re.findall(r'([A-Za-z-]+)\s*=\s*"([^"]*)"', m.group(3))}
    return Tag(name, bool(m.group(1)), bool(m.group(4)) or name in SELF_CLOSING, attrs)


def html_lines(raw: str) -> list:
    lines = [""]
    for tok in HTML_TOK.findall(raw):
        t = tag_info(tok)
        if t:
            if t.name == "br" or (t.name == "tr" and t.closing):
                lines.append("")
            continue
        lines[-1] += html.unescape(tok)
    return [clean(line) for line in lines if clean(line)]


def visible_lines(v: Optional[Val]) -> list:
    if v is None:
        return []
    if v.kind == "html":
        return html_lines(v.raw)
    if v.kind == "q":
        return [clean(unescape_q(p)) for p in Q_BREAK.split(v.raw) if clean(unescape_q(p))]
    return [v.raw]


def node_lines(n: NodeStmt) -> list:
    label = n.attrs.get("label")
    if label is None or label.raw == "\\N":
        return [n.id]
    return visible_lines(label)


def already_in(line: str, text: str) -> bool:
    """True when `line` (or every path-like token in it, by basename) is in `text`."""
    if line in text:
        return True
    paths = [t for t in re.split(r"[\s·,;()]+", line) if "/" in t or re.search(r"\.\w+:\d", t)]
    if not paths or not all(t.rstrip(":").rsplit("/", 1)[-1] in text for t in paths):
        return False
    residue = re.sub(r"\S*[/.]\S*|:?\d+\b|[\s·,;():]+", "", line)
    return not residue


def add_to_tooltip(attrs: Attrs, lines: list, prepend: bool = False) -> int:
    """Add the lines missing from the tooltip. Returns how many were added."""
    cur = attrs.get("tooltip")
    cur_text = "\n".join(visible_lines(cur))
    new = []
    for line in lines:
        if line and not already_in(line, cur_text) and line not in new:
            new.append(line)
    if not new:
        return 0
    add = "\\n".join(escape_q(line) for line in new)
    if cur is None or not cur.raw:
        raw = add
    else:
        raw = add + "\\n" + cur.raw if prepend else cur.raw + "\\n" + add
    attrs.set("tooltip", Val("q", raw))
    return len(new)


def cleanup_breaks(toks: list) -> list:
    """Drop leading, repeated, and trailing <br/> tokens."""
    out, seen_text = [], False
    for tok in toks:
        t = tag_info(tok)
        if t and t.name == "br":
            if seen_text:
                out.append(tok)
                seen_text = False
        else:
            out.append(tok)
            if not t and tok.strip():
                seen_text = True
    last_text = max((i for i, tok in enumerate(out) if not tag_info(tok) and tok.strip()), default=-1)
    return [tok for i, tok in enumerate(out)
            if i <= last_text or not (tag_info(tok) and tag_info(tok).name == "br")]


def strip_detail_html(raw: str, base_size: float, mono_only: bool) -> tuple:
    """Remove <font> runs set in a monospace face or smaller than base_size.

    Returns (new_raw, removed_lines). new_raw is raw unchanged when nothing
    visible would remain.
    """
    def is_detail(t: Tag) -> bool:
        if MONO_RE.search(t.attrs.get("face", "")):
            return True
        if mono_only:
            return False
        try:
            return float(t.attrs.get("point-size", "inf")) < base_size
        except ValueError:
            return False

    out, moved, skip = [], [""], 0
    for tok in HTML_TOK.findall(raw):
        t = tag_info(tok)
        if skip:
            if t is None:
                moved[-1] += html.unescape(tok)
            elif t.selfclosing:
                if t.name == "br":
                    moved.append("")
            else:
                skip += -1 if t.closing else 1
            continue
        if t and t.name == "font" and not t.closing and not t.selfclosing and is_detail(t):
            skip = 1
            moved.append("")
            continue
        out.append(tok)
    moved = [clean(m) for m in moved if clean(m)]
    if not moved:
        return raw, []
    new = "".join(cleanup_breaks(out))
    if not html_lines(new):
        return raw, []
    return new, moved


def cap_html_lines(raw: str, n: int) -> tuple:
    if re.search(r"<\s*table", raw, re.I):
        return raw, []
    out, stack, moved, count, cutting = [], [], [""], 0, False
    for tok in HTML_TOK.findall(raw):
        t = tag_info(tok)
        if cutting:
            if t is None:
                moved[-1] += html.unescape(tok)
            elif t.name == "br":
                moved.append("")
            continue
        if t and t.name == "br":
            count += 1
            if count >= n:
                cutting = True
                continue
        elif t and not t.selfclosing:
            if t.closing:
                if t.name in stack:
                    while stack and stack.pop() != t.name:
                        pass
            else:
                stack.append(t.name)
        out.append(tok)
    moved = [clean(m) for m in moved if clean(m)]
    if not moved:
        return raw, []
    out.append("…")
    out.extend(f"</{name}>" for name in reversed(stack))
    return "".join(out), moved


def cap_q_lines(raw: str, n: int) -> tuple:
    parts = Q_BREAK.split(raw)
    seps = Q_BREAK.findall(raw)
    if len(parts) <= n:
        return raw, []
    kept = parts[0] + "".join(s + p for s, p in zip(seps[:n - 1], parts[1:n]))
    moved = [clean(unescape_q(p)) for p in parts[n:] if clean(unescape_q(p))]
    return kept + "…", moved


def as_float(v: Optional[Val], default: float) -> float:
    try:
        return float(v.raw) if v is not None else default
    except ValueError:
        return default


# --------------------------------------------------------------------- passes


def insert_after(stmts: list, anchor, new: list) -> None:
    pos = next(i for i, s in enumerate(stmts) if s is anchor) + 1
    stmts[pos:pos] = new


def materialize_edge_defaults(e: EdgeStmt, ctx: Ctx) -> None:
    for k, v in ctx.edefs_local.items():
        if e.attrs.get(k) is None:
            e.attrs.items.append((k, v))


def pass_hoist(g: Graph, idx: Index, opts) -> str:
    moved = defaultdict(list)  # top-level subgraph -> edges hoisted out of it
    for e, lst, ctx in idx.edges:
        c = innermost_cluster(ctx.path)
        if c is None:
            continue
        if not any(end.id in idx.home and c not in idx.home[end.id] for end in (e.tail, e.head)):
            continue
        materialize_edge_defaults(e, ctx)
        remove(lst, e)
        moved[ctx.path[0]].append(e)
    for top, edges in moved.items():
        insert_after(g.stmts, top, edges)
    return f"{sum(map(len, moved.values()))} cross-cluster edges moved to root"


def pass_focus(g: Graph, idx: Index, opts) -> str:
    seeds = [s.strip() for s in opts.focus.split(",") if s.strip()]
    ids = idx.ids()
    for s in seeds:
        if s not in idx.first:
            near = difflib.get_close_matches(s, ids, n=5)
            raise DotError(f"--focus: no node {s!r}; close matches: {', '.join(near) or 'none'}")
    adj = defaultdict(set)
    for e, _, _ in idx.edges:
        adj[e.tail.id].add(e.head.id)
        adj[e.head.id].add(e.tail.id)
    keep, frontier = set(seeds), set(seeds)
    for _ in range(opts.depth):
        frontier = {w for u in frontier for w in adj[u]} - keep
        keep |= frontier
    for n, lst, _ in idx.nodes:
        if n.id not in keep:
            remove(lst, n)
    for e, lst, _ in idx.edges:
        if e.tail.id not in keep or e.head.id not in keep:
            remove(lst, e)
    return f"kept {len(keep)} of {len(ids)} nodes within {opts.depth} hops of {', '.join(seeds)}"


def subgraph_label(sg: Subgraph) -> list:
    for s in sg.stmts:
        if isinstance(s, Assign) and s.key == "label":
            return visible_lines(s.val)
        if isinstance(s, AttrStmt) and s.kind == "graph" and s.attrs.get("label"):
            return visible_lines(s.attrs.get("label"))
    return [sg.name or ""]


def subgraph_attr(sg: Subgraph, key: str) -> Optional[Val]:
    val = None
    for s in sg.stmts:
        if isinstance(s, Assign) and s.key == key:
            val = s.val
        elif isinstance(s, AttrStmt) and s.kind == "graph" and s.attrs.get(key):
            val = s.attrs.get(key)
    return val


def find_clusters(idx: Index, spec: str) -> list:
    spec_l = spec.lower()
    hits = [sg for sg, _, _ in idx.subgraphs if sg.name in (spec, f"cluster_{spec}")]
    if not hits:
        hits = [sg for sg, _, _ in idx.subgraphs
                if is_cluster(sg) and spec_l in " ".join(subgraph_label(sg)).lower()]
    if not hits:
        names = [sg.name for sg, _, _ in idx.subgraphs if sg.name]
        raise DotError(f"--collapse: no cluster matches {spec!r}; clusters: {', '.join(names)}")
    return hits


def pass_collapse(g: Graph, idx: Index, opts) -> str:
    targets = []
    for spec in opts.collapse:
        targets.extend(find_clusters(idx, spec))
    if opts.collapse_except:
        keep = [sg for spec in opts.collapse_except for sg in find_clusters(idx, spec)]
        targets.extend(sg for sg, _, ctx in idx.subgraphs
                       if is_cluster(sg) and innermost_cluster(ctx.path) is None
                       and not any(k is sg or k in _descendants(sg) for k in keep))
    parents = {id(sg): (lst, ctx) for sg, lst, ctx in idx.subgraphs}
    done, summary = [], []
    for sg in targets:
        if any(sg is d or sg in _descendants(d) for d in done):
            continue
        done.append(sg)
        inner = {id(x) for x in _descendants(sg)} | {id(sg)}
        members = [nid for nid in idx.ids() if any(id(p) in inner for p in idx.home_of(nid))]
        mset = set(members)
        new_id = f"collapsed_{re.sub(r'[^A-Za-z0-9_]', '_', sg.name or 'subgraph')}"
        lst, ctx = parents[id(sg)]
        # edges written inside the cluster body that leave it go to the root
        leaving = []
        for e, _, ectx in idx.edges:
            if any(p is sg for p in ectx.path) and not (e.tail.id in mset and e.head.id in mset):
                materialize_edge_defaults(e, ectx)
                leaving.append(e)
        title = subgraph_label(sg)[0] if subgraph_label(sg) else new_id
        member_lines = []
        for nid in members:
            decl = idx.decls.get(nid)
            member_lines.append(node_lines(decl[0])[0] if decl else nid)
        attrs = Attrs([
            ("label", q_val(f"{title}\n({len(members)} nodes)")),
            ("shape", Val("id", "box")),
            ("style", Val("q", "rounded,filled,bold")),
            ("fillcolor", subgraph_attr(sg, "fillcolor") or Val("q", "#f1f3f4")),
            ("color", subgraph_attr(sg, "color") or Val("q", "#5f6368")),
            ("fontsize", Val("id", "12")),
            ("tooltip", q_val("\n".join(member_lines))),
        ])
        pos = next(i for i, s in enumerate(lst) if s is sg)
        lst[pos] = summary_node = NodeStmt(new_id, None, attrs, id_val(new_id))
        insert_after(g.stmts, ctx.path[0] if ctx.path else summary_node, leaving)
        names = {x.name for x in _descendants(sg)} | {sg.name}
        for e, _, _ in Index(g).edges:
            for end in (e.tail, e.head):
                if end.id in mset:
                    end.id, end.port, end.idval = new_id, None, id_val(new_id)
            for k in ("lhead", "ltail"):
                if e.attrs.get(k) is not None and e.attrs.get(k).raw in names:
                    e.attrs.pop(k)
        for e, elst, _ in Index(g).edges:
            if e.tail.id == new_id and e.head.id == new_id:
                remove(elst, e)
        summary.append(f"{sg.name} ({len(members)} nodes)")
    return "collapsed " + (", ".join(summary) or "nothing")


def _descendants(sg: Subgraph) -> list:
    out = []
    for s in sg.stmts:
        if isinstance(s, Subgraph):
            out.append(s)
            out.extend(_descendants(s))
    return out


def pass_drop_undirected(g: Graph, idx: Index, opts) -> str:
    n = 0
    for e, lst, _ in idx.edges:
        d = e.attrs.get("dir")
        if d is not None and d.raw == "none":
            remove(lst, e)
            n += 1
    return f"{n} dir=none edges dropped"


def edge_key(e: EdgeStmt, directed: bool) -> tuple:
    ends = (e.tail.id, e.head.id) if directed else tuple(sorted((e.tail.id, e.head.id)))
    get = lambda k: e.attrs.get(k).raw if e.attrs.get(k) is not None else ""
    return ends + (get("dir"), get("style"))


def pass_merge_parallel(g: Graph, idx: Index, opts) -> str:
    groups = defaultdict(list)
    for e, lst, _ in idx.edges:
        groups[edge_key(e, g.directed)].append((e, lst))
    merged = 0
    for items in groups.values():
        if len(items) < 2:
            continue
        keep = items[0][0]
        labels = []
        for e, _ in items:
            text = " ".join(visible_lines(e.attrs.get("label")))
            if text and text not in labels:
                labels.append(text)
        if labels:
            keep.attrs.set("label", q_val(" / ".join(labels)))
        for e, lst in items[1:]:
            add_to_tooltip(keep.attrs, visible_lines(e.attrs.get("tooltip")))
            remove(lst, e)
            merged += 1
    return f"{merged} parallel edges merged"


def graph_label_stmts(g: Graph, idx: Index) -> list:
    """(attrs-like holder, base fontsize) for graph and cluster labels."""
    out = []
    scopes = [(g.stmts, None)] + [(sg.stmts, sg) for sg, _, _ in idx.subgraphs if is_cluster(sg)]
    for stmts, sg in scopes:
        for s in stmts:
            if isinstance(s, AttrStmt) and s.kind == "graph" and s.attrs.get("label"):
                out.append((s.attrs, stmts))
            elif isinstance(s, Assign) and s.key == "label":
                out.append((s, stmts))
    return out


def pass_detail(g: Graph, idx: Index, opts) -> str:
    labels = chars = 0
    for n, _, ctx in idx.nodes:
        label = n.attrs.get("label")
        if label is None or label.kind != "html":
            continue
        base = as_float(n.attrs.get("fontsize") or ctx.ndefs.get("fontsize"), 14.0)
        new, moved = strip_detail_html(label.raw, base, opts.detail_mono_only)
        if moved:
            n.attrs.set("label", Val("html", new))
            add_to_tooltip(n.attrs, moved)
            labels += 1
            chars += sum(len(m) for m in moved)
    # graph and cluster labels: monospace runs only, so legends stay visible
    for holder, stmts in graph_label_stmts(g, idx):
        val = holder.val if isinstance(holder, Assign) else holder.get("label")
        if val.kind != "html":
            continue
        new, moved = strip_detail_html(val.raw, 0, True)
        if not moved:
            continue
        if isinstance(holder, Assign):
            holder.val = Val("html", new)
            tip = next((s for s in stmts if isinstance(s, Assign) and s.key == "tooltip"), None)
            tattrs = Attrs([("tooltip", tip.val)] if tip else [])
            add_to_tooltip(tattrs, moved)
            if tip:
                tip.val = tattrs.get("tooltip")
            else:
                stmts.append(Assign("tooltip", tattrs.get("tooltip")))
        else:
            holder.set("label", Val("html", new))
            add_to_tooltip(holder, moved)
        labels += 1
        chars += sum(len(m) for m in moved)
    return f"{labels} labels: {chars} chars of detail moved to tooltips"


def pass_label_lines(g: Graph, idx: Index, opts) -> str:
    n_capped = 0
    for n, _, _ in idx.nodes:
        label = n.attrs.get("label")
        if label is None or label.kind == "id":
            continue
        cap = cap_html_lines if label.kind == "html" else cap_q_lines
        new, moved = cap(label.raw, opts.label_lines)
        if moved:
            n.attrs.set("label", Val(label.kind, new))
            add_to_tooltip(n.attrs, moved)
            n_capped += 1
    return f"{n_capped} node labels capped at {opts.label_lines} lines"


def shorten(text: str, limit: int) -> str:
    """Cut `text` to at most `limit` chars at a word boundary, ending in an ellipsis."""
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0] if " " in text[:limit] else text[:limit - 1]
    return re.sub(r"[\s·,;:/→(\-]+$", "", cut) + "…"


def pass_edge_labels(g: Graph, idx: Index, opts) -> str:
    changed = 0
    for e, _, _ in idx.edges:
        label = e.attrs.get("label")
        if label is None:
            continue
        lines = visible_lines(label)
        new = "" if opts.edge_labels == "none" else shorten(" ".join(lines), opts.edge_label_max)
        if lines and len(lines) == 1 and new == lines[0]:
            continue
        add_to_tooltip(e.attrs, lines, prepend=True)
        if new:
            e.attrs.set("label", q_val(new))
        else:
            e.attrs.pop("label")
        changed += 1
    return f"{changed} edge labels shortened ({opts.edge_labels}, max {opts.edge_label_max})"


def pass_chains(g: Graph, idx: Index, opts) -> str:
    out_e, in_e = defaultdict(list), defaultdict(list)
    for e, lst, _ in idx.edges:
        if e.tail.id != e.head.id:
            out_e[e.tail.id].append((e, lst))
            in_e[e.head.id].append((e, lst))
    first_decl = {}
    for n, lst, _ in idx.nodes:
        first_decl.setdefault(n.id, (n, lst))

    def link(u):
        if len(out_e[u]) != 1:
            return None
        e, lst = out_e[u][0]
        v = e.head.id
        if len(in_e[v]) != 1 or u not in first_decl or v not in first_decl:
            return None
        if len(idx.decls[u]) > 1 or len(idx.decls[v]) > 1:
            return None
        if idx.home_of(u) != idx.home_of(v) or e.tail.port or e.head.port:
            return None
        d = e.attrs.get("dir")
        if d is not None and d.raw == "none":
            return None
        if visible_lines(e.attrs.get("label")) and not opts.chains_labeled:
            return None
        return e, lst, v

    nxt = {u: r for u in list(first_decl) if (r := link(u))}
    targets = {r[2] for r in nxt.values()}
    merged = 0
    for start in [u for u in nxt if u not in targets]:
        chain, u = [start], start
        while u in nxt and nxt[u][2] not in chain:
            u = nxt[u][2]
            chain.append(u)
        if len(chain) < 2:
            continue
        head, _ = first_decl[start]
        lines, tips = [], []
        for nid in chain:
            n, _ = first_decl[nid]
            nl = node_lines(n)
            lines.append(nl[0] if nl else nid)
            tips.extend(nl[:1] + visible_lines(n.attrs.get("tooltip")) + [""])
        head.attrs.set("label", Val("html", "<br/>↓<br/>".join(html.escape(x, quote=False) for x in lines)))
        head.attrs.set("tooltip", q_val("\n".join(tips).strip()))
        for a, b in zip(chain, chain[1:]):
            e, lst, _ = nxt[a]
            remove(lst, e)
        for nid in chain[1:]:
            n, lst = first_decl[nid]
            remove(lst, n)
        last = chain[-1]
        for e, _ in out_e[last]:
            e.tail.id, e.tail.idval = start, id_val(start)
        merged += len(chain) - 1
    return f"{merged} nodes merged into chains"


def pass_tred(g: Graph, idx: Index, opts) -> str:
    def flow(e):
        d = e.attrs.get("dir")
        return not (d is not None and d.raw == "none")

    adj = defaultdict(list)
    for e, _, _ in idx.edges:
        if flow(e):
            adj[e.tail.id].append(e)
    dead = set()
    for e, lst, _ in idx.edges:
        if not flow(e) or (visible_lines(e.attrs.get("label")) and not opts.tred_labeled):
            continue
        seen, stack, found = {e.tail.id}, [x for x in adj[e.tail.id] if x is not e], False
        while stack and not found:
            x = stack.pop()
            if id(x) in dead:
                continue
            w = x.head.id
            if w == e.head.id:
                found = True
            elif w not in seen:
                seen.add(w)
                stack.extend(y for y in adj[w] if y is not e)
        if found:
            dead.add(id(e))
            remove(lst, e)
    return f"{len(dead)} redundant edges removed"


PASSES = {
    "hoist": pass_hoist, "focus": pass_focus, "collapse": pass_collapse,
    "drop-undirected": pass_drop_undirected, "merge-parallel": pass_merge_parallel,
    "detail": pass_detail, "label-lines": pass_label_lines,
    "edge-labels": pass_edge_labels, "chains": pass_chains, "tred": pass_tred,
}


def apply_sets(g: Graph, sets: list) -> None:
    for spec in sets:
        target, _, rest = spec.partition(".")
        key, eq, value = rest.partition("=")
        if target not in ("graph", "node", "edge") or not key or not eq:
            raise DotError(f"--set {spec!r}: use graph.KEY=VALUE, node.KEY=VALUE or edge.KEY=VALUE")
        val = id_val(value)
        stmt = next((s for s in g.stmts if isinstance(s, AttrStmt) and s.kind == target), None)
        if stmt is None:
            g.stmts.insert(0, AttrStmt(target, Attrs([(key, val)])))
        else:
            stmt.attrs.set(key, val)
        if target == "graph":
            for s in list(g.stmts):
                if isinstance(s, Assign) and s.key == key:
                    remove(g.stmts, s)


def prune(g: Graph) -> None:
    def content(stmts):
        return any(isinstance(s, (NodeStmt, EdgeStmt)) or (isinstance(s, Subgraph) and content(s.stmts))
                   for s in stmts)

    def sweep(stmts):
        for s in list(stmts):
            if isinstance(s, Subgraph):
                if content(s.stmts):
                    sweep(s.stmts)
                else:
                    remove(stmts, s)

    sweep(g.stmts)
    idx = Index(g)
    clusters = {sg.name for sg, _, _ in idx.subgraphs}
    for e, _, _ in idx.edges:
        for k in ("lhead", "ltail"):
            v = e.attrs.get(k)
            if v is not None and v.raw not in clusters:
                e.attrs.pop(k)


# ---------------------------------------------------------------------- stats


def measure(g: Graph) -> dict:
    idx = Index(g)
    node_chars = sum(len(" ".join(node_lines(n))) for n, _, _ in idx.nodes)
    edge_chars = sum(len(" ".join(visible_lines(e.attrs.get("label")))) for e, _, _ in idx.edges)
    return {"nodes": len(idx.ids()), "edges": len(idx.edges),
            "clusters": sum(1 for sg, _, _ in idx.subgraphs if is_cluster(sg)),
            "node label chars": node_chars, "edge label chars": edge_chars}


def cross_cluster_lint(idx: Index) -> list:
    out = []
    for e, _, ctx in idx.edges:
        c = innermost_cluster(ctx.path)
        if c is None:
            continue
        for end in (e.tail, e.head):
            if end.id in idx.home and c not in idx.home[end.id]:
                home = innermost_cluster(idx.home[end.id])
                pulled = c in idx.first.get(end.id, ())
                out.append((e, c, end.id, home, pulled))
    return out


def cmd_stats(g: Graph, path: str) -> None:
    idx = Index(g)
    m = measure(g)
    print(f"{path}: {m['nodes']} nodes, {m['edges']} edges, {m['clusters']} clusters")
    print(f"visible label text: nodes {m['node label chars']} chars, edges {m['edge label chars']} chars")

    print("\nclusters (nodes whose innermost cluster it is):")
    counts = defaultdict(int)
    for nid in idx.ids():
        c = innermost_cluster(idx.home_of(nid))
        counts[id(c) if c else None] += 1
    for sg, _, ctx in idx.subgraphs:
        if is_cluster(sg):
            depth = sum(1 for p in ctx.path if is_cluster(p))
            title = (subgraph_label(sg) or [""])[0][:60]
            print(f"  {'  ' * depth}{sg.name}: {counts[id(sg)]} nodes — {title}")
    print(f"  (root): {counts[None]} nodes")

    print("\nheaviest node labels (lines / chars):")
    heavy = sorted(idx.nodes, key=lambda t: -len(" ".join(node_lines(t[0]))))[:8]
    for n, _, _ in heavy:
        nl = node_lines(n)
        print(f"  {n.id}: {len(nl)} / {len(' '.join(nl))}  {nl[0][:50] if nl else ''}")

    detail_nodes = detail_chars = 0
    for n, _, ctx in idx.nodes:
        label = n.attrs.get("label")
        if label is not None and label.kind == "html":
            base = as_float(n.attrs.get("fontsize") or ctx.ndefs.get("fontsize"), 14.0)
            _, moved = strip_detail_html(label.raw, base, False)
            if moved:
                detail_nodes += 1
                detail_chars += sum(len(x) for x in moved)
    share = detail_chars / m["node label chars"] if m["node label chars"] else 0
    print(f"\ndetail pass would move {detail_chars} chars ({share:.0%} of node label text) "
          f"from {detail_nodes} labels")

    labeled = [e for e, _, _ in idx.edges if visible_lines(e.attrs.get("label"))]
    multi = [e for e in labeled if len(visible_lines(e.attrs.get("label"))) > 1]
    firsts = [len(visible_lines(e.attrs.get("label"))[0]) for e in labeled]
    if labeled:
        print(f"edge labels: {len(labeled)} labeled, {len(multi)} multi-line, "
              f"first line mean {sum(firsts) / len(firsts):.0f} / max {max(firsts)} chars")
    groups = defaultdict(int)
    for e, _, _ in idx.edges:
        groups[edge_key(e, g.directed)] += 1
    print(f"parallel edge groups: {sum(1 for v in groups.values() if v > 1)}")
    undirected = sum(1 for e, _, _ in idx.edges if e.attrs.get("dir") is not None
                     and e.attrs.get("dir").raw == "none")
    back = sum(1 for e, _, _ in idx.edges if e.attrs.get("constraint") is not None
               and e.attrs.get("constraint").raw == "false")
    print(f"dir=none edges: {undirected}; constraint=false edges: {back}")

    probe = parse(emit(g))
    pidx = Index(probe)
    opts = argparse.Namespace(chains_labeled=False, tred_labeled=False)
    print(f"chains: {pass_chains(probe, pidx, opts)}")
    probe = parse(emit(g))
    print(f"tred: {pass_tred(probe, Index(probe), opts)}")

    lint = cross_cluster_lint(idx)
    print(f"\nlint: {len(lint)} edge endpoints written inside a cluster that does not declare them")
    for e, c, nid, home, pulled in lint:
        where = home.name if home else "(root)"
        note = "  <- drawn inside " + c.name if pulled else ""
        print(f"  {e.tail.id} -> {e.head.id} in {c.name}: {nid} is declared in {where}{note}")


# ------------------------------------------------------------------------ cli


def render(out_path: Path, formats: list, dpi: Optional[int]) -> list:
    if not shutil.which("dot"):
        raise DotError("--render needs graphviz `dot` on PATH")
    written = []
    for fmt in formats:
        target = out_path.with_suffix(f".{fmt}")
        cmd = ["dot", f"-T{fmt}", str(out_path), "-o", str(target)]
        if dpi and fmt == "png":
            cmd.insert(1, f"-Gdpi={dpi}")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.stderr.strip():
            print(res.stderr.strip(), file=sys.stderr)
        if res.returncode:
            raise DotError(f"dot failed rendering {target}")
        written.append(str(target))
    return written


def cmd_simplify(g: Graph, args) -> None:
    passes = list(PRESETS[args.preset])
    defaults = PRESET_DEFAULTS[args.preset]
    if args.edge_label_max is None:
        args.edge_label_max = defaults.get("edge_label_max", 40)
    if args.label_lines is None:
        args.label_lines = defaults.get("label_lines")
    elif "label-lines" not in passes:
        passes.append("label-lines")
    if args.focus:
        passes.append("focus")
    if args.collapse or args.collapse_except:
        passes.append("collapse")
    passes += args.add
    if args.edge_labels != "short" and "edge-labels" not in passes:
        passes.append("edge-labels")
    passes = [p for p in PASS_ORDER if p in passes and p not in args.skip]
    if "label-lines" in passes and not args.label_lines:
        passes.remove("label-lines")

    before = measure(g)
    report = []
    for name in passes:
        report.append(f"{name}: {PASSES[name](g, Index(g), args)}")
    apply_sets(g, args.set)
    prune(g)
    after = measure(g)

    src = Path(args.input).name
    comment = f"Simplified from {src} by simplify_dot.py (passes: {', '.join(passes) or 'none'})."
    text = emit(g, comment)
    if args.output in (None, "-"):
        sys.stdout.write(text)
    else:
        Path(args.output).write_text(text)
        report.append(f"wrote {args.output}")
        if args.render:
            report += [f"wrote {p}" for p in render(Path(args.output), args.render.split(","), args.dpi)]
    for line in report:
        print(line, file=sys.stderr)
    print("before → after: " + ", ".join(f"{k} {before[k]} → {after[k]}" for k in before), file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("stats", help="measure a graph and suggest what to simplify")
    st.add_argument("input")

    sp = sub.add_parser("simplify", help="apply simplification passes")
    sp.add_argument("input")
    sp.add_argument("-o", "--output", help="output .dot (default stdout)")
    sp.add_argument("--preset", choices=sorted(PRESETS), default="tidy")
    sp.add_argument("--add", action="append", default=[], choices=PASS_ORDER, help="add a pass")
    sp.add_argument("--skip", action="append", default=[], choices=PASS_ORDER, help="skip a pass")
    sp.add_argument("--edge-labels", choices=["short", "none"], default="short",
                    help="short: one line, cut at a word boundary; none: tooltip only")
    sp.add_argument("--edge-label-max", type=int, help="max visible edge label chars")
    sp.add_argument("--label-lines", type=int, help="cap node labels at N lines (adds label-lines)")
    sp.add_argument("--detail-mono-only", action="store_true",
                    help="detail pass strips monospace runs only, not smaller-font runs")
    sp.add_argument("--collapse", action="append", default=[], metavar="CLUSTER",
                    help="collapse a cluster (name, name without cluster_, or label substring)")
    sp.add_argument("--collapse-except", action="append", default=[], metavar="CLUSTER",
                    help="collapse every top-level cluster except these")
    sp.add_argument("--focus", help="comma-separated node ids to keep, with neighbors")
    sp.add_argument("--depth", type=int, default=1, help="hops kept around --focus nodes")
    sp.add_argument("--chains-labeled", action="store_true", help="chains may absorb labeled edges")
    sp.add_argument("--tred-labeled", action="store_true", help="tred may drop labeled edges")
    sp.add_argument("--set", action="append", default=[], metavar="SCOPE.KEY=VALUE",
                    help="set a default attribute, e.g. graph.ranksep=0.3 or node.fontsize=10")
    sp.add_argument("--render", help="also render OUTPUT with dot, e.g. svg,png")
    sp.add_argument("--dpi", type=int, help="dpi for --render png")

    args = ap.parse_args(argv)
    try:
        g = parse(Path(args.input).read_text())
        if args.cmd == "stats":
            cmd_stats(g, args.input)
        else:
            cmd_simplify(g, args)
    except DotError as exc:
        print(f"simplify_dot: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
