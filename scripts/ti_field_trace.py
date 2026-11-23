#!/usr/bin/env python3
"""Trace every field of the transaction file, by analysis, from the code (roadmap R10).

    python scripts/ti_field_trace.py            # rewrite docs/ti_field_trace.md and .json
    python scripts/ti_field_trace.py --check    # exit 1 if either file is stale

James Gilmore: "id really like to trace each individual field in the transaction file by
analysis." This script answers that from the source, never from a hand-kept list, so a new
analysis cannot read a field without the trace showing it (`tests/test_ti_field_trace.py` fails
when the checked-in trace is stale).

What it reads, statically with `ast` (nothing is imported or run):

  - the loader (`ti/transaction_intelligence/loader.py`): COLUMNS, KEEP, HEADER_MAP and the
    columns `read_file` adds to the frame (merchant_key, source_file);
  - the analyses (`ti/transaction_intelligence/*.py`) and the section driver
    (`ti/txn_sections.py`), with the lens build call in `ti_build.py` as the one other seed;
  - the slide builders (`ti/deck/txn_*.py`) and the chapter lists and titles
    (`ti/chapters_txn.py`: TI_BUILDERS, COMP_BUILDERS, ATTRITION_BUILDERS, TITLES and the
    combined pairs).

How a field reaches a slide:

  1. The frames are followed by data flow, not by name: `ctx.txn` is the transaction frame,
     `ctx.frame` the ODD, `ctx.lenses` the account lenses (and `lenses.attrs` an ODD frame).
     A frame passed to an analysis function marks that parameter; a row filter, `.loc`,
     `.copy()` and the like keep the mark; `for _, g in frame.groupby(...)` marks `g`.
  2. A column read on a marked frame (`df["amount"]`, `df.loc[m, "amount"]`, `"x" in
     df.columns`, `df.groupby("x")`) records the field. Each local name carries the fields its
     value was built from (flow-insensitive: a name reused in a function carries every field
     it was ever bound to, so the trace can over-state, never under-state, within a function).
  3. A pack key is a write to `out[...]`, a dict returned into `out`, or `out.update(...)`.
     `key_prefix + "x"` / `K + "x"` / f-strings are expanded per call site with the prefixes
     the callers pass (fin_, finb_, comp_, compb_, mch_, mchb_, beh_, ic_, rel_). The business
     subsets that txn_sections filters through FINB_KEYS / COMPB_KEYS / MCHB_KEYS keep only
     those keys. Keys that start with "_" are hand-offs between sections (`ctx.shared`), not
     pack keys; what they carry follows them into the sections that read them.
  4. A slide builder's `t.get("key")` / `t["key"]` reads (and its helpers', with constant key
     arguments and module constant tables expanded) name the pack keys each slide draws.

Anything that cannot be resolved this way is listed under "Unresolved", never dropped: a key
expression that is not a constant after expansion, a column name held in a variable that
cannot be traced, a frame handed to a function outside the scan (core/, monthly_analysis/).
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from itertools import product
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ARS = REPO / "build" / "ars_pipeline"
TI = ARS / "ti"
TI_PKG = TI / "transaction_intelligence"
DECK = TI / "deck"
OUT_MD = REPO / "docs" / "ti_field_trace.md"
OUT_JSON = REPO / "docs" / "ti_field_trace.json"

# modules that are scanned as analyses but are not analyses of the frames: the loader is the
# source of the fields, the two report modules only print a finished pack
NOT_ANALYSES = {"loader", "__init__", "competition_report", "sections_report"}

FRAME_KINDS = ("txn", "odd")
# methods that hand back the same rows-and-columns frame (or a filtered / reordered one)
FRAME_METHODS = {"copy", "assign", "query", "dropna", "drop_duplicates", "sort_values",
                 "sort_index", "reset_index", "head", "tail", "rename", "drop", "set_index",
                 "fillna", "sample", "filter", "reindex", "loc", "iloc", "where", "mask",
                 "astype", "nlargest", "nsmallest", "pipe"}
# methods whose string arguments name columns
COLUMN_ARG_METHODS = {"groupby", "sort_values", "drop_duplicates", "set_index", "pivot_table",
                      "pivot", "dropna", "value_counts", "nlargest", "nsmallest", "get",
                      "melt", "explode", "duplicated"}
COLUMN_KWARGS = {"by", "subset", "columns", "keys", "index", "values", "column", "on",
                 "id_vars", "value_vars"}
WHOLE_FRAME_METHODS = {"join", "merge"}
LENS_FIELD = "odd:(account lenses)"
UNRES = ("__unresolved__",)


# ----------------------------------------------------------------------------- module model
class Module:
    def __init__(self, dotted: str, path: Path, role: str):
        self.dotted, self.path, self.role = dotted, path, role
        self.tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        self.consts: dict[str, ast.AST] = {}
        for node in self.tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name):
                self.consts[node.targets[0].id] = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value:
                self.consts[node.target.id] = node.value
        self.funcs = {n.name: n for n in self.tree.body if isinstance(n, ast.FunctionDef)}

    @property
    def short(self) -> str:
        return {"analysis": self.dotted.rsplit(".", 1)[-1],
                "deck": "deck." + self.dotted.rsplit(".", 1)[-1]}.get(self.role, self.dotted.rsplit(".", 1)[-1])

    def package(self) -> str:
        return self.dotted.rsplit(".", 1)[0] if "." in self.dotted else ""


def _abs_module(mod: Module, node: ast.ImportFrom) -> str:
    if not node.level:
        return node.module or ""
    parts = mod.dotted.split(".")[:-1]
    if node.level > 1:
        parts = parts[: len(parts) - (node.level - 1)]
    return ".".join(parts + ([node.module] if node.module else []))


class Func:
    def __init__(self, mod: Module, node: ast.FunctionDef):
        self.mod, self.node, self.name = mod, node, node.name
        a = node.args
        self.params = [p.arg for p in a.posonlyargs + a.args]
        self.kwonly = [p.arg for p in a.kwonlyargs]
        self.defaults: dict[str, ast.AST] = {}
        for p, d in zip(reversed(self.params), reversed(a.defaults)):
            self.defaults[p] = d
        for p, d in zip(self.kwonly, a.kw_defaults):
            if d is not None:
                self.defaults[p] = d
        self.qual = f"{mod.short}.{node.name}"

    def all_params(self):
        return self.params + self.kwonly


# ----------------------------------------------------------------------------- the analyzer
class Trace:
    def __init__(self):
        self.modules: dict[str, Module] = {}
        for p in sorted(TI_PKG.glob("*.py")):
            self._add(f"ti.transaction_intelligence.{p.stem}", p, "analysis")
        self._add("ti.txn_sections", TI / "txn_sections.py", "driver")
        self._add("ti_build", ARS / "ti_build.py", "seed")
        for p in sorted(DECK.glob("txn_*.py")):
            self._add(f"ti.deck.{p.stem}", p, "deck")
        self.funcs: dict[str, Func] = {}
        for m in self.modules.values():
            for fn in m.funcs.values():
                f = Func(m, fn)
                self.funcs[f.qual] = f
        self.imports = {m.dotted: self._imports(m, m.tree.body) for m in self.modules.values()}
        # interprocedural state
        self.param_kinds: dict[str, dict[str, set]] = {q: {} for q in self.funcs}
        self.param_strs: dict[str, dict[str, set]] = {q: {} for q in self.funcs}
        self.ret_deps: dict[str, frozenset] = {q: frozenset() for q in self.funcs}
        self.writes: dict[str, dict] = {q: {} for q in self.funcs}     # tmpl -> (deps, origins)
        self.unres_writes: dict[str, set] = {q: set() for q in self.funcs}
        self.deck_reads: dict[str, set] = {q: set() for q in self.funcs}  # templates
        self.deck_unres: dict[str, set] = {q: set() for q in self.funcs}
        self.shared: dict[str, set] = {}
        self.calls: dict[str, set] = {q: set() for q in self.funcs}
        self.col_reads: dict[str, set] = {q: set() for q in self.funcs}  # (kind, col)
        self.derived: dict[str, set] = {q: set() for q in self.funcs}    # (kind, col)
        self.unresolved: set = set()
        self._seed()

    def _add(self, dotted, path, role):
        self.modules[dotted] = Module(dotted, path, role)

    # ------------------------------------------------------------------ imports / call targets
    def _imports(self, mod: Module, body) -> dict:
        out = {}
        for node in body:
            for n in ast.walk(node) if body is not mod.tree.body else [node]:
                if isinstance(n, ast.ImportFrom):
                    base = _abs_module(mod, n)
                    for a in n.names:
                        name = a.asname or a.name
                        full = f"{base}.{a.name}"
                        if full in self.modules:
                            out[name] = ("module", full)
                        elif base in self.modules and a.name in self.modules[base].funcs:
                            out[name] = ("func", f"{self.modules[base].short}.{a.name}")
                        else:
                            out[name] = ("external", full)
                elif isinstance(n, ast.Import):
                    for a in n.names:
                        out[a.asname or a.name.split(".")[0]] = (
                            ("module", a.name) if a.name in self.modules else ("external", a.name))
        return out

    def _scope_imports(self, f: Func) -> dict:
        key = ("scope", f.qual)
        if key not in self.__dict__.setdefault("_scope_cache", {}):
            d = dict(self.imports[f.mod.dotted])
            d.update(self._imports(f.mod, f.node.body))
            self._scope_cache[key] = d
        return self._scope_cache[key]

    def resolve_call(self, f: Func, func: ast.AST):
        """('func', qual) | ('external', dotted) | None."""
        imp = self._scope_imports(f)
        if isinstance(func, ast.Name):
            if func.id in f.mod.funcs:
                return ("func", f"{f.mod.short}.{func.id}")
            hit = imp.get(func.id)
            if hit and hit[0] in ("func", "external"):
                return hit
            return None
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            hit = imp.get(func.value.id)
            if hit and hit[0] == "module":
                m = self.modules[hit[1]]
                if func.attr in m.funcs:
                    return ("func", f"{m.short}.{func.attr}")
                return ("external", f"{hit[1]}.{func.attr}")
            if hit and hit[0] == "external":
                return ("external", f"{hit[1]}.{func.attr}")
        return None

    # ------------------------------------------------------------------ seeds
    def _seed(self):
        # slide builders: (h, t, base) -- t is the pack
        self.builders = self._chapter_builders()
        for q in self.builders:
            f = self.funcs[q]
            self.param_kinds[q].setdefault(f.params[1], set()).add("pack")
        # driver: a parameter named `metrics` is the pack computed so far (hotspots, filed)
        for q, f in self.funcs.items():
            if f.mod.role == "driver" and "metrics" in f.params:
                self.param_kinds[q].setdefault("metrics", set()).add("pack")

    def _chapter_builders(self) -> dict:
        mod = Module("ti.chapters_txn", TI / "chapters_txn.py", "chapters")
        self.chapters = mod
        imp = {}
        for n in mod.tree.body:
            if isinstance(n, ast.ImportFrom):
                base = _abs_module(mod, n)
                for a in n.names:
                    imp[a.asname or a.name] = f"{base}.{a.name}"
        self.titles = ast.literal_eval(mod.consts["TITLES"])
        self.combined = {}
        pairs = list(ast.literal_eval(mod.consts["TI_COMBINED"])) + list(ast.literal_eval(mod.consts["COMP_COMBINED"]))
        for n in mod.tree.body:
            if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name) \
                    and n.target.id in ("TI_COMBINED", "COMP_COMBINED"):
                pairs += list(ast.literal_eval(n.value))
        for a, b, _topic, headline, _sub, _name in pairs:
            self.combined[a] = (b, headline)
            self.combined[b] = (a, headline)
        self.sections = []
        for n in ast.walk(mod.funcs["compute_all"]):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "T":
                if n.attr not in self.sections:
                    self.sections.append(n.attr)
        out = {}
        for listname, chapter in (("TI_BUILDERS", "Transaction Intelligence"),
                                  ("COMP_BUILDERS", "Competition"), ("ATTRITION_BUILDERS", "Attrition")):
            for e in mod.consts[listname].elts:
                dotted = imp[e.value.id]
                m = self.modules[dotted]
                q = f"{m.short}.{e.attr}"
                out[q] = {"builder": e.attr, "chapter": chapter,
                          "title": self.titles.get(e.attr, e.attr)}
        return out

    # ------------------------------------------------------------------ per-function analysis
    def analyze(self, f: Func, record: bool):
        S = _Scope(self, f)
        S.run(record)
        return S


class _Scope:
    """One function's flow-insensitive environment: per local name, the fields it depends on,
    the frame kinds it holds and the strings it may be."""

    def __init__(self, tr: Trace, f: Func):
        self.tr, self.f = tr, f
        self.deps: dict[str, set] = {}
        self.kind: dict[str, set] = {}
        self.strs: dict[str, set] = {}
        self.loopvars: set[str] = set(f.all_params())
        self.call_binds: dict[str, list] = {}
        self.recording = False
        for p in f.all_params():
            self.deps[p] = {("param", p)}
            self.kind[p] = set(tr.param_kinds[f.qual].get(p, ()))
            self.strs[p] = {(("param", p),)}

    # ---------------------------------------------------------------- helpers
    def _const_node(self, name):
        return self.f.mod.consts.get(name)

    def tmpl(self, e) -> set | None:
        """Possible string values of `e` as templates (tuples of str / ('param', p))."""
        if isinstance(e, ast.Constant) and isinstance(e.value, str):
            return {(e.value,)}
        if isinstance(e, ast.Name):
            if e.id in self.strs:
                v = self.strs[e.id]
                return None if (UNRES in v or not v) else v
            c = self._const_node(e.id)
            if c is not None and not isinstance(c, (ast.Tuple, ast.List, ast.Dict)):
                return self.tmpl(c)
            return None
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Add):
            a, b = self.tmpl(e.left), self.tmpl(e.right)
            if a is None or b is None:
                return None
            return {_join(x + y) for x, y in product(a, b)}
        if isinstance(e, ast.JoinedStr):
            acc = {()}
            for part in e.values:
                if isinstance(part, ast.Constant):
                    s = {(str(part.value),)}
                elif isinstance(part, ast.FormattedValue) and part.format_spec is None and part.conversion == -1:
                    s = self.tmpl(part.value)
                else:
                    s = None
                if s is None:
                    return None
                acc = {_join(x + y) for x, y in product(acc, s)}
            return acc
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.func.attr == "replace" \
                and len(e.args) == 2 and not e.keywords \
                and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in e.args):
            base = self.tmpl(e.func.value)
            if base is None or any(any(not isinstance(p, str) for p in x) for x in base):
                return None
            return {("".join(x).replace(e.args[0].value, e.args[1].value),) for x in base}
        if isinstance(e, ast.IfExp):
            a, b = self.tmpl(e.body), self.tmpl(e.orelse)
            return None if a is None or b is None else a | b
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id == "next" \
                and e.args and isinstance(e.args[0], ast.GeneratorExp):
            g = e.args[0]
            if isinstance(g.elt, ast.Name) and len(g.generators) == 1 \
                    and isinstance(g.generators[0].target, ast.Name) and g.generators[0].target.id == g.elt.id:
                seq = self.const_seq(g.generators[0].iter)
                if seq is not None:
                    out = set()
                    for x in seq:
                        t = self.tmpl(x)
                        if t is None:
                            return None
                        out |= t
                    return out
        return None

    def concrete(self, e) -> list | None:
        t = self.tmpl(e)
        if t is None or any(any(not isinstance(p, str) for p in x) for x in t):
            return None
        return sorted("".join(x) for x in t)

    def const_seq(self, e):
        """The element nodes of a literal sequence (or a module constant that is one)."""
        if isinstance(e, (ast.Tuple, ast.List, ast.Set)):
            return list(e.elts)
        if isinstance(e, ast.Name) and e.id not in self.strs:
            c = self._const_node(e.id)
            if isinstance(c, (ast.Tuple, ast.List)):
                return list(c.elts)
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Add):
            a, b = self.const_seq(e.left), self.const_seq(e.right)
            if a is not None and b is not None:
                return a + b
        return None

    def columns(self, e) -> list | None:
        """Column names a subscript / argument names, or None."""
        one = self.concrete(e)
        if one is not None:
            return one
        if isinstance(e, (ast.List, ast.Tuple)):
            out = []
            for x in e.elts:
                c = self.concrete(x)
                if c is None:
                    return None
                out += c
            return out
        if isinstance(e, ast.ListComp) and isinstance(e.elt, ast.Name) and len(e.generators) == 1 \
                and isinstance(e.generators[0].target, ast.Name) and e.generators[0].target.id == e.elt.id:
            seq = self.const_seq(e.generators[0].iter)
            if seq is not None:
                out = []
                for x in seq:
                    c = self.concrete(x)
                    if c is None:
                        return None
                    out += c
                return out
        if isinstance(e, ast.Name) and e.id in self.list_binds:
            return self.columns(self.list_binds[e.id])
        return None

    @property
    def list_binds(self):
        if not hasattr(self, "_list_binds"):
            self._list_binds = {}
            for n in ast.walk(self.f.node):
                if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) \
                        and isinstance(n.value, (ast.List, ast.ListComp, ast.Tuple)):
                    self._list_binds[n.targets[0].id] = n.value
        return self._list_binds

    def is_ctx(self, e, attr):
        return isinstance(e, ast.Attribute) and e.attr == attr and isinstance(e.value, ast.Name) \
            and e.value.id == "ctx"

    def kinds(self, e) -> set:
        if isinstance(e, ast.Name):
            return set(self.kind.get(e.id, ()))
        if self.is_ctx(e, "txn"):
            return {"txn"}
        if self.is_ctx(e, "frame"):
            return {"odd"}
        if self.is_ctx(e, "lenses"):
            return {"lenses"}
        if isinstance(e, ast.Attribute):
            if e.attr == "attrs" and "lenses" in self.kinds(e.value):
                return {"odd"}
            return set()
        if isinstance(e, ast.Subscript):
            v = e.value
            if isinstance(v, ast.Attribute) and v.attr in ("loc", "iloc"):
                k = self.kinds(v.value) & set(FRAME_KINDS)
                if not k:
                    return set()
                if isinstance(e.slice, ast.Tuple) and len(e.slice.elts) == 2:
                    return set() if self.concrete(e.slice.elts[1]) is not None else k
                return k
            k = self.kinds(v) & set(FRAME_KINDS)
            if not k:
                return set()
            return set() if self.concrete(e.slice) is not None else k
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.func.attr in FRAME_METHODS:
            return self.kinds(e.func.value) & set(FRAME_KINDS)
        if isinstance(e, ast.BoolOp):
            out = set()
            for v in e.values:
                out |= self.kinds(v)
            return out
        return set()

    def _read(self, kind, cols, node):
        if self.recording:
            for c in cols:
                self.tr.col_reads[self.f.qual].add((kind, c))
        return {f"{kind}:{c}" for c in cols}

    def _unresolved(self, msg):
        if self.recording:
            self.tr.unresolved.add(f"`{self.f.qual}`: {msg}")

    # ---------------------------------------------------------------- deps
    def dep(self, e) -> set:
        if e is None:
            return set()
        if isinstance(e, ast.Constant):
            return set()
        if isinstance(e, ast.Name):
            return set(self.deps.get(e.id, ()))
        if isinstance(e, ast.Attribute):
            if self.is_ctx(e, "txn") or self.is_ctx(e, "frame"):
                return set()
            if self.is_ctx(e, "lenses"):
                return {LENS_FIELD}
            vk = self.kinds(e.value)
            if e.attr == "attrs" and "lenses" in vk:
                return set()
            base = self.dep(e.value)
            if "lenses" in vk:
                base.add(LENS_FIELD)
            if "txn" in vk and e.attr in self.tr.loader_fields:
                base |= self._read("txn", [e.attr], e)
            return base
        if isinstance(e, ast.Subscript):
            return self._dep_subscript(e)
        if isinstance(e, ast.Call):
            return self._dep_call(e)
        if isinstance(e, ast.Compare):
            out = self.dep(e.left)
            for op, c in zip(e.ops, e.comparators):
                out |= self.dep(c)
                if isinstance(op, (ast.In, ast.NotIn)):
                    tgt = c.value if isinstance(c, ast.Attribute) and c.attr == "columns" else c
                    k = self.kinds(tgt) & set(FRAME_KINDS)
                    cols = self.concrete(e.left)
                    if k and cols:
                        for kk in k:
                            out |= self._read(kk, cols, e)
                    if "pack" in self.kinds(tgt) and cols:
                        out |= self._pack_read(e.left)
            return out
        if isinstance(e, ast.Lambda):
            return self.dep(e.body)
        if isinstance(e, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            return self._dep_comp(e)
        out = set()
        for c in ast.iter_child_nodes(e):
            if isinstance(c, ast.keyword):
                out |= self.dep(c.value)
            elif isinstance(c, ast.comprehension):
                out |= self.dep(c.iter)
                for i in c.ifs:
                    out |= self.dep(i)
            elif isinstance(c, ast.expr):
                out |= self.dep(c)
        return out

    def _dep_comp(self, e):
        """A comprehension's names live only inside it (Python 3), so they are bound here, for this
        comprehension alone, and do not leak into the function's names of the same spelling."""
        saved = {}
        out = set()
        for g in e.generators:
            it = self.dep(g.iter)
            names = [n.id for n in ast.walk(g.target) if isinstance(n, ast.Name)]
            for nm in names:
                if nm not in saved:
                    saved[nm] = (self.deps.get(nm), self.kind.get(nm), self.strs.get(nm))
                self.deps[nm], self.kind[nm], self.strs[nm] = set(it), set(), {UNRES}
            seq = self.const_seq(g.iter)
            if seq is not None:
                vals: dict[str, set] = {}
                for el in seq:
                    pairs = [(g.target, el)]
                    if isinstance(g.target, ast.Tuple) and isinstance(el, (ast.Tuple, ast.List)) \
                            and len(el.elts) == len(g.target.elts):
                        pairs = list(zip(g.target.elts, el.elts))
                    for t, v in pairs:
                        if isinstance(t, ast.Name):
                            s = self.tmpl(v)
                            vals.setdefault(t.id, set()).update(s if s is not None else {UNRES})
                self.strs.update(vals)
            else:
                self.loopvars.update(names)
            if isinstance(g.iter, ast.Call) and isinstance(g.iter.func, ast.Attribute) \
                    and g.iter.func.attr == "groupby" and isinstance(g.target, ast.Tuple) \
                    and isinstance(g.target.elts[-1], ast.Name):
                self.kind[g.target.elts[-1].id] = self.kinds(g.iter.func.value) & set(FRAME_KINDS)
            for cond in g.ifs:
                out |= self.dep(cond)
        for x in ([e.key, e.value] if isinstance(e, ast.DictComp) else [e.elt]):
            out |= self.dep(x)
        for nm, (d, k, s) in saved.items():
            for store, v in ((self.deps, d), (self.kind, k), (self.strs, s)):
                if v is None:
                    store.pop(nm, None)
                else:
                    store[nm] = v
        return out

    def _pack_read(self, key_expr):
        """A read of the pack: a slide's t.get(...) or a driver's metrics.get(...)."""
        t = self.tmpl(key_expr)
        if self.f.mod.role == "deck":           # a slide's reads are its summary, kept on every pass
            if t is None:
                self.tr.deck_unres[self.f.qual].add(ast.unparse(key_expr))
            else:
                self.tr.deck_reads[self.f.qual] |= t
            return set()
        if t is None:
            self._unresolved(f"reads the pack with a key that cannot be resolved: `{ast.unparse(key_expr)}`")
            return set()
        return {("pack", "".join(x)) for x in t if all(isinstance(p, str) for p in x)}

    def _out_reads(self, e):
        """out["k"] read back inside the function that writes it: the fields of what was written
        to that key, not of everything in `out`."""
        want = self.tmpl(e.slice)
        if want is None:
            return None
        if not hasattr(self, "_out_assigns"):
            self._out_assigns = []
            for n in ast.walk(self.f.node):
                if isinstance(n, (ast.Assign, ast.AugAssign)):
                    for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                        root = t
                        while isinstance(root, ast.Subscript) and isinstance(root.value, ast.Subscript):
                            root = root.value
                        if isinstance(root, ast.Subscript) and isinstance(root.value, ast.Name) \
                                and root.value.id == "out":
                            self._out_assigns.append((root.slice, n.value))
        guard = self.__dict__.setdefault("_out_guard", set())
        out = set()
        for sl, val in self._out_assigns:
            if id(val) in guard or self.tmpl(sl) != want:
                continue
            guard.add(id(val))
            try:
                out |= self.dep(val)
            finally:
                guard.discard(id(val))
        return out

    def _dep_subscript(self, e):
        v = e.value
        if isinstance(v, ast.Name) and v.id == "out" and self.f.mod.role != "deck":
            r = self._out_reads(e)
            if r is not None:
                return r
        if isinstance(v, ast.Attribute) and v.attr == "shared" and isinstance(v.value, ast.Name) and v.value.id == "ctx":
            c = self.concrete(e.slice)
            return {("shared", x) for x in c} if c else set()
        if "pack" in self.kinds(v):
            return self._pack_read(e.slice)
        if isinstance(v, ast.Attribute) and v.attr in ("loc", "iloc"):
            k = self.kinds(v.value) & set(FRAME_KINDS)
            out = self.dep(v.value)
            if k and isinstance(e.slice, ast.Tuple) and len(e.slice.elts) == 2:
                out |= self.dep(e.slice.elts[0])
                cols = self.columns(e.slice.elts[1])
                if cols is not None:
                    for kk in k:
                        out |= self._read(kk, cols, e)
                elif not isinstance(e.slice.elts[1], ast.Slice):
                    self._unresolved(f"column(s) `{ast.unparse(e.slice.elts[1])}` of the {'/'.join(sorted(k))} "
                                     f"frame cannot be resolved")
                return out
            return out | self.dep(e.slice)
        k = self.kinds(v) & set(FRAME_KINDS)
        out = self.dep(v)
        if k:
            cols = self.columns(e.slice)
            if cols is not None:
                for kk in k:
                    out |= self._read(kk, cols, e)
                return out
            if isinstance(e.slice, ast.Name) and e.slice.id in self.loopvars:
                self._unresolved(f"column `{e.slice.id}` of the {'/'.join(sorted(k))} frame is a variable "
                                 f"that cannot be resolved")
            return out | self.dep(e.slice)
        return out | self.dep(e.slice)

    def _bind_args(self, g: Func, call: ast.Call):
        """param -> arg node (or default node, or None) for one call."""
        out = {}
        pos = [a for a in call.args]
        for i, p in enumerate(g.params):
            if i < len(pos) and not isinstance(pos[i], ast.Starred):
                out[p] = ("arg", pos[i])
        for kw in call.keywords:
            if kw.arg is not None:
                out[kw.arg] = ("arg", kw.value)
        for p in g.all_params():
            if p not in out:
                out[p] = ("default", g.defaults.get(p))
        return out

    def _subst_deps(self, deps, binds, g: Func):
        out = set()
        for d in deps:
            if isinstance(d, tuple) and d[0] == "param":
                how, node = binds.get(d[1], ("default", None))
                if how == "arg":
                    out |= self.dep(node)
            else:
                out.add(d)
        return out

    def _subst_tmpl(self, tmpls, binds, g: Func):
        out = set()
        for t in tmpls:
            acc = {()}
            for part in t:
                if isinstance(part, str):
                    acc = {_join(x + (part,)) for x in acc}
                    continue
                how, node = binds.get(part[1], ("default", None))
                if node is None:
                    return None
                s = self.tmpl(node) if how == "arg" else _Scope(self.tr, g).tmpl(node)
                if s is None:
                    return None
                acc = {_join(x + y) for x, y in product(acc, s)}
            out |= acc
        return out

    def _dep_call(self, e: ast.Call):
        func = e.func
        # ctx.shared.get("x")
        if isinstance(func, ast.Attribute) and func.attr in ("get", "pop", "setdefault"):
            v = func.value
            if isinstance(v, ast.Attribute) and v.attr == "shared" and isinstance(v.value, ast.Name) and v.value.id == "ctx" and e.args:
                c = self.concrete(e.args[0])
                return {("shared", x) for x in c} if c else set()
            if "pack" in self.kinds(v) and e.args and func.attr == "get":
                return self._pack_read(e.args[0]) | set().union(*[self.dep(a) for a in e.args[1:]])
            if func.attr == "pop" and isinstance(v, ast.Name) and v.id == "out" and e.args:
                c = self.concrete(e.args[0])
                if c:
                    return {("pack", x) for x in c}
        target = self.tr.resolve_call(self.f, func)
        argdeps = set()
        for a in e.args:
            argdeps |= self.dep(a.value if isinstance(a, ast.Starred) else a)
        for kw in e.keywords:
            argdeps |= self.dep(kw.value)
        if target and target[0] == "func" and target[1] in self.tr.funcs:
            g = self.tr.funcs[target[1]]
            binds = self._bind_args(g, e)
            if self.recording:
                self.tr.calls[self.f.qual].add(g.qual)
            return self._subst_deps(self.tr.ret_deps[g.qual], binds, g)
        out = argdeps | self.dep(func)
        if isinstance(func, ast.Attribute):
            k = self.kinds(func.value) & set(FRAME_KINDS)
            if k and func.attr in COLUMN_ARG_METHODS:
                cand = list(e.args[:1]) + [kw.value for kw in e.keywords if kw.arg in COLUMN_KWARGS]
                for a in cand:
                    cols = self.columns(a)
                    if cols is not None:
                        for kk in k:
                            out |= self._read(kk, cols, e)
            if k and func.attr == "assign" and self.recording:
                for kw in e.keywords:
                    if kw.arg:
                        for kk in k:
                            self.tr.derived[self.f.qual].add((kk, kw.arg))
            if func.attr in WHOLE_FRAME_METHODS:
                for x in [func.value] + list(e.args):
                    if "odd" in self.kinds(x) and not (isinstance(x, ast.Subscript) and self.columns(x.slice)):
                        self._unresolved(f"joins the ODD frame `{ast.unparse(x)[:40]}` whole: every column it "
                                         f"holds (lens.build's kept columns) can reach the result")
        if target and target[0] == "external" and not target[1].split(".")[0] in ("pandas", "numpy", "pd", "np"):
            for a in list(e.args) + [kw.value for kw in e.keywords]:
                k = self.kinds(a) & set(FRAME_KINDS)
                if k:
                    self._unresolved(f"passes the {'/'.join(sorted(k))} frame to `{target[1]}`, outside the "
                                     f"scan; the columns it reads there are not traced")
        return out

    # ---------------------------------------------------------------- binding
    def _bind(self, target, value, deps=None, kinds=None, strs=None):
        if deps is None:
            deps = self.dep(value)
            kinds = self.kinds(value)
            strs = self.tmpl(value) if value is not None else None
        changed = False
        if isinstance(target, ast.Name):
            n = target.id
            old = (len(self.deps.get(n, ())), len(self.kind.get(n, ())), len(self.strs.get(n, ())))
            self.deps.setdefault(n, set()).update(deps)
            self.kind.setdefault(n, set()).update(kinds or ())
            self.strs.setdefault(n, set()).update(strs if strs is not None else {UNRES})
            new = (len(self.deps[n]), len(self.kind[n]), len(self.strs[n]))
            return old != new
        if isinstance(target, (ast.Tuple, ast.List)):
            if isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == len(target.elts):
                for t, v in zip(target.elts, value.elts):
                    changed |= self._bind(t, v)
            else:
                for t in target.elts:
                    changed |= self._bind(t, None, deps, set(), None)
            return changed
        if isinstance(target, ast.Starred):
            return self._bind(target.value, None, deps, set(), None)
        if isinstance(target, (ast.Subscript, ast.Attribute)):
            root = target
            deps = set(deps)
            while isinstance(root, (ast.Subscript, ast.Attribute)):
                if isinstance(root, ast.Subscript):      # x[mask] = v: x now depends on the mask too
                    deps |= self.dep(root.slice)
                root = root.value
            if isinstance(root, ast.Name):
                if isinstance(target, ast.Subscript) and self.recording:
                    k = self.kinds(target.value) & set(FRAME_KINDS)
                    cols = self.concrete(target.slice)
                    if k and cols:
                        for kk in k:
                            for c in cols:
                                self.tr.derived[self.f.qual].add((kk, c))
                return self._mutate(root.id, deps) if root.id != "ctx" else False
        return False

    def _mutate(self, name, deps):
        """`name` (and every container it was taken out of: row = pg.setdefault(...)) takes `deps`."""
        changed = False
        seen, stack = set(), [name]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            changed |= self._bind(ast.Name(id=n), None, deps, set(), set())
            stack += self.aliases.get(n, [])
        return changed

    @property
    def aliases(self):
        """x -> containers x was read out of (x = y[k], y.get(k), y.setdefault(k, ...))."""
        if not hasattr(self, "_aliases"):
            self._aliases = {}
            for n in ast.walk(self.f.node):
                if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                    v = n.value
                    src = None
                    if isinstance(v, ast.Subscript) and isinstance(v.value, ast.Name):
                        src = v.value.id
                    elif isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) \
                            and v.func.attr in ("get", "setdefault") and isinstance(v.func.value, ast.Name):
                        src = v.func.value.id
                    if src and src not in ("ctx", "out") and src != n.targets[0].id:
                        self._aliases.setdefault(n.targets[0].id, []).append(src)
        return self._aliases

    def _bind_iter(self, target, it):
        changed = False
        deps = self.dep(it)
        seq = self.const_seq(it)
        if seq is not None:
            for el in seq:
                changed |= self._bind(target, el)
            return changed
        # for _, g in frame.groupby(...): g is the same kind of frame
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) and it.func.attr == "groupby":
            k = self.kinds(it.func.value) & set(FRAME_KINDS)
            if k and isinstance(target, ast.Tuple) and target.elts:
                for t in target.elts[:-1]:
                    changed |= self._bind(t, None, deps, set(), None)
                return changed | self._bind(target.elts[-1], None, deps, k, None)
        for n in ast.walk(target):
            if isinstance(n, ast.Name):
                self.loopvars.add(n.id)
        return changed | self._bind(target, None, deps, set(), None)

    def _env_pass(self):
        changed = False
        for n in ast.walk(self.f.node):
            if n is self.f.node:
                continue
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    changed |= self._bind(t, n.value)
                    if isinstance(n.value, ast.Call):
                        names = [t] if isinstance(t, ast.Name) else (t.elts[:1] if isinstance(t, ast.Tuple) else [])
                        for nm in names:
                            if isinstance(nm, ast.Name):
                                lst = self.call_binds.setdefault(nm.id, [])
                                if n.value not in lst:
                                    lst.append(n.value)
            elif isinstance(n, (ast.AnnAssign, ast.AugAssign)) and n.value is not None:
                changed |= self._bind(n.target, n.value)
            elif isinstance(n, ast.NamedExpr):
                changed |= self._bind(n.target, n.value)
            elif isinstance(n, ast.For):
                changed |= self._bind_iter(n.target, n.iter)
            elif isinstance(n, ast.withitem) and n.optional_vars is not None:
                changed |= self._bind(n.optional_vars, n.context_expr)
            elif isinstance(n, ast.Expr) and isinstance(n.value, ast.Call):
                # a call made for its effect may change what it is handed (x.append(v),
                # attach_competitors(facts, rows)): every name it touches takes every argument's fields
                c = n.value
                d = set()
                for a in c.args:
                    d |= self.dep(a.value if isinstance(a, ast.Starred) else a)
                for kw in c.keywords:
                    d |= self.dep(kw.value)
                touched = list(c.args) + [kw.value for kw in c.keywords]
                if isinstance(c.func, ast.Attribute):
                    touched.append(c.func.value)
                for x in touched:
                    while isinstance(x, (ast.Attribute, ast.Subscript, ast.Starred)):
                        x = x.value
                    if isinstance(x, ast.Name) and x.id not in ("ctx", "out", "warn") and x.id in self.deps:
                        changed |= self._mutate(x.id, d)
            elif isinstance(n, ast.FunctionDef):
                for a in n.args.args:
                    self.loopvars.add(a.arg)
        return changed

    # ---------------------------------------------------------------- writes and the final pass
    def _add_write(self, tmpls, deps, origin, where):
        W = self.tr.writes[self.f.qual]
        if tmpls is None:
            self.tr.unres_writes[self.f.qual].add(f"`{self.f.qual}` writes a pack key that cannot be resolved: {where}")
            return
        for t in tmpls:
            d0, o0 = W.get(t, (frozenset(), frozenset()))
            W[t] = (frozenset(d0 | deps), frozenset(o0 | origin))

    def _roll(self, g: Func, call: ast.Call, keep=None):
        binds = self._bind_args(g, call)
        for t, (d, o) in list(self.tr.writes[g.qual].items()):
            nt = self._subst_tmpl({t}, binds, g)
            if nt is None:
                self.tr.unres_writes[self.f.qual].add(
                    f"`{g.qual}` writes `{_show(t)}` and the call in `{self.f.qual}` passes a prefix that cannot be resolved")
                continue
            if keep is not None:
                nt = {x for x in nt if all(isinstance(p, str) for p in x) and "".join(x) in keep}
                if not nt:
                    continue
            self._add_write(nt, self._subst_deps(d, binds, g), set(o), "")
        for u in self.tr.unres_writes[g.qual]:
            self.tr.unres_writes[self.f.qual].add(u)

    def _scanned(self, call):
        if not isinstance(call, ast.Call):
            return None
        t = self.tr.resolve_call(self.f, call.func)
        if t and t[0] == "func" and t[1] in self.tr.funcs:
            return self.tr.funcs[t[1]]
        return None

    def _dict_into_out(self, v, where):
        me = {self.f.qual}
        if isinstance(v, ast.BoolOp):
            v = v.values[0]
        if isinstance(v, ast.Dict):
            for k, val in zip(v.keys, v.values):
                if k is None:
                    self._dict_into_out(val, where)
                    continue
                self._add_write(self.tmpl(k), self.dep(val), me, f"`{ast.unparse(k)}` ({where})")
            return
        g = self._scanned(v)
        if g is not None:
            self._roll(g, v)
            return
        if isinstance(v, ast.DictComp):
            keep = self._comp_filter(v)
            if keep is not None:
                src = v.generators[0].iter.func.value
                calls = self.call_binds.get(src.id, []) if isinstance(src, ast.Name) else []
                rolled = False
                for c in calls:
                    g = self._scanned(c)
                    if g is not None:
                        self._roll(g, c, keep=set(keep))
                        rolled = True
                if not rolled:
                    self._add_write({(k,) for k in keep}, self.dep(src), me, where)
                return
            self.tr.unres_writes[self.f.qual].add(
                f"`{self.f.qual}` merges a dict comprehension whose keys cannot be resolved: "
                f"`{ast.unparse(v)[:90]}`")
            return
        if isinstance(v, ast.Name) and v.id in self.call_binds:
            for c in self.call_binds[v.id]:
                g = self._scanned(c)
                if g is not None:
                    self._roll(g, c)
            return
        self.tr.unres_writes[self.f.qual].add(
            f"`{self.f.qual}` merges `{ast.unparse(v)[:80]}` into the pack; its keys cannot be resolved")

    def _comp_filter(self, v: ast.DictComp):
        """{k: v for k, v in X.items() if k in NAME} -> the strings in NAME."""
        if len(v.generators) != 1:
            return None
        g = v.generators[0]
        if not (isinstance(g.iter, ast.Call) and isinstance(g.iter.func, ast.Attribute) and g.iter.func.attr == "items"):
            return None
        for cond in g.ifs:
            if isinstance(cond, ast.Compare) and len(cond.ops) == 1 and isinstance(cond.ops[0], ast.In):
                seq = self.const_seq(cond.comparators[0])
                if seq is not None:
                    out = []
                    for x in seq:
                        c = self.concrete(x)
                        if c is None:
                            return None
                        out += c
                    return out
        return None

    def _final_pass(self):
        f, tr = self.f, self.tr
        tr.writes[f.qual] = {}
        tr.unres_writes[f.qual] = set()
        tr.deck_reads[f.qual] = set()
        tr.deck_unres[f.qual] = set()
        ret = set()
        me = {f.qual}
        for n in ast.walk(f.node):
            saved = self._enter_loops(n)
            self._final_node(n, ret, me)
            self._leave_loops(saved)
        tr.ret_deps[f.qual] = frozenset(ret)

    def _parents(self):
        if not hasattr(self, "_parent"):
            self._parent = {}
            for p in ast.walk(self.f.node):
                for c in ast.iter_child_nodes(p):
                    self._parent[c] = p
        return self._parent

    def _enter_loops(self, n):
        """Inside `for a, b in <literal table>:` the loop's names are exactly that table's values,
        whatever else the function later binds them to (portfolio's `key`)."""
        par = self._parents()
        over = {}
        x = n
        while x in par:
            x = par[x]
            if isinstance(x, (ast.For, ast.comprehension)):
                seq = self.const_seq(x.iter)
                if seq is None:
                    continue
                vals: dict[str, set] = {}
                for el in seq:
                    pairs = [(x.target, el)]
                    if isinstance(x.target, ast.Tuple) and isinstance(el, (ast.Tuple, ast.List)) \
                            and len(el.elts) == len(x.target.elts):
                        pairs = list(zip(x.target.elts, el.elts))
                    for t, v in pairs:
                        if isinstance(t, ast.Name):
                            s = self.tmpl(v)
                            vals.setdefault(t.id, set()).update(s if s is not None else {UNRES})
                for name, v in vals.items():
                    over.setdefault(name, v)
        saved = {name: self.strs.get(name) for name in over}
        self.strs.update(over)
        return saved

    def _leave_loops(self, saved):
        for name, v in saved.items():
            if v is None:
                self.strs.pop(name, None)
            else:
                self.strs[name] = v

    def _final_node(self, n, ret, me):
        f, tr = self.f, self.tr
        if True:
            if isinstance(n, ast.stmt):
                # every expression a statement holds (not its assignment targets): records the reads
                skip = set(map(id, n.targets)) if isinstance(n, ast.Assign) else \
                    {id(n.target)} if isinstance(n, (ast.For, ast.AnnAssign)) else set()
                for c in ast.iter_child_nodes(n):
                    if isinstance(c, ast.expr) and id(c) not in skip:
                        self.dep(c)
            if isinstance(n, ast.Call):
                # every call: bind frame kinds into the callee's parameters
                g = self._scanned(n)
                if g is not None:
                    for p, (how, node) in self._bind_args(g, n).items():
                        if how == "arg":
                            k = self.kinds(node)
                            if k:
                                tr.param_kinds[g.qual].setdefault(p, set()).update(k)
                    if any(isinstance(a, ast.Name) and a.id == "out" for a in n.args) and f.mod.role != "deck":
                        self._roll(g, n)
                    if f.mod.role == "deck" and any("pack" in self.kinds(a) for a in n.args):
                        binds = self._bind_args(g, n)
                        r = self._subst_tmpl(tr.deck_reads[g.qual], binds, g) if tr.deck_reads[g.qual] else set()
                        if r is None:
                            tr.deck_unres[f.qual].add(f"keys read by `{g.qual}` with a key argument that cannot be resolved")
                        else:
                            tr.deck_reads[f.qual] |= r
                        tr.deck_unres[f.qual] |= tr.deck_unres[g.qual]
                fn = n.func
                if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "out" \
                        and f.mod.role != "deck":
                    if fn.attr == "update" and n.args:
                        self._dict_into_out(n.args[0], f"out.update in {f.qual}")
                    elif fn.attr == "setdefault" and n.args:
                        self._add_write(self.tmpl(n.args[0]), self.dep(n.args[1]) if len(n.args) > 1 else set(),
                                        me, ast.unparse(n.args[0]))
                # ctx.shared.update(a=..., b=...)
                if isinstance(fn, ast.Attribute) and fn.attr == "update" and isinstance(fn.value, ast.Attribute) \
                        and fn.value.attr == "shared":
                    for kw in n.keywords:
                        if kw.arg:
                            tr.shared.setdefault(kw.arg, set()).update(self.dep(kw.value))
            elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)) and getattr(n, "value", None) is not None:
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                for t in targets:
                    self._bind(t, n.value)       # records derived columns
                    root = t
                    while isinstance(root, ast.Subscript) and isinstance(root.value, ast.Subscript):
                        root = root.value
                    if isinstance(root, ast.Subscript) and isinstance(root.value, ast.Name) and root.value.id == "out" \
                            and f.mod.role != "deck":
                        self._add_write(self.tmpl(root.slice), self.dep(n.value), me, f"`out[{ast.unparse(root.slice)}]`")
                    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Attribute) and t.value.attr == "shared":
                        c = self.concrete(t.slice)
                        for x in c or []:
                            tr.shared.setdefault(x, set()).update(self.dep(n.value))
                    first = t.elts[0] if isinstance(t, ast.Tuple) and t.elts else t
                    if isinstance(first, ast.Name) and first.id == "out" and f.mod.role != "deck":
                        if isinstance(n.value, ast.Dict):
                            self._dict_into_out(n.value, f"out = in {f.qual}")
                        else:
                            g = self._scanned(n.value)
                            if g is not None:
                                self._roll(g, n.value)
            elif isinstance(n, ast.Return) and n.value is not None:
                ret |= self.dep(n.value)
                if f.mod.role != "deck":
                    v = n.value
                    if isinstance(v, ast.Tuple) and v.elts:
                        v = v.elts[0]
                    if isinstance(v, (ast.Dict, ast.DictComp)) or self._scanned(v) is not None:
                        if isinstance(v, ast.DictComp) and self._comp_filter(v) is None and f.mod.role == "analysis":
                            pass                       # a helper's own dict, not merged into a pack here
                        else:
                            self._dict_into_out(v, f"return in {f.qual}")

    def run(self, record):
        for _ in range(40):
            if not self._env_pass():
                break
        else:
            raise RuntimeError(f"environment of {self.f.qual} did not settle")
        self.recording = record
        self._final_pass()


