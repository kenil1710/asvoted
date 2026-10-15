"""No state written before any check that can revert - for every contract.

For every @gl.public.write method (payable or not) of every contract in
contracts/, walk the statements in source order (nested defs - the nondet
leader / validator - are skipped: they never write storage) and record

  * writes:  assignments / aug-assignments / deletes whose target is rooted
             at `self` or at a local alias of storage (x = self.<...>), and
             calls to the mutating helpers (self._credit, self._settle,
             self._bump, self._drop, self._refuse) or to .append on storage;
  * reverts: `raise`, and calls to helpers that may raise (none today).

A method passes if no revert appears after its first write.

   python3 tools/scan_writes.py            (exit 1 on any violation)
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WRITER_HELPERS = {"_credit", "_settle", "_bump", "_drop", "_refuse"}
RAISING_HELPERS = set()


def is_write_method(f):
    return any(ast.unparse(d).startswith("gl.public.write") for d in f.decorator_list)


def root(node):
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Call)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else ""


def scan(f):
    aliases = {"self"}
    events = []

    def visit(stmts):
        for s in stmts:
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name):
                src = ast.unparse(s.value)
                if src.startswith("self.") and not src.startswith(("self._now", "self._sender", "self._ext",
                                                                   "self._binding", "self._input",
                                                                   "self._vote_problem", "self._standing")):
                    aliases.add(s.targets[0].id)
            nodes = [s] if isinstance(s, (ast.If, ast.For, ast.While, ast.Try, ast.With)) else list(ast.walk(s))
            if isinstance(s, (ast.If, ast.While)):
                nodes = list(ast.walk(s.test))
            for n in nodes:
                if isinstance(n, ast.Raise):
                    events.append(("revert", n.lineno, "raise"))
                elif isinstance(n, ast.Call):
                    fn = n.func
                    if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "self":
                        if fn.attr in RAISING_HELPERS:
                            events.append(("revert", n.lineno, "self." + fn.attr + "()"))
                        if fn.attr in WRITER_HELPERS:
                            events.append(("write", n.lineno, "self." + fn.attr + "()"))
                    if isinstance(fn, ast.Attribute) and fn.attr in ("append", "append_new_get") and root(fn.value) in aliases:
                        events.append(("write", n.lineno, ast.unparse(fn)))
                    if ast.unparse(fn).endswith("emit_transfer"):
                        events.append(("write", n.lineno, "emit_transfer"))
                elif isinstance(n, (ast.Assign, ast.AugAssign, ast.Delete)):
                    targets = n.targets if isinstance(n, (ast.Assign, ast.Delete)) else [n.target]
                    for t in targets:
                        if isinstance(t, (ast.Attribute, ast.Subscript)) and root(t) in aliases:
                            events.append(("write", n.lineno, ast.unparse(t)))
            if isinstance(s, ast.If):
                visit(s.body)
                visit(s.orelse)
            elif isinstance(s, (ast.For, ast.While)):
                visit(s.body)
                visit(s.orelse)
            elif isinstance(s, ast.Try):
                visit(s.body)
                for h in s.handlers:
                    visit(h.body)
                visit(s.orelse)
                visit(s.finalbody)
            elif isinstance(s, ast.With):
                visit(s.body)

    visit(f.body)
    events.sort(key=lambda e: e[1])
    first_write = next((e for e in events if e[0] == "write"), None)
    late = [e for e in events if e[0] == "revert" and first_write and e[1] > first_write[1]]
    return events, first_write, late


def run(out=sys.stdout):
    bad = 0
    rows = []
    for path in sorted((ROOT / "contracts").glob("*.py")):
        tree = ast.parse(path.read_text())
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            methods = [f for f in cls.body if isinstance(f, ast.FunctionDef) and is_write_method(f)]
            for f in methods:
                events, fw, late = scan(f)
                reverts = [e for e in events if e[0] == "revert"]
                lr = max((e for e in reverts if not fw or e[1] < fw[1]), key=lambda e: e[1], default=None)
                ok = not late
                bad += 0 if ok else 1
                rows.append((cls.name, f.name, fw, lr, ok, late))
                print(f"{(cls.name + '.' + f.name):40} first write {('L%d %s' % (fw[1], fw[2]))[:40] if fw else '-':42} "
                      f"last revert before {('L%d' % lr[1]) if lr else '-':7} {'PASS' if ok else 'FAIL ' + str(late)}", file=out)
    return bad, rows


if __name__ == "__main__":
    b, _ = run()
    sys.exit(1 if b else 0)
