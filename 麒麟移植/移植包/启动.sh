#!/bin/bash
# 抽签点名 —— 银河麒麟 / Linux 启动脚本
# 用法：双击本文件，或在终端执行  ./启动.sh

cd "$(dirname "$0")" || exit 1

echo "======================================"
echo "  抽签点名"
echo "======================================"

# 找一个可用的 Python 3
PY=""
for c in python3 /usr/bin/python3 python; do
    if command -v "$c" >/dev/null 2>&1; then
        PY="$c"
        break
    fi
done

if [ -z "$PY" ]; then
    echo
    echo "【没找到 Python3】"
    echo "请先安装： sudo apt install python3"
    echo
    read -r -p "按回车键关闭..." _
    exit 1
fi

echo "Python: $($PY --version 2>&1)"

# 检查 tkinter（图形界面必需）
if ! "$PY" -c "import tkinter" >/dev/null 2>&1; then
    echo
    echo "【缺少 tkinter 图形库】"
    echo "请执行下面这条命令安装，然后重新双击本文件："
    echo
    echo "    sudo apt install python3-tk"
    echo
    echo "（银河麒麟基于 Ubuntu/Debian，用 apt 即可）"
    echo
    read -r -p "按回车键关闭..." _
    exit 1
fi

echo "tkinter: 正常"
echo "正在启动……"
echo

exec "$PY" "抽签点名.py"