def _join(parts: tuple) -> tuple:
    out = []
    for p in parts:
        if isinstance(p, str) and out and isinstance(out[-1], str):
            out[-1] = out[-1] + p
        elif p != "":
            out.append(p)
    return tuple(out)


def _show(t) -> str:
    return "".join(p if isinstance(p, str) else "{" + p[1] + "}" for p in t)


# ----------------------------------------------------------------------------- the loader
def loader_facts():
    mod = Module("ti.transaction_intelligence.loader", TI_PKG / "loader.py", "source")
    columns = ast.literal_eval(mod.consts["COLUMNS"])
    keep = ast.literal_eval(mod.consts["KEEP"])
    header = ast.literal_eval(mod.consts["HEADER_MAP"])
    aliases = {}
    for raw, canon in header.items():
        aliases.setdefault(canon, []).append(raw)
    added = []
    for n in ast.walk(mod.funcs["read_file"]):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == "frame" \
                        and isinstance(t.slice, ast.Constant) and t.slice.value not in keep \
                        and t.slice.value not in added:
                    added.append(t.slice.value)
    hashed = any(isinstance(n, ast.Constant) and n.value == "primary_account_num"
                 for n in ast.walk(mod.funcs["_names_from_header"]))
    return {"columns": columns, "keep": keep, "aliases": aliases, "added": added,
            "hash_header_account": hashed}


