#!/usr/bin/env bash
# 一键复刻「秋招信息工作台」同款：build 顶层 我的素材库 → 我的信息台.html
# 用法：bash build_my_desk.sh   （mac 双击也行）
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
"$PY" "$DIR/scripts/build_desk.py" --lib "$DIR/我的素材库" --out "$DIR/我的信息台.html"
if command -v open >/dev/null 2>&1; then open "$DIR/我的信息台.html"; fi
