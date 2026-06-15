"""
KBench tool arms.

Two tool sets for the A/B comparison:
  - A-baseline: grep / glob / read (operate on the kernel source tree).
  - B-kgraph:   baseline + KGraph's 13 MCP tools (additive).

KGraph tools are extracted from KGraph's mcp/server.py (loaded by file path —
the mcp/ dir collides with the SDK pkg name) and called directly as plain
functions, returning the SAME formatted strings the live MCP server returns —
so the token cost measured here is faithful to real agent usage.

Each tool is exposed as an Anthropic tool definition:
  {"name", "description", "input_schema"} + a callable dispatcher.
"""
from __future__ import annotations

import importlib.util as _ilu
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


# ──────────────────────────────────────────────
# Baseline tools: grep / glob / read
# ──────────────────────────────────────────────

class BaselineTools:
    """grep/glob/read over a source tree, sandboxed under repo_root."""

    def __init__(self, repo_root: Path, grep_max_matches: int = 40,
                 read_max_lines: int = 200):
        self.root = Path(repo_root).resolve()
        self.grep_max = grep_max_matches
        self.read_max = read_max_lines

    # --- tool schemas (Anthropic input_schema) ---
    SCHEMAS = {
        "grep": {
            "description": "Search file contents recursively with a regex (like `grep -rn`). "
                           "Returns up to N matches as `path:line: text`. Search under the repo root.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "regex pattern"},
                    "glob": {"type": "string", "description": "optional file glob filter, e.g. '*.c'"},
                    "max_matches": {"type": "integer", "description": "cap on matches (default 40)"},
                },
                "required": ["pattern"],
            },
        },
        "glob": {
            "description": "Find files by glob pattern under the repo root (like `find`). "
                           "Returns relative paths.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "glob, e.g. '**/file.c' or 'fs/ext4/*.c'"},
                    "max": {"type": "integer", "description": "cap on results (default 50)"},
                },
                "required": ["pattern"],
            },
        },
        "read": {
            "description": "Read a range of lines from a file (relative to repo root). "
                           "Returns the lines with 1-based line numbers.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "repo-relative file path"},
                    "start_line": {"type": "integer", "description": "1-based start (default 1)"},
                    "end_line": {"type": "integer", "description": "1-based end (inclusive)"},
                },
                "required": ["path"],
            },
        },
    }

    def definitions(self) -> list[dict]:
        return [{"name": k, **v} for k, v in self.SCHEMAS.items()]

    def dispatch(self, name: str, args: dict) -> str:
        fn = getattr(self, f"_t_{name}", None)
        if fn is None:
            return f"unknown tool: {name}"
        try:
            return fn(args)
        except Exception as e:  # surface errors to the agent
            return f"ERROR ({name}): {type(e).__name__}: {e}"

    # --- implementations ---
    def _resolve(self, rel: str) -> Path | None:
        p = (self.root / rel).resolve()
        try:
            p.relative_to(self.root)   # sandbox
        except ValueError:
            return None
        return p

    def _t_grep(self, args: dict) -> str:
        pattern = args["pattern"]
        glob_pat = args.get("glob") or ""
        max_m = int(args.get("max_matches") or self.grep_max)
        cmd = ["grep", "-rnE", "--color=never", pattern]
        include = []
        if glob_pat:
            include = ["--include", glob_pat]
        cmd += include + ["."]
        try:
            out = subprocess.run(cmd, cwd=str(self.root), capture_output=True,
                                 text=True, timeout=60).stdout
        except subprocess.TimeoutExpired:
            return "grep timed out"
        lines = out.splitlines()
        return "\n".join(lines[:max_m]) + (f"\n... ({len(lines)-max_m} more)" if len(lines) > max_m else "")

    def _t_glob(self, args: dict) -> str:
        pattern = args["pattern"]
        max_n = int(args.get("max") or 50)
        matches = sorted(p.relative_to(self.root).as_posix()
                         for p in self.root.glob(pattern) if p.is_file())
        return "\n".join(matches[:max_n]) + (f"\n... ({len(matches)-max_n} more)" if len(matches) > max_n else "")

    def _t_read(self, args: dict) -> str:
        rel = args["path"]
        p = self._resolve(rel)
        if p is None or not p.is_file():
            return f"not found / outside repo: {rel}"
        s = int(args.get("start_line") or 1)
        e = args.get("end_line")
        lines = p.read_text(errors="replace").splitlines()
        e = int(e) if e else len(lines)
        e = min(e, s - 1 + self.read_max)
        chunk = lines[s - 1:e]
        return "\n".join(f"{i+1:>6}\t{ln}" for i, ln in enumerate(chunk, start=s))