# ----------------------------------------------------------------------------- build
def build() -> dict:
    lf = loader_facts()
    tr = Trace()
    tr.loader_fields = set(lf["columns"]) | set(lf["added"])
    # seed: the lens build call in ti_build.py hands it ctx.frame
    order = [q for q, f in tr.funcs.items() if f.mod.role != "deck"] + \
            [q for q, f in tr.funcs.items() if f.mod.role == "deck"]

    def snapshot():
        return (json.dumps({q: {p: sorted(v) for p, v in d.items()} for q, d in tr.param_kinds.items()}, sort_keys=True),
                json.dumps({q: sorted(map(repr, v)) for q, v in tr.ret_deps.items()}, sort_keys=True),
                json.dumps({q: sorted((repr(k), sorted(map(repr, d)), sorted(o)) for k, (d, o) in v.items())
                            for q, v in tr.writes.items()}, sort_keys=True),
                json.dumps({q: sorted(map(repr, v)) for q, v in tr.deck_reads.items()}, sort_keys=True),
                json.dumps({k: sorted(map(repr, v)) for k, v in tr.shared.items()}, sort_keys=True))

    prev = None
    for _ in range(30):
        for q in order:
            tr.analyze(tr.funcs[q], record=False)
        cur = snapshot()
        if cur == prev:
            break
        prev = cur
    else:
        raise RuntimeError("the interprocedural trace did not settle")
    tr.col_reads = {q: set() for q in tr.funcs}
    tr.derived = {q: set() for q in tr.funcs}
    tr.unresolved = set()
    tr.calls = {q: set() for q in tr.funcs}
    for q in order:
        f = tr.funcs[q]
        if f.mod.role == "seed":
            tr.analyze(f, record=False)
            continue
        tr.analyze(f, record=True)
    return assemble(tr, lf)


