# -*- coding: utf-8 -*-
r"""内部工具库 · 本地小服务（双击 启动工具库.bat 就跑这个）

为什么要它：
    浏览器不允许一个网页去读它自己旁边的文件夹（file:// 下没有列目录的
    权限），所以「打开网页就自己扫」只能靠一个能读盘的小程序代劳。
    这个脚本只监听本机 127.0.0.1，不对外、不联网。

它做的事：
    1. 起服务，顺手把 软件工具库\ 和 文档代码库\ 扫一遍；
    2. 网页每次打开、每次刷新（GET /__lib）都现扫一次 —— 不加新东西时
       几乎不花时间，所以永远是新的；
    3. 设置里改的标题 / 默认联系人，存进 admin\设置.json（POST /__lib）；
    4. 打开浏览器到 http://127.0.0.1:端口/。

路径全部用本文件所在位置推出来（不写死盘符，也不写死文件夹名），
整个文件夹拖到 P 盘、U 盘、共享盘、改成别的名字都照用。
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

sys.dont_write_bytecode = True      # 别在 admin\ 里留 __pycache__
ADMIN = os.path.dirname(os.path.abspath(__file__))     # 本脚本就在 admin\ 里
HERE = os.path.dirname(ADMIN)                          # …\内部工具库网页
sys.path.insert(0, ADMIN)

import build_index as BI           # 扫描规则只有一份，直接复用

PAGE = "软件库网站.html"
PAGE_PATH = os.path.join(ADMIN, PAGE)        # 页面收在 admin\ 里，外面只留 启动工具库.bat
SET_PATH = os.path.join(ADMIN, "设置.json")
PORTS = range(8765, 8786)          # 8765 被占就往后找

# 上次用的是哪个端口。记下来是为了下次启动只探这一个 —— 见 probe() 的注释，
# 在这台机器上盲扫 21 个端口要白等十几秒。
PORT_PATH = os.path.join(ADMIN, "运行端口.txt")
# 上次扫描的结果。启动时先吐它，页面一打开就有东西看，不用等后台扫完。
PAYLOAD_PATH = os.path.join(ADMIN, "清单缓存.json")

BUILD = "2026-11-09e"              # 页面和脚本要配套，版本对不上网页会提醒

# 什么时候退出：
#   主路 —— 页面关掉时发一个 /__bye，过 BYE_DELAY 秒没再吭声就走。
#   兜底 —— 页面崩了连招呼都没打，安静 IDLE_EXIT 秒也走。
# 兜底给得宽，是因为浏览器会把后台标签页的定时器压到一分钟一次：
# 用户切去干别的活，心跳就稀了，阈值太小会把活着的服务误杀。
BYE_DELAY = 10
IDLE_EXIT = 240

_last_seen = [0.0]                 # 最近一次收到请求的时间
_bye_at = [0.0]                    # 页面说「我关了」的时间
_ever_seen = [False]               # 是否真的有页面连上来过（没连过不退出）


# ---------------------------------------------------------------- 配置
def load_cfg():
    """config.json 是随包带的默认值；设置.json 是用户在这儿改过的，优先。"""
    cfg = {}
    if os.path.isfile(BI.CFG_PATH):
        try:
            with open(BI.CFG_PATH, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    if os.path.isfile(SET_PATH):
        try:
            with open(SET_PATH, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_cfg(patch):
    cur = {}
    if os.path.isfile(SET_PATH):
        try:
            with open(SET_PATH, encoding="utf-8") as f:
                cur = json.load(f)
        except Exception:
            cur = {}
    for k in ("title", "subtitle", "contactDefault"):
        if isinstance(patch.get(k), str):
            cur[k] = patch[k].strip()
    with open(SET_PATH, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)
    return load_cfg()


# ---------------------------------------------------------------- 扫描
def build_payload():
    cfg = load_cfg()
    BI.apply_dirs(cfg)                 # config.json 里指定了目录名就以它为准
    tools, notes = BI.scan(cfg)
    LAST["cfg"], LAST["tools"] = cfg, tools      # 留给 bake_page 写回页面用
    return {
        "config": BI.page_config(cfg),     # 带上 dirs，网页才知道两个货架叫什么
        "tools": tools,
        "notes": notes,
        "generated": time.strftime("%Y-%m-%d"),
        "at": time.strftime("%H:%M:%S"),
        "root": HERE,          # 绝对路径，网页上「复制路径」要用
        "build": BUILD,
    }


# 现在这份清单。扫描从「用户等它」变成「后台自己补」，全靠这三个值：
#   payload  最近一次扫出来的东西（启动时先从 清单缓存.json 读一份进来）
#   scanning 后台是不是正在扫，页面据此显示「正在刷新清单…」
#   error    上一次扫描的错，页面照旧用旧的清单顶着
STATE = {"payload": None, "scanning": False, "error": "", "seq": 0}
_scan_lock = threading.Lock()
LAST = {"cfg": None, "tools": None}      # 最近一次扫描的原料，写回页面要用


def bake_page():
    """把这次扫出来的清单写回页面里的数据区。

    为什么要在服务端顺手做：页面自带一份 DATA，纯网页模式（没有 Python）
    和首屏那一瞬间吃的就是它。以前只有「更新索引.bat」会刷它，于是
    「把 admin 整个替换一份」之后，页面自带的那份还是旧柜子的清单 ——
    卡片点下去是 404。现在只要开着服务打开一次页面，它自己就追上了。

    写不进去（共享盘只读、文件被占用）只打一行提示，不影响页面照常显示。
    """
    if LAST["tools"] is None:
        return
    try:
        n = BI.write_page(LAST["cfg"], LAST["tools"])
        if n:
            print("  页面自带的清单也更新了（%.0f KB）" % (n / 1024.0))
    except SystemExit as e:                  # 数据区标记被改坏了
        print("  [..] 页面自带的清单没更新：%s" % str(e).strip().splitlines()[0])
    except Exception as e:
        print("  [..] 页面自带的清单没更新：%s（不影响看网页）" % e)


def load_payload_cache():
    """读上次的扫描结果。读不到就算了，页面自己有内置的一份清单能顶着。"""
    try:
        with open(PAYLOAD_PATH, encoding="utf-8") as f:
            p = json.load(f)
        if not isinstance(p, dict) or "tools" not in p:
            return None
        p["root"] = HERE                     # 文件夹挪过位置，绝对路径要以现在为准
        p["build"] = BUILD
        p["cached"] = True                   # 告诉页面：这份是上次的，别当新鲜的
        return p
    except Exception:
        return None


def save_payload_cache(p):
    try:
        tmp = PAYLOAD_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False)
        os.replace(tmp, PAYLOAD_PATH)
    except Exception:
        pass                                 # 缓存写不进去不影响正经事


def scan_now(verbose=False):
    """扫一遍，把结果换上。给后台线程和「刷新清单」按钮共用。

    verbose=True 只在启动那一次用：把每条工具的明细打到黑窗口上，方便排查。
    之后用户点「刷新清单」再扫，只打一行汇总，别刷屏。
    """
    with _scan_lock:                         # 同时只许一个在扫
        if STATE["scanning"]:
            return
        STATE["scanning"] = True
    try:
        t0 = time.time()
        p = build_payload()
        p["seq"] = STATE["seq"] + 1
        p["ms"] = int((time.time() - t0) * 1000)
        STATE["payload"] = p
        STATE["seq"] = p["seq"]
        STATE["error"] = ""
        save_payload_cache(p)
        bake_page()                      # 顺手把页面自带那份刷新（变了才写）

        if not verbose:
            print("  清单已刷新：%d 条（%d 毫秒）" % (len(p["tools"]), p["ms"]))
        else:
            for t in p["tools"]:
                if t.get("kind") == "doc":
                    # 文档代码库没有版本号（skill 06 第 10 条），打文件数
                    print("  %-22s %-8s %s  [%d 个文件]"
                          % (t["name"][:22], t.get("contact") or "",
                             t.get("updated") or "", len(t.get("files") or [])))
                else:
                    print("  %-22s v%-6s %s"
                          % (t["name"][:22], t.get("version") or "?",
                             t.get("contact") or ""))
            for x in p["notes"]:
                print("  · " + x)
            print("  （%d 毫秒）" % p["ms"])
    except Exception as e:
        STATE["error"] = str(e)
        print("  [!] 扫描出错：%s（网页上会显示上一次的清单）" % e)
    finally:
        STATE["scanning"] = False


def lib_json():
    """给页面的清单。/__lib 和 /__scan 都从这里出，保证两边一个口径。"""
    p = STATE["payload"]
    if not p:
        p = {"config": BI.page_config(load_cfg()), "tools": [], "notes": [],
             "generated": "", "at": "", "root": HERE, "build": BUILD}
    out = dict(p)
    out["scanning"] = STATE["scanning"]
    out["error"] = STATE["error"]
    out["seq"] = STATE["seq"]
    return out


# ---------------------------------------------------------------- HTTP
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def log_message(self, *a):        # 黑窗口别刷屏
        pass

    def handle_one_request(self):
        # 浏览器常常把刚发出的请求掐掉（切页面、预读取消）。这不算错，
        # 但 socketserver 会打一整段堆栈到黑窗口，看着像崩了。吞掉。
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            self.close_connection = True

    def handle_error(self, *a):
        pass

    def _send(self, code, body, ctype, cors=False):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")   # 永远拿新的
            if cors:
                # 只为 file:// 打开的网页探活用（它的 Origin 是 null）；
                # 别的网站带着真 Origin，拿不到这个头，读不了。
                self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass                    # 对方已经走了，不算事

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    def do_GET(self):
        u = urlparse(self.path)
        p = u.path
        _last_seen[0] = time.time()
        _ever_seen[0] = True
        if p == "/__ping":
            return self._send(200, "ok " + BUILD, "text/plain; charset=utf-8", cors=True)
        if p == "/__bye":
            _bye_at[0] = time.time()
            return self._send(200, "bye", "text/plain; charset=utf-8", cors=True)

        # 只要还有别的请求进来（刷新重开、另一个标签页还在），
        # 就把「再见」作废 —— 说明还活着。
        _bye_at[0] = 0.0
        if p == "/__open":
            return self._open(u.query)
        if p == "/__copy":
            return self._copy(u.query)
        if p == "/__lib":
            # 不管后台扫没扫完，都立刻把手上这份吐出去 —— 让页面先有事干。
            # 扫描的进度靠 scanning / seq 两个字段告诉页面，页面自己决定要不要再拉一次。
            return self._json(lib_json())
        # 页面在 admin\ 里，但要在「根」上给出去 ——
        # 这样页面里的相对路径（软件工具库/x.zip）才对得上。
        if p in ("/", "/index.html"):
            return self._serve_page()
        # 直接敲 /admin/软件库网站.html 也送回根上，不然相对路径会错一层
        if unquote(p).rstrip("/").endswith("/" + PAGE):
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return
        return super().do_GET()

    def _serve_page(self):
        try:
            with open(PAGE_PATH, "r", encoding="utf-8") as f:
                html = f.read()
        except Exception as e:
            return self._send(500, "页面读不出来：%s" % e, "text/plain; charset=utf-8")
        return self._send(200, html, "text/html; charset=utf-8")

    def _open(self, query):
        """在资源管理器里打开库里的某个文件夹（网页上「打开文件夹」按钮）。

        只认带 X-Lib 头的请求：别的网站没法伪造这个头（跨域要预检），
        所以这条接口不会被外面的网页当跳板。
        """
        if self.headers.get("X-Lib") != "1":
            return self._json({"ok": False, "why": "bad request"}, 403)
        q = parse_qs(query)
        rel = unquote((q.get("p") or [""])[0]).strip()
        sel = unquote((q.get("select") or [""])[0]).strip()
        dry = (q.get("dry") or [""])[0] == "1"

        root = os.path.abspath(HERE)
        target = os.path.abspath(os.path.join(root, rel)) if rel else root
        try:
            inside = os.path.commonpath([root, target]) == root
        except ValueError:                                # 不同盘符
            inside = False
        if not inside:
            return self._json({"ok": False, "why": "越界"}, 403)
        if not os.path.exists(target):
            return self._json({"ok": False, "why": "没有这个文件夹：%s" % rel}, 404)
        if dry:
            return self._json({"ok": True, "path": target, "dry": True})

        try:
            hit = os.path.join(target, sel) if sel else ""
            if sys.platform == "darwin":
                # Mac 没有 explorer / os.startfile，用 open：
                #   open -R 文件  → 在访达里把它选中
                #   open 文件夹   → 打开这个文件夹
                if hit and os.path.isfile(hit):
                    subprocess.Popen(["open", "-R", hit])
                else:
                    subprocess.Popen(["open", target])
            elif hit and os.path.isfile(hit):             # 打开并选中那个文件
                subprocess.Popen('explorer /select,"%s"' % hit)
            else:
                os.startfile(target)                      # 打开文件夹
        except Exception as e:
            return self._json({"ok": False, "why": str(e)}, 500)
        return self._json({"ok": True, "path": target})

    def _copy(self, query):
        """把这个包本身放进剪贴板（文件，不是路径）。

        网页按钮点一下 → 到资源管理器（Mac 是访达）里右键「粘贴」，
        落下来的就是这份 zip。因为不是浏览器下载的，所以不带
        「来自 Internet」的标记。"""
        if self.headers.get("X-Lib") != "1":
            return self._json({"ok": False, "why": "bad request"}, 403)
        rel = unquote((parse_qs(query).get("p") or [""])[0]).strip()
        root = os.path.abspath(HERE)
        target = os.path.abspath(os.path.join(root, rel))
        try:
            inside = os.path.commonpath([root, target]) == root
        except ValueError:
            inside = False
        if not inside or not os.path.isfile(target):
            return self._json({"ok": False, "why": "找不到这个文件"}, 404)

        if sys.platform == "darwin":
            # Mac 没有 powershell。用 AppleScript 把「这个文件」设为剪贴板内容，
            # 访达里 ⌘V 出来就是文件本身，和 Windows 那条路的效果一样。
            script = 'set the clipboard to (POSIX file "%s")' % target.replace('"', '\\"')
            cmd = ["osascript", "-e", script]
        else:
            ps = "Set-Clipboard -Path '%s'" % target.replace("'", "''")
            cmd = ["powershell", "-NoProfile", "-STA", "-Command", ps]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=20)
        except Exception as e:
            return self._json({"ok": False, "why": str(e)}, 500)
        if r.returncode != 0:
            msg = (r.stderr or b"").decode("utf-8", "ignore").strip()[:200]
            return self._json({"ok": False, "why": msg or "放进剪贴板没成功"}, 500)
        return self._json({"ok": True, "path": target,
                           "name": os.path.basename(target)})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/__bye":                 # 页面关掉时的告别（sendBeacon 只能发 POST）
            _last_seen[0] = time.time()
            _bye_at[0] = time.time()
            return self._send(200, "bye", "text/plain; charset=utf-8", cors=True)
        if path == "/__scan":                # 「刷新清单」按钮：重扫一遍
            _bye_at[0] = 0.0                 # 还有人在点按钮，说明还活着，告别作废
            if self.headers.get("X-Lib") != "1":
                return self._json({"ok": False, "why": "bad request"}, 403)
            threading.Thread(target=scan_now, daemon=True).start()
            return self._json({"ok": True, "scanning": True})
        if path != "/__lib":
            return self._send(404, "no", "text/plain; charset=utf-8")
        _bye_at[0] = 0.0                     # 还有人在用，告别作废
        try:
            n = int(self.headers.get("Content-Length") or 0)
            patch = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return self._json({"ok": False, "why": "bad json"}, 400)
        try:
            cfg = save_cfg(patch)
        except Exception as e:
            return self._json({"ok": False, "why": str(e)}, 500)
        return self._json({"ok": True, "config": BI.page_config(cfg)})


# ---------------------------------------------------------------- 什么时候收摊
def quit_now(server):
    try:
        server.shutdown()
    except Exception:
        pass
    os._exit(0)


def watchdog(server):
    """页面关掉之后没人再来敲门，就自己退出，省得留个黑窗口。"""
    while True:
        time.sleep(2)
        if not _ever_seen[0]:
            continue                      # 还没人打开过网页，别急着走
        now = time.time()
        # 主路：页面说了再见，之后安安静静 → 走
        if _bye_at[0] and now - _bye_at[0] > BYE_DELAY:
            print("\n  浏览器已经关了，工具库跟着退出。")
            quit_now(server)
        # 兜底：没打招呼就没了（浏览器崩了、进程被杀了）
        if now - _last_seen[0] > IDLE_EXIT:
            # 提示里说哪个文件，按平台来 —— Mac 上没有 .bat，说了也白说
            launcher = "启动工具库.command" if sys.platform == "darwin" else "启动工具库.bat"
            print("\n  半天没人用了，工具库先退出。要用再双击 %s。" % launcher)
            quit_now(server)


def start_watchdog(server):
    threading.Thread(target=watchdog, args=(server,), daemon=True).start()


# ---------------------------------------------------------------- 找端口 / 复用
_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# 探活超时。**必须给得短**，原因见 pick_port() 的注释。
PROBE_TIMEOUT = 0.15


def alive(port, timeout=PROBE_TIMEOUT):
    """这个端口上是不是已经有一个我们自己的服务在跑。

    必须绕开系统代理：公司机子上挂着 HTTP_PROXY 时，urllib 会把
    127.0.0.1 也交给代理，结果明明有服务也说不通，白白再起一个。
    """
    try:
        with _NO_PROXY.open("http://127.0.0.1:%d/__ping" % port, timeout=timeout) as r:
            return r.read(2) == b"ok"
    except Exception:
        return False


def bind_ok(port):
    """这个端口现在能不能占上。bind 是瞬时的，比发一个请求快几百倍。"""
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def read_port_file():
    try:
        with open(PORT_PATH, encoding="utf-8") as f:
            n = int(f.read().strip())
        return n if n in PORTS else 0
    except Exception:
        return 0


def write_port_file(port):
    try:
        with open(PORT_PATH, "w", encoding="utf-8") as f:
            f.write(str(port))
    except Exception:
        pass


def pick_port():
    """选端口。返回 (端口, 是不是已经有一个在跑了)。都选不到就返回 (0, False)。

    **别改回「挨个端口发请求问一遍」。** 2026-11-09 实测：这台机器上连本机的
    「关着的端口」不会立刻被拒绝，而是把包悄悄丢掉、一直等到超时
    （裸 socket 连 127.0.0.1 的关闭端口实测 TimeoutError 0.60 秒，不是瞬时的
    ConnectionRefused）。照老写法 21 个端口 × 0.6 秒 ≈ 12.7 秒，全花在干等上 ——
    用户双击完先盯着空黑窗口十几秒，看着就像卡死了。

    现在的顺序：
      1. 上次用过的端口（记在 运行端口.txt）—— 只问这一个，通常问到这儿就结束；
      2. 挨个 bind 试，bind 是瞬时的；
      3. 只有 bind 失败（被别的程序占着）才去问那个端口是不是我们自己，
         而且上次问过的那个不再重复问。
    """
    last = read_port_file()
    if last and alive(last):
        return last, True

    for p in PORTS:
        if bind_ok(p):
            return p, False
        if p != last and alive(p):       # 占着它的可能是上一次没退干净的服务
            return p, True
    return 0, False


def main():
    no_open = "--no-open" in sys.argv          # 调试用：别把浏览器弹出来
    if not os.path.isfile(PAGE_PATH):
        raise SystemExit("\n[中止] 找不到 %s\n" % PAGE_PATH)

    port, running = pick_port()
    if running:                                # 已经开着一个了：不再起第二个
        url = "http://127.0.0.1:%d/" % port
        print("  工具库已经在跑了，直接把浏览器打开：%s" % url)
        if not no_open:
            webbrowser.open(url)
        return 0
    if not port:
        raise SystemExit("\n[中止] 8765~8785 都被占了，这个也解决不了，找维护者。\n")

    # 先把上次扫出来的清单读进来。页面一打开就有东西看，不用干等扫描 ——
    # 这份可能比库里实际内容旧，后台扫完页面会自己换上新的。
    STATE["payload"] = load_payload_cache()

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    start_watchdog(server)
    write_port_file(port)                      # 记下来，下次启动只探这一个
    url = "http://127.0.0.1:%d/" % port

    print("=" * 58)
    print("  内部工具库 · 本地服务")
    print("=" * 58)
    print("位置：%s" % HERE)
    print()
    print("  网页地址：%s" % url)
    print("  网页马上就打开。这个黑窗口就是工具库在干活，别手动关。")
    print("  把浏览器标签页关掉以后，它自己会跟着退出（十秒左右）。")
    print("  清单在后台扫，扫完网页自己会补上，不用等。")
    print("  要重扫（比如刚往库里放了新包），点网页上那个「刷新清单」。")
    print("-" * 58)
    print()

    # 界面是头等大事：先把浏览器叫起来，扫描丢到后台慢慢干。
    # 以前是「先扫完再开浏览器」，21 个端口盲扫加扫描能让人盯着空窗口十几秒。
    threading.Timer(0.25, lambda: (not no_open) and webbrowser.open(url)).start()
    threading.Thread(target=scan_now, kwargs={"verbose": True}, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  已停止。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        print("\n[出错] %s\n" % e)
        input("按回车关掉…")
        sys.exit(1)
