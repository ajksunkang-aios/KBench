#!/bin/bash
# KBench retrieval setup: checkout the pinned commit and build the kgraph.db.
#
# Workflow (run this once before `kbench run`):
#   1. git checkout the pinned commit (from tasks/retrieval/manifest.json)
#   2. build a clang compile_commands.json (kernel build prerequisite)
#   3. kgraph init → build <linux>/.kgraph/kgraph.db at that commit
#
# Usage: scripts/setup_retrieval.sh <linux-tree> [<kgraph-repo>]
#
# NOTE: step 3 runs scip-clang, which is a Linux x86-64 binary — run this on Linux.
set -euo pipefail

LINUX="${1:?usage: setup_retrieval.sh <linux-tree> [<kgraph-repo>]}"
KGRAPH="${2:-$(cd "$(dirname "$0")/.." && pwd)/../KGraph}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

COMMIT="$("${PYTHON:-python3}" -c "import json,sys; print(json.load(open('$HERE/tasks/retrieval/manifest.json'))['commit']))")"
COMMIT="$(echo "$COMMIT" | tr -d '[:space:]')"

echo "== checkout $COMMIT in $LINUX =="
git -C "$LINUX" fetch --depth 1 origin "$COMMIT" 2>/dev/null || true
git -C "$LINUX" checkout "$COMMIT"

if [ ! -f "$LINUX/compile_commands.json" ]; then
  cat <<EOF
compile_commands.json missing — build the kernel with clang first:

  cd "$LINUX"
  make CC=clang LLVM=1 defconfig
  make -j"\$(nproc)" CC=clang LLVM=1
  ./scripts/clang-tools/gen_compile_commands.py

Then re-run this script (or kgraph init directly).
EOF
  exit 1
fi

echo "== build kgraph.db (scip-clang → SQLite) =="
"${PYTHON:-python3}" "$KGRAPH/src/cli/init_cmd.py" "$LINUX" --force

echo
echo "✓ ready: tree @ $COMMIT, db at $LINUX/.kgraph/kgraph.db"
echo "  now run:  python -m kbench.cli run --repo $LINUX --kgraph-repo $KGRAPH --db $LINUX/.kgraph/kgraph.db"