def assemble(tr: Trace, lf: dict) -> dict:
    roots = [f"txn_sections.{s}" for s in tr.sections]
    # pack keys, per section
    key_deps: dict[str, set] = {}
    key_sections: dict[str, set] = {}
    key_writers: dict[str, set] = {}
    unresolved = set(tr.unresolved)
    for r in roots:
        for t, (d, o) in tr.writes[r].items():
            if not all(isinstance(p, str) for p in t):
                unresolved.add(f"`{r}`: key `{_show(t)}` still holds a parameter after expansion")
                continue
            k = "".join(t)
            key_deps.setdefault(k, set()).update(d)
            key_sections.setdefault(k, set()).add(r.split(".", 1)[1])
            key_writers.setdefault(k, set()).update(o)
        unresolved |= tr.unres_writes[r]

    # close the symbolic refs: shared hand-offs and pack keys read by later sections
    def close(deps, seen=None):
        seen = set() if seen is None else seen
        out = set()
        for d in deps:
            if isinstance(d, str):
                out.add(d)
            elif d[0] == "pack" and ("pack", d[1]) not in seen:
                seen.add(d)
                if d[1] not in key_deps:
                    unresolved.add(f"a section reads pack key `{d[1]}`, which no traced section writes")
                out |= close(key_deps.get(d[1], ()), seen)
            elif d[0] == "shared" and d not in seen:
                seen.add(d)
                out |= close(tr.shared.get(d[1], ()), seen)
        return out

    def vias(deps):
        return sorted({f"{d[0]}:{d[1]}" for d in deps if isinstance(d, tuple) and d[0] in ("pack", "shared")})

    keys = {}
    for k in sorted(key_deps):
        fields = close(key_deps[k])
        keys[k] = {"sections": sorted(key_sections[k]), "writers": sorted(key_writers[k]),
                   "handoff": k.startswith("_"),
                   "txn_fields": sorted(x[4:] for x in fields if x.startswith("txn:")),
                   "odd_fields": sorted(x[4:] for x in fields if x.startswith("odd:")),
                   "via": vias(key_deps[k]), "slides": []}

    # slides
    slide_keys_missing = {}
    builders = {}
    for q, info in tr.builders.items():
        reads = tr.deck_reads[q]
        ks = sorted({"".join(t) for t in reads if all(isinstance(p, str) for p in t)})
        for t in reads:
            if not all(isinstance(p, str) for p in t):
                unresolved.add(f"`{q}`: slide reads `{_show(t)}`, still holding a parameter")
        for u in tr.deck_unres[q]:
            unresolved.add(f"`{q}`: slide reads the pack with `{u}`, which cannot be resolved")
        partner = tr.combined.get(info["builder"])
        label = info["title"] + (f" [drawn with {tr.titles.get(partner[0], partner[0])} as \"{partner[1]}\"]"
                                 if partner else "")
        builders[q] = dict(info, keys=ks, label=label)
        for k in ks:
            if k in keys:
                keys[k]["slides"].append(q)
            else:
                slide_keys_missing.setdefault(k, []).append(q)

    # functions reached from each section (for "read directly in")
    reach = {}
    for r in roots:
        seen, stack = set(), [r]
        while stack:
            q = stack.pop()
            if q in seen:
                continue
            seen.add(q)
            stack += [c for c in tr.calls.get(q, ()) if tr.funcs[c].mod.role != "deck"]
        reach[r.split(".", 1)[1]] = seen

    def field_block(kind, name):
        readers = sorted(q for q, cols in tr.col_reads.items() if (kind, name) in cols)
        rows = []
        tag = "txn_fields" if kind == "txn" else "odd_fields"
        by_section = {}
        for k, v in keys.items():
            if name in v[tag]:
                for s in v["sections"]:
                    by_section.setdefault(s, []).append(k)
        for s in tr.sections:
            if s not in by_section:
                continue
            ks = sorted(by_section[s])
            direct = sorted(q for q in readers if q in reach.get(s, ()))
            pk = [k for k in ks if not keys[k]["handoff"]]
            ho = [k for k in ks if keys[k]["handoff"]]
            via = sorted({x for k in ks for x in keys[k]["via"]}) if not direct else []
            slides = sorted({q for k in pk for q in keys[k]["slides"]}, key=lambda q: list(tr.builders).index(q))
            rows.append({"section": s, "read_in": direct, "via": via, "pack_keys": pk,
                         "handoffs": ho, "slides": slides})
        return {"read_in": readers, "sections": rows}

    fields = {}
    for i, c in enumerate(lf["columns"]):
        fields[c] = {"position": i + 1, "aliases": sorted(lf["aliases"].get(c, [])),
                     "kept": c in lf["keep"], **field_block("txn", c)}
        if c == "primary_account_num" and lf["hash_header_account"]:
            fields[c]["aliases"].append("(a bare hash header cell)")
    added = {c: field_block("txn", c) for c in lf["added"]}
    known = set(lf["columns"]) | set(lf["added"])
    other_txn = sorted({c for cols in tr.col_reads.values() for (k, c) in cols if k == "txn" and c not in known})
    derived = sorted({(c, q) for q, s in tr.derived.items() for (k, c) in s if k == "txn"})
    odd_cols = sorted({c for cols in tr.col_reads.values() for (k, c) in cols if k == "odd"})
    odd = {c: field_block("odd", c) for c in odd_cols}
    lens_keys = sorted(k for k, v in keys.items() if "(account lenses)" in v["odd_fields"])
    return {
        "loader": {"columns": lf["columns"], "keep": lf["keep"], "added": lf["added"]},
        "fields": fields, "added_fields": added,
        "other_txn_columns": {c: field_block("txn", c) for c in other_txn},
        "derived_txn_columns": [{"column": c, "written_in": q} for c, q in derived],
        "odd_fields": odd, "lens_keys": lens_keys,
        "derived_odd_columns": {c: sorted(q for q, s in tr.derived.items() if ("odd", c) in s)
                                for c in sorted({c for s in tr.derived.values() for (k, c) in s if k == "odd"})},
        "pack_keys": keys, "slides": builders,
        "sections": tr.sections,
        "slide_keys_without_producer": {k: sorted(v) for k, v in sorted(slide_keys_missing.items())},
        "unresolved": sorted(unresolved),
    }