# ──────────────────────────────────────────────
# KGraph tools: extract from mcp/server.py
# ──────────────────────────────────────────────

class KGraphTools:
    """Loads KGraph's MCP tools and exposes them as Anthropic tool defs + a dispatcher.

    Set KGRAPH_DB / KGRAPH_ROOT in env BEFORE calling load(), since server.py
    resolves them at import time.
    """

    def __init__(self, kgraph_repo: Path, db_path: Path, root: Path):
        self.kgraph_repo = Path(kgraph_repo)
        self.db_path = Path(db_path)
        self.root = Path(root)
        self._mod = None
        self._tools: dict[str, Any] = {}   # name -> Tool

    def load(self):
        # server.py reads these at import time.
        os.environ["KGRAPH_DB"] = str(self.db_path)
        os.environ["KGRAPH_ROOT"] = str(self.root)
        for sub in ("src", "scripts"):
            p = str(self.kgraph_repo / sub)
            if p not in sys.path:
                sys.path.insert(0, p)
        server_py = self.kgraph_repo / "mcp" / "server.py"
        spec = _ilu.spec_from_file_location("kgraph_server", str(server_py))
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self._mod = mod
        self._tools = dict(mod.mcp._tool_manager._tools)

    def definitions(self) -> list[dict]:
        defs = []
        for name, t in self._tools.items():
            defs.append({
                "name": t.name,
                "description": (t.description or "").strip(),
                "input_schema": t.parameters,
            })
        return defs

    def dispatch(self, name: str, args: dict) -> str:
        if name not in self._tools:
            return f"unknown tool: {name}"
        fn = getattr(self._mod, name, None)
        if fn is None:
            return f"tool not callable: {name}"
        try:
            return str(fn(**args))
        except Exception as e:
            return f"ERROR ({name}): {type(e).__name__}: {e}"


# ──────────────────────────────────────────────
# Arm assembly
# ──────────────────────────────────────────────

def build_arm(arm: str, repo_root: Path, kgraph_repo: Path | None,
              db_path: Path | None) -> tuple[list[dict], Callable[[str, dict], str]]:
    """Return (tool_definitions, dispatch) for an arm.

    arm: "A-baseline" or "B-kgraph".
    """
    baseline = BaselineTools(repo_root)
    if arm == "A-baseline":
        return baseline.definitions(), baseline.dispatch

    if arm == "B-kgraph":
        if not kgraph_repo or not db_path:
            raise ValueError("B-kgraph requires --kgraph-repo and --db")
        kg = KGraphTools(kgraph_repo, db_path, repo_root)
        kg.load()
        base_defs = baseline.definitions()
        kg_defs = kg.definitions()
        # additive: baseline + KGraph (dedup by name, KGraph wins on conflict)
        by_name = {d["name"]: d for d in base_defs}
        for d in kg_defs:
            by_name[d["name"]] = d

        def dispatch(name: str, args: dict) -> str:
            if name in kg._tools:
                return kg.dispatch(name, args)
            return baseline.dispatch(name, args)

        return list(by_name.values()), dispatch

    raise ValueError(f"unknown arm: {arm}")
