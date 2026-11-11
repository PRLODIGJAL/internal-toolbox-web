#!/bin/bash
# ============================================================
#  内部工具库 —— Mac 双击启动（对应 Windows 的「启动工具库.bat」）
#
#  干的事和 .bat 一样：起一个只监听 127.0.0.1 的本地小服务，再把网页打开。
#  为什么要它：浏览器不允许一个网页去读它自己旁边的文件夹，所以「打开就
#  自己扫」只能靠一个能读盘的小程序代劳。它不对外、不联网。
#
#  ⚠️ 和 .bat 唯一的不同：这里**不先开 file:// 的网页**，而是让服务自己把
#     浏览器开在 http://127.0.0.1:端口/ 上。原因有两个：
#       1) Mac 上 Safari 对 file:// 页面去 fetch http://127.0.0.1 有额外限制，
#          页面可能探不到服务，于是就一直是「离线清单」，按钮也降级；
#       2) 从 http 打开时页面和服务同源，「打开文件夹 / 复制」这些功能直接就通。
#     Mac 上 Python 起得很快（实测扫描 59 毫秒），不需要像 Windows 共享盘那样
#     先开页面遮掉 8~11 秒的空窗期，所以这个顺序反而更简单也更稳。
#
#  找 Python 的顺序（重要）：
#    1. runtime/bin/python3   —— 随包带的 Mac 运行时（有就优先，免装任何东西）
#    2. Homebrew 的 python3   （Apple Silicon 在 /opt/homebrew，Intel 在 /usr/local）
#    3. python.org 框架版
#    4. /usr/bin/python3      —— macOS 自带的（需要装过 Xcode 命令行工具）
#    5. 都没有                —— 退化成「只开网页」，见下面的提示
#
#  ⚠️ 现在的 runtime/ 是 Windows 版（里面是 python.exe），Mac 上用不了，
#     所以这里会跳过它去找 runtime/bin/python3。哪天给 Mac 也配一份运行时，
#     直接放进 runtime/ 就会被自动优先使用，这个脚本一个字都不用改。
#
#  ⚠️ 双击时 Finder 给的 PATH 只有 /usr/bin:/bin:/usr/sbin:/sbin，
#     所以下面全用绝对路径去试，不能只靠 command -v。
# ============================================================
cd "$(dirname "$0")" || exit 1
HERE="$(pwd)"

HTML="$HERE/admin/软件库网站.html"
SERVE="$HERE/admin/serve.py"

if [ ! -f "$HTML" ] || [ ! -f "$SERVE" ]; then
  echo "找不到 admin/软件库网站.html 或 admin/serve.py"
  echo "这个包不完整，把整个文件夹重新拷一份。"
  echo
  read -r -p "按回车键关闭…"
  exit 1
fi

# ---------------------------------------------------------------- 找 Python
PY=""
if [ -x "$HERE/runtime/bin/python3" ]; then
  PY="$HERE/runtime/bin/python3"
else
  for c in \
      /opt/homebrew/bin/python3 \
      /usr/local/bin/python3 \
      /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
      /usr/bin/python3
  do
    if [ -x "$c" ]; then PY="$c"; break; fi
  done
fi
# 最后再问一次 PATH（有些人的 Python 装在别处并进了 PATH）
if [ -z "$PY" ] && command -v python3 >/dev/null 2>&1; then
  PY="$(command -v python3)"
fi

# ------------------------------------------------- 没 Python：只开网页
if [ -z "$PY" ]; then
  cat <<'EOF'

  ==========================================================
    内部工具库 · 纯网页模式
  ==========================================================

    这台电脑上没找到 Python，本地小服务起不来，直接把网页打开。

      能用    ：浏览、搜索、下载
      不能用  ：打开文件夹、复制到剪贴板
                （这两个按钮会自动改成「复制路径」，
                  粘到访达的「前往 → 前往文件夹」里一样能到）

    想要完整功能，两条路：
      · 在 runtime/ 里放一份 Mac 版 Python（免安装）
      · 或者装一个 python3（Homebrew / python.org 都行）

  ==========================================================

EOF
  open "$HTML"
  sleep 6
  exit 0
fi

# ------------------------------------------------- 正常：起服务，由它开浏览器
echo "  内部工具库 · Mac"
echo "  Python: $PY"
echo
echo "  版本: $("$PY" -V 2>&1)"
echo "  关掉浏览器标签页后，这个窗口会自己退出（十秒左右）。"
echo

"$PY" "$SERVE" "$@"
RC=$?

if [ "$RC" -ne 0 ]; then
  echo
  echo "  [!] 退出了，退出码 $RC。上面那段是原因。"
  echo
  read -r -p "按回车键关闭…"
fi
exit "$RC"