# ----------------------------------------------------------------------------- rendering
def _code(xs):
    return ", ".join(f"`{x}`" for x in xs) if xs else "none"


def _slides(trace, qs):
    return "; ".join(f"{trace['slides'][q]['label']} (`{trace['slides'][q]['builder']}`)" for q in qs) or "no slide"


def _esc(s: str) -> str:
    return s.replace("|", "\\|")


def render_md(trace: dict) -> str:
    L = []
    A = L.append
    A("# Transaction file field trace")
    A("")
    A("Generated by `scripts/ti_field_trace.py` from the code. Do not edit by hand: run "
      "`python scripts/ti_field_trace.py` to rebuild it (and `docs/ti_field_trace.json` beside it). "
      "`tests/test_ti_field_trace.py` fails when either file is stale.")
    A("")
    A("Each transaction field is followed from the loader (`ti/transaction_intelligence/loader.py`) "
      "through the analyses that read it (`ti/transaction_intelligence/*.py`, run by `ti/txn_sections.py`) "
      "to the pack keys they write and the slides (`ti/deck/txn_*.py`, titled in `ti/chapters_txn.py`) "
      "that draw those keys. The trace is static (Python's `ast`) and follows data flow: a key lists "
      "the fields its value was computed from, row filters included. It does not follow `if` tests, "
      "so a field used only to decide whether a key is written is not listed against that key; and "
      "within one function a reused name carries every field it was ever bound to, so a key can list "
      "a field that only shares a name with its inputs. Anything the scan cannot resolve is listed "
      "under Unresolved, never dropped.")
    A("")
    A("## Summary")
    A("")
    A("| Field | Position | Header aliases | Loader | Analyses that read it | Pack keys | Slides |")
    A("|---|---|---|---|---|---|---|")
    for c, v in trace["fields"].items():
        nkeys = len({k for r in v["sections"] for k in r["pack_keys"]})
        nsl = len({q for r in v["sections"] for q in r["slides"]})
        A(f"| `{c}` | {v['position']} | {_esc(_code(v['aliases']))} | {'kept' if v['kept'] else 'dropped (not in KEEP)'} "
          f"| {len(v['read_in'])} | {nkeys} | {nsl} |")
    for c, v in trace["added_fields"].items():
        nkeys = len({k for r in v["sections"] for k in r["pack_keys"]})
        nsl = len({q for r in v["sections"] for q in r["slides"]})
        A(f"| `{c}` | added | none | added by `read_file` | {len(v['read_in'])} | {nkeys} | {nsl} |")
    A("")
    unread = [c for c, v in trace["fields"].items() if v["kept"] and not v["read_in"]]
    A(f"Kept fields no analysis reads: {_code(unread)}. "
      f"Fields the loader drops (in COLUMNS, not in KEEP): {_code([c for c, v in trace['fields'].items() if not v['kept']])}.")
    A("")

    def field_section(name, v, head):
        A(f"### `{name}`")
        A("")
        for h in head:
            A(f"- {h}")
        A(f"- Read directly in: {_code(v['read_in'])}")
        A("")
        if not v["sections"]:
            A("No pack key depends on it.")
            A("")
            return
        A("| Section | Read in | Pack keys | Slides |")
        A("|---|---|---|---|")
        for r in v["sections"]:
            read = _code(r["read_in"]) if r["read_in"] else "through " + _code(r["via"])
            keys = _code(r["pack_keys"]) + (f" (hand-offs: {_code(r['handoffs'])})" if r["handoffs"] else "")
            A(f"| `{r['section']}` | {read} | {keys} | {_esc(_slides(trace, r['slides']))} |")
        A("")

    A("## Transaction fields")
    A("")
    for c, v in trace["fields"].items():
        head = [f"Position {v['position']} of {len(trace['loader']['columns'])} in a headerless file",
                f"Header aliases: {_esc(_code(v['aliases']))}",
                "Loader: kept" if v["kept"] else "Loader: dropped (in COLUMNS, not in KEEP), so no analysis can read it"]
        field_section(c, v, head)
    A("## Columns the loader adds")
    A("")
    for c, v in trace["added_fields"].items():
        field_section(c, v, ["Added to every frame by `loader.read_file`"])
    if trace["other_txn_columns"]:
        A("## Columns read from the transaction frame that the loader does not produce")
        A("")
        for c, v in trace["other_txn_columns"].items():
            field_section(c, v, ["Not produced by the loader"])
    A("## Columns the analyses write onto the transaction frame")
    A("")
    if trace["derived_txn_columns"]:
        A("| Column | Written in |")
        A("|---|---|")
        for d in trace["derived_txn_columns"]:
            A(f"| `{d['column']}` | `{d['written_in']}` |")
    else:
        A("None.")
    A("")
    A("## ODD fields the transaction analyses read")
    A("")
    A("Read from `ctx.frame` or from the account lenses' attribute frame (`lenses.attrs`, built by "
      "`lens.build` from the ODD). The lenses themselves (`personal`, `business`, responders and the "
      "other masks) are built in `ti/core/account_lenses.py`, outside this scan; keys that depend on "
      f"them are marked with the pseudo-field `(account lenses)`: {len(trace['lens_keys'])} keys.")
    A("")
    for c, v in trace["odd_fields"].items():
        if c == "(account lenses)":
            continue
        made = trace["derived_odd_columns"].get(c)
        field_section(c, v, [f"Not an ODD column: derived on the attribute frame by {_code(made)}"] if made else [])
    A("## Pack keys and the slides that read them")
    A("")
    A("| Pack key | Section | Transaction fields | ODD fields | Slides |")
    A("|---|---|---|---|---|")
    for k, v in trace["pack_keys"].items():
        if v["handoff"]:
            continue
        odd = [x for x in v["odd_fields"] if x != "(account lenses)"]
        if "(account lenses)" in v["odd_fields"]:
            odd.append("(account lenses)")
        A(f"| `{k}` | {_code(v['sections'])} | {_code(v['txn_fields'])} | {_esc(_code(odd))} "
          f"| {_esc(_slides(trace, v['slides']))} |")
    A("")
    A("## Hand-offs between sections")
    A("")
    A("Keys an analysis writes with a leading underscore; `ti/txn_sections.py` pops them into `ctx.shared` "
      "for a later section, so they never reach the pack.")
    A("")
    A("| Hand-off | Section | Transaction fields |")
    A("|---|---|---|")
    for k, v in trace["pack_keys"].items():
        if v["handoff"]:
            A(f"| `{k}` | {_code(v['sections'])} | {_code(v['txn_fields'])} |")
    A("")
    A("## Slides")
    A("")
    A("| Slide | Builder | Chapter | Pack keys read |")
    A("|---|---|---|---|")
    for q, s in trace["slides"].items():
        A(f"| {_esc(s['label'])} | `{q}` | {s['chapter']} | {_code(s['keys'])} |")
    A("")
    A("## Slide keys no traced section writes")
    A("")
    A("Keys a slide reads that no section in `ti/txn_sections.py` writes as far as the scan can see "
      "(written outside it, by `filed` through `ti/core/filed`, by `ti_build.py`, or not at all).")
    A("")
    if trace["slide_keys_without_producer"]:
        A("| Key | Read by |")
        A("|---|---|")
        for k, qs in trace["slide_keys_without_producer"].items():
            A(f"| `{k}` | {_code(qs)} |")
    else:
        A("None.")
    A("")
    A("## Unresolved")
    A("")
    if trace["unresolved"]:
        for u in trace["unresolved"]:
            A(f"- {u}")
    else:
        A("None.")
    A("")
    return "\r\n".join(L)


def render_json(trace: dict) -> str:
    return json.dumps(trace, indent=1, sort_keys=False, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"


def outputs() -> tuple[str, str]:
    t = build()
    return render_md(t), render_json(t)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the checked-in trace is stale")
    a = ap.parse_args(argv)
    md, js = outputs()
    if a.check:
        stale = [p for p, s in ((OUT_MD, md), (OUT_JSON, js))
                 if not p.exists() or p.read_bytes().replace(b"\r\n", b"\n") != s.encode("utf-8").replace(b"\r\n", b"\n")]
        for p in stale:
            print(f"stale: {p.relative_to(REPO)}")
        return 1 if stale else 0
    OUT_MD.write_bytes(md.encode("utf-8"))
    OUT_JSON.write_bytes(js.encode("utf-8"))
    print(f"wrote {OUT_MD.relative_to(REPO)} and {OUT_JSON.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
