"""Restricted formula grammar -> AST -> parameterized DuckDB SQL.

Raw SQL is NEVER accepted. Users write a small expression language:

    formula   := expr [ WHERE bool ]
    expr      := term (('+'|'-') term)*
    term      := unary (('*'|'/'|'%') unary)*
    unary     := '-' unary | primary
    primary   := NUMBER | STRING | DATE 'YYYY-MM-DD' | '(' expr ')' | call | IDENT | '[' Metric Name ']'
    call      := NAME '(' [expr (',' expr)*] ')'      -- whitelisted functions only
    bool      := or-expression of comparisons (=, !=, <>, <, <=, >, >=, IN, BETWEEN, IS [NOT] NULL, LIKE)

Every literal becomes a bound parameter. Every identifier is validated against the dataset schema and quoted.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

MAX_FORMULA_LEN = 2000
MAX_DEPTH = 40

KEYWORDS = {"AND", "OR", "NOT", "IN", "IS", "NULL", "TRUE", "FALSE", "LIKE", "ILIKE", "BETWEEN", "WHERE", "DATE"}
AGG_FUNCS = {"SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT", "MEDIAN", "STDDEV"}
COND_AGG = {"SUMIF", "COUNTIF", "AVGIF"}
SCALAR_FUNCS = {"ABS", "ROUND", "COALESCE", "IF", "NULLIF", "UPPER", "LOWER", "YEAR", "MONTH", "LENGTH"}
GRAINS = {"day", "week", "month", "quarter", "year"}


class FormulaError(Exception):
    def __init__(self, message: str, pos: int = 0):
        super().__init__(message)
        self.message = message
        self.pos = pos

    def to_dict(self) -> dict:
        return {"message": self.message, "position": self.pos}


# ----------------------------------------------------------------------------- lexer
@dataclass
class Tok:
    kind: str  # NUM STR ID KW REF OP LP RP COMMA EOF
    value: str
    pos: int


_NUM = re.compile(r"\d+(?:\.\d+)?")
_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_REF = re.compile(r"\[([A-Za-z0-9 _\-().&/]{1,80})\]")


def tokenize(text: str) -> list[Tok]:
    if len(text) > MAX_FORMULA_LEN:
        raise FormulaError(f"Formula too long (max {MAX_FORMULA_LEN} characters)")
    if "--" in text or "/*" in text or "*/" in text:
        raise FormulaError("Comments are not allowed in formulas", max(text.find("--"), text.find("/*"), 0))
    toks: list[Tok] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c.isdigit():
            m = _NUM.match(text, i)
            toks.append(Tok("NUM", m.group(), i))
            i = m.end()
            continue
        if c == "'":
            j, buf = i + 1, []
            while True:
                if j >= n:
                    raise FormulaError("Unterminated string literal", i)
                if text[j] == "'":
                    if j + 1 < n and text[j + 1] == "'":
                        buf.append("'")
                        j += 2
                        continue
                    break
                buf.append(text[j])
                j += 1
            s = "".join(buf)
            if len(s) > 500 or "\x00" in s:
                raise FormulaError("Invalid string literal", i)
            toks.append(Tok("STR", s, i))
            i = j + 1
            continue
        if c.isalpha() or c == "_":
            m = _ID.match(text, i)
            word = m.group()
            up = word.upper()
            toks.append(Tok("KW" if up in KEYWORDS else "ID", up if up in KEYWORDS else word, i))
            i = m.end()
            continue
        if c == "[":
            m = _REF.match(text, i)
            if not m:
                raise FormulaError("Invalid metric reference; use [Metric Name]", i)
            toks.append(Tok("REF", m.group(1).strip(), i))
            i = m.end()
            continue
        two = text[i : i + 2]
        if two in ("<=", ">=", "<>", "!="):
            toks.append(Tok("OP", "!=" if two == "<>" else two, i))
            i += 2
            continue
        if c in "+-*/%=<>":
            toks.append(Tok("OP", c, i))
            i += 1
            continue
        if c == "(":
            toks.append(Tok("LP", c, i))
            i += 1
            continue
        if c == ")":
            toks.append(Tok("RP", c, i))
            i += 1
            continue
        if c == ",":
            toks.append(Tok("COMMA", c, i))
            i += 1
            continue
        raise FormulaError(f"Unexpected character {c!r}", i)
    toks.append(Tok("EOF", "", n))
    return toks


# ----------------------------------------------------------------------------- parser
Node = tuple  # ("kind", ...)


@dataclass
class Parsed:
    expr: Node | None
    where: Node | None
    text: str


class Parser:
    def __init__(self, text: str):
        self.text = text
        self.toks = tokenize(text)
        self.i = 0
        self.depth = 0

    @property
    def cur(self) -> Tok:
        return self.toks[self.i]

    def peek(self, k: int = 1) -> Tok:
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def eat(self, kind: str, value: str | None = None) -> Tok:
        t = self.cur
        if t.kind != kind or (value is not None and t.value != value):
            want = value or {"RP": ")", "LP": "(", "EOF": "end of formula", "COMMA": ",", "STR": "a text value in quotes"}.get(kind, kind)
            raise FormulaError(f"Expected {want!r} but found {t.value or 'end of formula'!r}", t.pos)
        self.i += 1
        return t

    def accept(self, kind: str, value: str | None = None) -> Tok | None:
        t = self.cur
        if t.kind == kind and (value is None or t.value == value):
            self.i += 1
            return t
        return None

    def _enter(self):
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise FormulaError("Expression nested too deeply", self.cur.pos)

    def _leave(self):
        self.depth -= 1

    # formula := expr [WHERE bool]
    def parse_formula(self) -> Parsed:
        if self.cur.kind == "EOF":
            raise FormulaError("Formula is empty", 0)
        expr = self.parse_expr()
        where = None
        if self.accept("KW", "WHERE"):
            where = self.parse_bool()
        self.eat("EOF")
        return Parsed(expr, where, self.text)

    def parse_condition(self) -> Parsed:
        if self.cur.kind == "EOF":
            raise FormulaError("Condition is empty", 0)
        b = self.parse_bool()
        self.eat("EOF")
        return Parsed(None, b, self.text)

    def parse_expr(self) -> Node:
        self._enter()
        node = self.parse_term()
        while self.cur.kind == "OP" and self.cur.value in "+-" and len(self.cur.value) == 1:
            op = self.cur.value
            self.i += 1
            node = ("bin", op, node, self.parse_term())
        self._leave()
        return node

    def parse_term(self) -> Node:
        node = self.parse_unary()
        while self.cur.kind == "OP" and self.cur.value in ("*", "/", "%"):
            op = self.cur.value
            self.i += 1
            node = ("bin", op, node, self.parse_unary())
        return node

    def parse_unary(self) -> Node:
        if self.cur.kind == "OP" and self.cur.value == "-":
            self.i += 1
            return ("neg", self.parse_unary())
        return self.parse_primary()

    def parse_primary(self) -> Node:
        t = self.cur
        if t.kind == "NUM":
            self.i += 1
            return ("num", float(t.value) if "." in t.value else int(t.value))
        if t.kind == "STR":
            self.i += 1
            return ("str", t.value)
        if t.kind == "KW" and t.value == "DATE":
            self.i += 1
            s = self.eat("STR")
            if not _is_iso_date(s.value):
                raise FormulaError("DATE literal must be 'YYYY-MM-DD'", s.pos)
            return ("date", s.value)
        if t.kind == "KW" and t.value in ("TRUE", "FALSE"):
            self.i += 1
            return ("bool", t.value == "TRUE")
        if t.kind == "KW" and t.value == "NULL":
            self.i += 1
            return ("null",)
        if t.kind == "REF":
            self.i += 1
            return ("ref", t.value, t.pos)
        if t.kind == "LP":
            self.i += 1
            self._enter()
            node = self.parse_expr()
            self._leave()
            self.eat("RP")
            return node
        if t.kind == "OP" and t.value == "*":
            raise FormulaError("'*' is only valid as COUNT(*)", t.pos)
        if t.kind == "ID":
            self.i += 1
            if self.cur.kind == "LP":
                return self.parse_call(t)
            return ("col", t.value, t.pos)
        raise FormulaError(f"Unexpected {t.value or 'end of formula'!r}", t.pos)

    def parse_call(self, name_tok: Tok) -> Node:
        name = name_tok.value.upper()
        if name not in AGG_FUNCS | COND_AGG | SCALAR_FUNCS:
            allowed = ", ".join(sorted(AGG_FUNCS | COND_AGG | SCALAR_FUNCS))
            raise FormulaError(f"Function '{name_tok.value}' is not allowed. Allowed: {allowed}", name_tok.pos)
        self.eat("LP")
        args: list[Node] = []
        if self.cur.kind == "OP" and self.cur.value == "*":
            if name != "COUNT":
                raise FormulaError("'*' is only valid in COUNT(*)", self.cur.pos)
            self.i += 1
            args.append(("star",))
        elif self.cur.kind != "RP":
            while True:
                args.append(self.parse_arg(name, len(args)))
                if not self.accept("COMMA"):
                    break
        self.eat("RP")
        return ("call", name, args, name_tok.pos)

    def parse_arg(self, fname: str, idx: int) -> Node:
        # condition arguments are boolean expressions
        if (fname in ("SUMIF", "AVGIF") and idx == 1) or (fname == "COUNTIF" and idx == 0) or (fname == "IF" and idx == 0):
            return self.parse_bool()
        return self.parse_expr()

    # ------------- boolean layer
    def parse_bool(self) -> Node:
        self._enter()
        node = self.parse_and()
        while self.accept("KW", "OR"):
            node = ("or", node, self.parse_and())
        self._leave()
        return node

    def parse_and(self) -> Node:
        node = self.parse_not()
        while self.accept("KW", "AND"):
            node = ("and", node, self.parse_not())
        return node

    def parse_not(self) -> Node:
        if self.accept("KW", "NOT"):
            return ("not", self.parse_not())
        return self.parse_cmp()

    def parse_cmp(self) -> Node:
        # '(' may open a bool group or an arithmetic group: try bool first, backtrack on failure
        if self.cur.kind == "LP":
            save = self.i
            try:
                self.i += 1
                inner = self.parse_bool()
                self.eat("RP")
                if not (self.cur.kind == "OP" or (self.cur.kind == "KW" and self.cur.value in ("IN", "BETWEEN", "IS", "LIKE", "ILIKE", "NOT"))):
                    if _is_boolish(inner):
                        return inner
            except FormulaError:
                pass
            self.i = save
        left = self.parse_expr()
        t = self.cur
        if t.kind == "OP" and t.value in ("=", "!=", "<", "<=", ">", ">="):
            self.i += 1
            return ("cmp", t.value, left, self.parse_expr())
        neg = False
        if t.kind == "KW" and t.value == "NOT":
            neg = True
            self.i += 1
            t = self.cur
        if t.kind == "KW" and t.value == "IN":
            self.i += 1
            self.eat("LP")
            items = [self.parse_expr()]
            while self.accept("COMMA"):
                items.append(self.parse_expr())
            self.eat("RP")
            if len(items) > 200:
                raise FormulaError("IN list too long (max 200)", t.pos)
            return ("in", left, items, neg)
        if t.kind == "KW" and t.value == "BETWEEN":
            self.i += 1
            lo = self.parse_expr()
            self.eat("KW", "AND")
            hi = self.parse_expr()
            return ("between", left, lo, hi, neg)
        if t.kind == "KW" and t.value in ("LIKE", "ILIKE"):
            self.i += 1
            pat = self.eat("STR")
            return ("like", left, pat.value, neg, t.value == "ILIKE")
        if neg:
            raise FormulaError("Expected IN, BETWEEN or LIKE after NOT", t.pos)
        if t.kind == "KW" and t.value == "IS":
            self.i += 1
            n2 = bool(self.accept("KW", "NOT"))
            self.eat("KW", "NULL")
            return ("isnull", left, n2)
        # bare boolean column/literal
        return ("truthy", left)


def _is_boolish(node: Node) -> bool:
    return node[0] in ("cmp", "in", "between", "like", "isnull", "and", "or", "not", "bool", "truthy")


def _is_iso_date(s: str) -> bool:
    try:
        date.fromisoformat(s)
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s))
    except ValueError:
        return False


def parse_formula(text: str) -> Parsed:
    return Parser(text.strip()).parse_formula()


def parse_condition(text: str) -> Parsed:
    return Parser(text.strip()).parse_condition()


# ----------------------------------------------------------------------------- AST utilities
def walk(node, fn):
    if isinstance(node, tuple):
        fn(node)
        for ch in node[1:]:
            if isinstance(ch, (tuple, list)):
                if isinstance(ch, list):
                    for x in ch:
                        walk(x, fn)
                else:
                    walk(ch, fn)


def extract_refs(parsed: Parsed) -> list[str]:
    out: list[str] = []

    def f(n):
        if n[0] == "ref" and n[1] not in out:
            out.append(n[1])

    for part in (parsed.expr, parsed.where):
        if part:
            walk(part, f)
    return out


def extract_aggregations(parsed: Parsed) -> list[str]:
    out: list[str] = []

    def f(n):
        if n[0] == "call" and n[1] in (AGG_FUNCS | COND_AGG):
            out.append(n[1])

    if parsed.expr:
        walk(parsed.expr, f)
    return sorted(set(out))


def canonical(node: Node | None) -> str:
    """Normalized rendering used for semantic equality (commutative operands sorted, case folded)."""
    if node is None:
        return ""
    k = node[0]
    if k == "num":
        return repr(node[1])
    if k == "str":
        return "'" + node[1] + "'"
    if k == "date":
        return "DATE'" + node[1] + "'"
    if k == "bool":
        return "TRUE" if node[1] else "FALSE"
    if k == "null":
        return "NULL"
    if k == "star":
        return "*"
    if k == "col":
        return node[1].lower()
    if k == "ref":
        return "[" + node[1].lower() + "]"
    if k == "neg":
        return "(-" + canonical(node[1]) + ")"
    if k == "bin":
        a, b = canonical(node[2]), canonical(node[3])
        if node[1] in "+*":
            a, b = sorted([a, b])
        return f"({a}{node[1]}{b})"
    if k == "call":
        return node[1] + "(" + ",".join(canonical(a) for a in node[2]) + ")"
    if k == "cmp":
        return f"({canonical(node[2])}{node[1]}{canonical(node[3])})"
    if k == "in":
        return f"({canonical(node[1])}{' NOT' if node[3] else ''} IN [{','.join(sorted(canonical(i) for i in node[2]))}])"
    if k == "between":
        return f"({canonical(node[1])}{' NOT' if node[4] else ''} BETWEEN {canonical(node[2])},{canonical(node[3])})"
    if k == "like":
        return f"({canonical(node[1])}{' NOT' if node[3] else ''} LIKE '{node[2]}')"
    if k == "isnull":
        return f"({canonical(node[1])} IS{' NOT' if node[2] else ''} NULL)"
    if k in ("and", "or"):
        a, b = sorted([canonical(node[1]), canonical(node[2])])
        return f"({a} {k.upper()} {b})"
    if k == "not":
        return f"(NOT {canonical(node[1])})"
    if k == "truthy":
        return canonical(node[1])
    return str(node)


def canonical_formula(parsed: Parsed) -> str:
    return canonical(parsed.expr) + (" WHERE " + canonical(parsed.where) if parsed.where else "")


# ----------------------------------------------------------------------------- compiler
@dataclass
class Compiled:
    sql: str
    params: list
    type: str  # numeric | string | date | bool | null
    agg: bool = False
    row: bool = False  # references row-level columns outside an aggregate


@dataclass
class CompileResult:
    sql: str
    params: list
    type: str
    columns: set[str] = field(default_factory=set)
    aggregations: set[str] = field(default_factory=set)
    metrics: list[str] = field(default_factory=list)
    where: list = field(default_factory=list)  # list[Compiled]


def qident(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_ ]*", name):
        raise FormulaError(f"Illegal identifier {name!r}")
    return '"' + name.replace('"', '""') + '"'


MetricResolver = Callable[[str], "tuple[Parsed, Parsed | None] | None"]


class Compiler:
    """schema: {column_name: category} with category in numeric|string|date|bool."""

    def __init__(self, schema: dict[str, str], resolver: MetricResolver | None = None):
        self.schema = schema
        self.lower = {k.lower(): k for k in schema}
        self.resolver = resolver
        self.columns: set[str] = set()
        self.aggs: set[str] = set()
        self.metrics: list[str] = []
        self._stack: list[str] = []

    # --- public
    def compile_formula(self, parsed: Parsed, extra_where: list[Parsed] | None = None) -> "CompileResult":
        where_parts: list[Compiled] = []
        for w in [parsed.where] + [p.where for p in (extra_where or [])]:
            if w is not None:
                where_parts.append(self._where(w))
        body = self._expr(parsed.expr, in_agg=False, filters=[])
        if body.row:
            raise FormulaError(
                "Formula mixes row-level columns with aggregates, or has no aggregate. Wrap columns in SUM(), COUNT(), AVG()..."
            )
        if not body.agg:
            raise FormulaError("Formula must contain at least one aggregate function (e.g. SUM(net_sales))")
        if body.type != "numeric":
            raise FormulaError("Formula must evaluate to a number")
        return CompileResult(
            body.sql, list(body.params), body.type, set(self.columns), set(self.aggs), list(self.metrics), where_parts
        )

    def compile_condition(self, node: Node) -> Compiled:
        return self._where(node)

    # --- internals
    def _where(self, node: Node) -> Compiled:
        c = self._bool(node, in_agg=True, filters=[])
        if c.agg:
            raise FormulaError("Aggregates are not allowed in WHERE / filter conditions")
        return c

    def _col(self, name: str, pos: int) -> Compiled:
        real = self.lower.get(name.lower())
        if real is None:
            sug = difflib.get_close_matches(name.lower(), list(self.lower), n=1, cutoff=0.6)
            hint = f". Did you mean '{self.lower[sug[0]]}'?" if sug else f". Available: {', '.join(list(self.schema)[:15])}"
            raise FormulaError(f"Unknown column '{name}'{hint}", pos)
        self.columns.add(real)
        return Compiled(qident(real), [], self.schema[real], row=True)

    def _expr(self, n: Node, in_agg: bool, filters: list[Compiled]) -> Compiled:
        k = n[0]
        if k == "num":
            return Compiled("?", [n[1]], "numeric")
        if k == "str":
            return Compiled("?", [n[1]], "string")
        if k == "date":
            return Compiled("CAST(? AS DATE)", [n[1]], "date")
        if k == "bool":
            return Compiled("TRUE" if n[1] else "FALSE", [], "bool")
        if k == "null":
            return Compiled("NULL", [], "null")
        if k == "col":
            c = self._col(n[1], n[2])
            return c if in_agg else c
        if k == "ref":
            return self._ref(n, filters)
        if k == "neg":
            c = self._expr(n[1], in_agg, filters)
            self._need_num(c, "unary minus")
            return Compiled(f"(-{c.sql})", c.params, "numeric", c.agg, c.row)
        if k == "bin":
            return self._bin(n, in_agg, filters)
        if k == "call":
            return self._call(n, in_agg, filters)
        if k in ("cmp", "in", "between", "like", "isnull", "and", "or", "not", "truthy"):
            return self._bool(n, in_agg, filters)
        raise FormulaError(f"Unsupported expression {k}")

    def _need_num(self, c: Compiled, what: str):
        if c.type not in ("numeric", "null"):
            raise FormulaError(f"{what} requires a numeric operand, got {c.type}")

    def _bin(self, n: Node, in_agg: bool, filters: list[Compiled]) -> Compiled:
        op = n[1]
        a = self._expr(n[2], in_agg, filters)
        b = self._expr(n[3], in_agg, filters)
        self._need_num(a, f"'{op}'")
        self._need_num(b, f"'{op}'")
        agg, row = a.agg or b.agg, a.row or b.row
        if agg and row:
            raise FormulaError("Cannot mix aggregated values with row-level columns in one expression")
        if op == "/":
            sql = f"({a.sql} / NULLIF({b.sql}, 0))"
        elif op == "%":
            sql = f"({a.sql} % NULLIF({b.sql}, 0))"
        else:
            sql = f"({a.sql} {op} {b.sql})"
        return Compiled(sql, a.params + b.params, "numeric", agg, row)

    def _ref(self, n: Node, filters: list[Compiled]) -> Compiled:
        name = n[1]
        if self.resolver is None:
            raise FormulaError(f"Metric reference [{name}] cannot be resolved in this context", n[2])
        if name.lower() in self._stack:
            raise FormulaError(f"Circular metric reference: {' -> '.join(self._stack + [name.lower()])}", n[2])
        if len(self._stack) >= 5:
            raise FormulaError("Metric references nested too deeply (max 5)", n[2])
        res = self.resolver(name)
        if res is None:
            raise FormulaError(f"Unknown or unpublished metric [{name}]", n[2])
        sub, sub_filter = res
        if name not in self.metrics:
            self.metrics.append(name)
        self._stack.append(name.lower())
        try:
            local_filters = list(filters)
            for w in (sub.where, sub_filter.where if sub_filter else None):
                if w is not None:
                    local_filters.append(self._where(w))
            c = self._expr(sub.expr, False, local_filters)
        finally:
            self._stack.pop()
        if c.row or not c.agg:
            raise FormulaError(f"Metric [{name}] is not a pure aggregate formula", n[2])
        return c

    def _call(self, n: Node, in_agg: bool, filters: list[Compiled]) -> Compiled:
        name, args, pos = n[1], n[2], n[3]
        if name in AGG_FUNCS or name in COND_AGG:
            if in_agg:
                raise FormulaError(f"Nested aggregate {name}() is not allowed", pos)
            self.aggs.add(name)
            return self._agg(name, args, filters, pos)
        # scalar functions
        cs = [self._expr(a, in_agg, filters) for a in args]
        agg = any(c.agg for c in cs)
        row = any(c.row for c in cs)
        if agg and row:
            raise FormulaError("Cannot mix aggregated values with row-level columns in one expression", pos)
        params = [p for c in cs for p in c.params]

        def need(cnt: int | tuple):
            ok = len(cs) == cnt if isinstance(cnt, int) else len(cs) in cnt
            if not ok:
                raise FormulaError(f"{name}() takes {cnt} argument(s), got {len(cs)}", pos)

        if name == "ABS":
            need(1)
            self._need_num(cs[0], "ABS")
            return Compiled(f"ABS({cs[0].sql})", params, "numeric", agg, row)
        if name == "ROUND":
            need((1, 2))
            self._need_num(cs[0], "ROUND")
            digits = 0
            if len(args) == 2:
                if args[1][0] != "num" or not isinstance(args[1][1], int) or not 0 <= args[1][1] <= 10:
                    raise FormulaError("ROUND digits must be an integer literal 0-10", pos)
                digits = args[1][1]
            return Compiled(f"ROUND({cs[0].sql}, {digits})", cs[0].params, "numeric", agg, row)
        if name == "COALESCE":
            if len(cs) < 2:
                raise FormulaError("COALESCE() needs at least 2 arguments", pos)
            t = next((c.type for c in cs if c.type != "null"), "null")
            for c in cs:
                if c.type not in (t, "null"):
                    raise FormulaError("COALESCE arguments must share one type", pos)
            return Compiled(f"COALESCE({', '.join(c.sql for c in cs)})", params, t, agg, row)
        if name == "NULLIF":
            need(2)
            return Compiled(f"NULLIF({cs[0].sql}, {cs[1].sql})", params, cs[0].type, agg, row)
        if name == "IF":
            need(3)
            if cs[0].type != "bool":
                raise FormulaError("IF() first argument must be a condition", pos)
            if cs[1].type not in (cs[2].type, "null") and cs[2].type != "null":
                raise FormulaError("IF() branches must have the same type", pos)
            t = cs[1].type if cs[1].type != "null" else cs[2].type
            return Compiled(f"(CASE WHEN {cs[0].sql} THEN {cs[1].sql} ELSE {cs[2].sql} END)", params, t, agg, row)
        if name in ("UPPER", "LOWER"):
            need(1)
            if cs[0].type != "string":
                raise FormulaError(f"{name}() requires a text column", pos)
            return Compiled(f"{name}({cs[0].sql})", params, "string", agg, row)
        if name == "LENGTH":
            need(1)
            if cs[0].type != "string":
                raise FormulaError("LENGTH() requires a text column", pos)
            return Compiled(f"LENGTH({cs[0].sql})", params, "numeric", agg, row)
        if name in ("YEAR", "MONTH"):
            need(1)
            if cs[0].type != "date":
                raise FormulaError(f"{name}() requires a date column", pos)
            return Compiled(f"{name}({cs[0].sql})", params, "numeric", agg, row)
        raise FormulaError(f"Unsupported function {name}", pos)

    def _agg(self, name: str, args: list[Node], filters: list[Compiled], pos: int) -> Compiled:
        def fsql() -> tuple[str, list]:
            if not filters:
                return "", []
            return " FILTER (WHERE " + " AND ".join(f.sql for f in filters) + ")", [p for f in filters for p in f.params]

        if name == "COUNT":
            if len(args) != 1:
                raise FormulaError("COUNT() takes exactly one argument (a column or *)", pos)
            fs, fp = fsql()
            if args[0][0] == "star":
                return Compiled(f"COUNT(*){fs}", fp, "numeric", agg=True)
            c = self._expr(args[0], True, [])
            return Compiled(f"COUNT({c.sql}){fs}", c.params + fp, "numeric", agg=True)
        if name == "COUNTIF":
            if len(args) != 1:
                raise FormulaError("COUNTIF(condition) takes one argument", pos)
            cond = self._bool(args[0], True, [])
            fs, fp = fsql()
            return Compiled(f"COUNT(CASE WHEN {cond.sql} THEN 1 END){fs}", cond.params + fp, "numeric", agg=True)
        if name in ("SUMIF", "AVGIF"):
            if len(args) != 2:
                raise FormulaError(f"{name}(expr, condition) takes two arguments", pos)
            val = self._expr(args[0], True, [])
            cond = self._bool(args[1], True, [])
            self._need_num(val, name)
            fs, fp = fsql()
            fn = "SUM" if name == "SUMIF" else "AVG"
            # text order: CASE WHEN cond THEN val
            return Compiled(f"{fn}(CASE WHEN {cond.sql} THEN {val.sql} END){fs}", cond.params + val.params + fp, "numeric", agg=True)
        if len(args) != 1:
            raise FormulaError(f"{name}() takes exactly one argument", pos)
        c = self._expr(args[0], True, [])
        if name in ("SUM", "AVG", "MEDIAN", "STDDEV"):
            if c.type != "numeric":
                raise FormulaError(f"{name}() requires a numeric expression, got {c.type}. Check the column type.", pos)
        fs, fp = fsql()
        if name == "COUNT_DISTINCT":
            return Compiled(f"COUNT(DISTINCT {c.sql}){fs}", c.params + fp, "numeric", agg=True)
        rt = c.type if name in ("MIN", "MAX") else "numeric"
        if name in ("MIN", "MAX") and c.type == "bool":
            raise FormulaError(f"{name}() cannot be applied to boolean values", pos)
        fn = "STDDEV_SAMP" if name == "STDDEV" else name
        return Compiled(f"{fn}({c.sql}){fs}", c.params + fp, rt, agg=True)

    # --- boolean layer
    def _bool(self, n: Node, in_agg: bool, filters: list[Compiled]) -> Compiled:
        k = n[0]
        if k in ("and", "or"):
            a, b = self._bool(n[1], in_agg, filters), self._bool(n[2], in_agg, filters)
            return Compiled(f"({a.sql} {k.upper()} {b.sql})", a.params + b.params, "bool", a.agg or b.agg, a.row or b.row)
        if k == "not":
            a = self._bool(n[1], in_agg, filters)
            return Compiled(f"(NOT {a.sql})", a.params, "bool", a.agg, a.row)
        if k == "truthy":
            a = self._expr(n[1], in_agg, filters)
            if a.type != "bool":
                raise FormulaError("Expected a condition (e.g. region = 'EU')")
            return a
        if k == "cmp":
            op = n[1]
            a = self._expr(n[2], in_agg, filters)
            b = self._expr(n[3], in_agg, filters)
            a, b = self._coerce(a, b, n[2], n[3])
            if a.type != b.type and "null" not in (a.type, b.type):
                raise FormulaError(f"Cannot compare {a.type} with {b.type}")
            if a.type == "bool" and op not in ("=", "!="):
                raise FormulaError("Booleans only support = and !=")
            sqlop = "<>" if op == "!=" else op
            return Compiled(f"({a.sql} {sqlop} {b.sql})", a.params + b.params, "bool", a.agg or b.agg, a.row or b.row)
        if k == "in":
            x = self._expr(n[1], in_agg, filters)
            items = []
            for it in n[2]:
                c = self._expr(it, in_agg, filters)
                x2, c2 = self._coerce(x, c, n[1], it)
                if c2.type != x2.type:
                    raise FormulaError(f"IN list item type {c2.type} does not match {x2.type}")
                items.append(c2)
            sql = f"({x.sql} {'NOT ' if n[3] else ''}IN ({', '.join(i.sql for i in items)}))"
            return Compiled(sql, x.params + [p for i in items for p in i.params], "bool", x.agg, x.row)
        if k == "between":
            x = self._expr(n[1], in_agg, filters)
            lo, hi = self._expr(n[2], in_agg, filters), self._expr(n[3], in_agg, filters)
            x1, lo = self._coerce(x, lo, n[1], n[2])
            x2, hi = self._coerce(x, hi, n[1], n[3])
            if not (x1.type == lo.type == hi.type):
                raise FormulaError("BETWEEN operands must share one type")
            return Compiled(
                f"({x.sql} {'NOT ' if n[4] else ''}BETWEEN {lo.sql} AND {hi.sql})",
                x.params + lo.params + hi.params, "bool", x.agg, x.row,
            )
        if k == "like":
            x = self._expr(n[1], in_agg, filters)
            if x.type != "string":
                raise FormulaError("LIKE requires a text column")
            op = "ILIKE" if n[4] else "LIKE"
            return Compiled(f"({x.sql} {'NOT ' if n[3] else ''}{op} ?)", x.params + [n[2]], "bool", x.agg, x.row)
        if k == "isnull":
            x = self._expr(n[1], in_agg, filters)
            return Compiled(f"({x.sql} IS {'NOT ' if n[2] else ''}NULL)", x.params, "bool", x.agg, x.row)
        # arithmetic/other expression in boolean position
        c = self._expr(n, in_agg, filters)
        if c.type != "bool":
            raise FormulaError("Expected a condition")
        return c

    def _coerce(self, a: Compiled, b: Compiled, na: Node, nb: Node) -> tuple[Compiled, Compiled]:
        """date column vs ISO string literal -> DATE; numeric strings are NOT coerced."""
        if a.type == "date" and b.type == "string" and nb[0] == "str":
            if not _is_iso_date(nb[1]):
                raise FormulaError(f"'{nb[1]}' is not a valid date (use YYYY-MM-DD)")
            return a, Compiled("CAST(? AS DATE)", [nb[1]], "date")
        if b.type == "date" and a.type == "string" and na[0] == "str":
            if not _is_iso_date(na[1]):
                raise FormulaError(f"'{na[1]}' is not a valid date (use YYYY-MM-DD)")
            return Compiled("CAST(? AS DATE)", [na[1]], "date"), b
        return a, b


def categorize(duck_type: str) -> str:
    t = duck_type.upper()
    if any(x in t for x in ("INT", "DOUBLE", "FLOAT", "DECIMAL", "REAL", "NUMERIC", "HUGEINT")):
        return "numeric"
    if t.startswith("TIMESTAMP") or t == "DATE" or t.startswith("DATE"):
        return "date"
    if t == "BOOLEAN":
        return "bool"
    return "string"
