#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
内部工具库 · 刷新页面
=====================

扫一遍 软件工具库\ 和 文档代码库\，把里面的东西写进页面。

库里分两柜，规矩不一样
    软件工具库   能下载下来装到本机的离线工具。全是 Windows 的，留历史版本。
    文档代码库   skill / 代码 / 规范这类不用安装、直接看或直接拖走的东西。
                 不产生历史版本；改动记录写在《IT工程部_项目总表》里。

目录规矩（一柜一个文件夹，两柜写法一样）
    软件工具库\<工具名><版本><姓名>\
        某某工具 2.0 Windows版.zip     ← 当前版本，放一个
        某某工具 1.0 Windows版.zip     ← 历史版本，可以放好几个
        总说明.md                      ← 标准名。由《IT工程部_项目总表》渲染，别手写
                                         老的 说明.txt 还认（第一行当一句话简介）

    文档代码库\<工具名><版本><姓名>\
        工程统一基线skill\             ← 文件本体，子文件夹多深都收
        使用说明书.md
        总说明.md                      ← 网页靠它取卡片简介和说明

  例：软件工具库\WI一致性检查工具2.0用户\

  文件夹名中间夹不夹空格都行，两柜同一套规矩：
      WI一致性检查工具2.0用户     ← 连写，跟资源管理器里一模一样（推荐）
      WI一致性检查 2.0 用户        ← 空格分开，老写法也还认
  三样东西会变成页面上的：工具名、版本号、负责人。
  版本号前面写不写 v 都行（2.0 和 v2.0 一样），整数也认（3 就是 3）。

  版本号以文件夹名为准（两柜一致）。包名里的版本只用来排历史顺序，
  两边对不上时脚本会提示一句，但页面显示的是文件夹名写的那个。

  包文件名里认版本号：带小数点的优先，只写整数也认。
  包名里写不写「Windows版」都行，不影响认版本号 —— 库里只按 Windows 处理。

  同一个文件夹放好几个 zip 时，版本号最高的那个算"当前版本"，
  其余的自动变成卡片上「历史 N」按钮里的内容，不用另外登记。
  文档代码库没有历史版本这一说：一个文件夹一条，同名文件夹并排放着
  （1.0 和 1.1 都在）时只显示版本最高的那个，并提示删旧的。

  说明书一律叫 总说明.md，一个文件夹只要一份（2026-11-09 定的，跟 skill v2.0 对齐）。
  总说明.md 由 sync_manual.py 从《IT工程部_项目总表》渲染出来，不许手改 ——
  手改的下次一渲染就没了。老的 说明.txt 继续认（第一行当一句话简介），
  但新放进去的一律用 总说明.md。
  两样都没有也能跑：软件那边会退到读 zip 里的 使用说明书。

改目录名
  三个文件夹的名字写在下面 DIRS 里（就一处）。真要换名字，
  改那三行就行，或者写进 config.json 的 "dirs"，代码不用动。
  本脚本自己住在 admin\ 里，这个位置是从文件路径现算的，不写死。

页面外观就是那个 html 文件本身 —— 想改长相直接改它，刷新不会覆盖你。
脚本只替换这两行标记之间的内容：

      /*__DATA_BEGIN__*/
      const CONFIG = {...};
      const DATA   = {...};
      /*__DATA_END__*/

用 法
  双击 更新索引.bat（或者 python build_index.py），没有参数。
"""

import hashlib
import json
import os
import re
import sys
import time
import zipfile
from datetime import datetime

# 这份脚本住在 admin\ 里，工具库根目录是它上一层。
# admin 这个名字不写死：从文件自己的位置推，改成什么叫什么都行。
ADMIN_DIR = os.path.dirname(os.path.abspath(__file__))
HERE = os.path.dirname(ADMIN_DIR)

# ---------------------------------------------------------------- 目录名
# 三个文件夹的名字只在这里写一次。页面、服务、扫描全从这儿取，
# 想换名字（比如把「软件工具库」改成「工具柜」）只改这三行；
# 懒得改代码就写进 config.json 的 "dirs"，一样的。
DIRS = {
    "admin": os.path.basename(ADMIN_DIR),   # 脚本自己住的这个，实测出来的
    "lib":   "软件工具库",                  # 柜一：能装的离线工具，留历史版本
    "doc":   "文档代码库",                  # 柜二：skill / 代码 / 规范，不留历史
}

# 页面文件名。要改名就改这一行，别的不用动。
PAGE_NAME = "软件库网站.html"
PAGE_DIR = ADMIN_DIR                 # 页面收在 admin\ 里，外面只留 启动工具库.bat
OUT_PATH = os.path.join(PAGE_DIR, PAGE_NAME)
# config.json 和这份脚本住在一起，跟工具库根目录无关
CFG_PATH = os.path.join(ADMIN_DIR, "config.json")


def dir_of(which):
    """柜子的绝对路径：dir_of("lib") / dir_of("doc")"""
    return os.path.join(HERE, DIRS[which])


def apply_dirs(cfg):
    """config.json 里给了 "dirs" 就以它为准，不然用上面 DIRS 的默认值。"""
    d = (cfg or {}).get("dirs") or {}
    for k in ("admin", "lib", "doc"):
        v = (d.get(k) or "").strip()
        if v and k != "admin":          # admin 永远是脚本所在的真实目录
            DIRS[k] = v
    return DIRS

BEGIN = "/*__DATA_BEGIN__*/"
END = "/*__DATA_END__*/"

# 根目录那份说明认哪几个名字。**总说明.md 排第一** —— 那是 skill v2.0 定的标准名
# （09-说明书上架同步.md：项目层那份只能从总表渲染，六段结构）。
# 老库里叫 说明.txt 的继续认，不然一改名卡片就全空。
DOC_NAMES = ["总说明.md", "说明.txt", "先看我.txt", "README.txt",
             "使用说明书.txt", "使用说明.txt"]
DOC_LIMIT = 20000           # 页面上最多塞这么多字（再长就提示看文件）
DESC_LIMIT = 80             # 说明.txt 第一行超过这么长就不当简介用
ZIP_JUNK = ("._", ".DS_Store")
# 包里那份「操作说明书」长什么样
MANUAL_RE = re.compile(r"说明|readme|手册|指南|操作|manual", re.I)
MANUAL_EXT = re.compile(r"\.(txt|md|pdf|docx?|chm|html?)$", re.I)

FOLDER_TIP = "工具名+版本号+姓名"


def _init_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def say(msg=""):
    print(msg)


def load_json(path, label):
    with open(path, "r", encoding="utf-8-sig") as f:
        raw = f.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise SystemExit(
            "\n[中止] %s 不是合法的 JSON：第 %d 行第 %d 列\n"
            "        %s\n\n"
            "        最常见的原因：\n"
            "          1. 多了一个或少了一个逗号\n"
            "          2. 用了中文引号 “ ” 而不是英文 \"\n"
            "          3. 最后一项后面多留了一个逗号\n" % (label, e.lineno, e.colno, e.msg)
        )


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# 校验码缓存：按「绝对路径 + 大小 + 修改时间」认，三者都没变就直接拿上次的。
# 为什么要有它：571MB 的包整份读一遍要 1.5 秒，而这个值只在网页「说明」弹窗里
# 露一眼，不是关键路径 —— 不该每进一次页面就重算一遍。
# 文件删了留下的死记录不影响什么（一条一百多字节），嫌乱可以直接删这个 json。
CACHE_FILE = os.path.join(ADMIN_DIR, "索引缓存.json")


def cache_load():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def cache_save(store):
    try:
        tmp = CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False)
        os.replace(tmp, CACHE_FILE)      # 先写临时文件再换，写一半断电也不会留坏文件
    except Exception:
        pass                             # 缓存写不进去不算事，下次重算就是


def sha256_cached(path, store):
    """带缓存的 sha256。store 就是一个 dict，调用方管读写。"""
    st = os.stat(path)
    key = "%s|%d|%d" % (os.path.abspath(path), st.st_size, int(st.st_mtime))
    got = store.get(key)
    if got:
        return got
    got = sha256_of(path)
    store[key] = got
    return got


def human_size(n):
    if n < 1024:
        return "%d B" % n
    if n < 1024 * 1024:
        return "%.0f KB" % (n / 1024.0)
    return "%.1f MB" % (n / 1048576.0)


# ---------------------------------------------------------------- 文件夹名
def space_cjk(s):
    """PDF差异对比 → PDF 差异对比（英文和汉字之间留一格，好认）"""
    s = re.sub(r"([A-Za-z0-9])([\u4e00-\u9fff])", r"\1 \2", s or "")
    return re.sub(r"([\u4e00-\u9fff])([A-Za-z0-9])", r"\1 \2", s)


# 文件夹名里的版本号：先认带小数点的（2.0 / 6.1），再认光秃秃的整数（3）
_VER_DOTTED = re.compile(r"(?<![\d.])[vV]?(\d+(?:\.\d+)+)(?![\d.])")
# 整数版得多两道防线，免得把 PDF2Word 里的 2 当版本
_VER_INT = re.compile(r"(?<![A-Za-z0-9.])[vV]?(\d+)(?![A-Za-z0-9.])")


def parse_folder(name, people=()):
    """「WI一致性检查工具2.0用户」→（WI 一致性检查工具, 2.0, 用户）

    几种写法都认，两柜用同一套：
        工具名版本姓名       ← 连写，跟资源管理器里的文件夹名一模一样
        工具名 版本 姓名      ← 空格分开（老写法，还认）
        工具名姓名           ← 文档代码库不带版本，姓名靠 people 名单认（见下）
    规则：先找版本号，找得到就前头是工具名、后头是负责人；
    找不到版本号，就看名字结尾是不是 config.json 里 "people" 写的人。
    """
    raw = (name or "").strip()
    if not raw:
        return "", "", ""

    # 一、空格分开的：中间那段正好是纯版本号，最不容易认错
    tokens = [t for t in re.split(r"\s+", raw) if t]
    for i, t in enumerate(tokens):
        if re.match(r"^[vV]?\d+(?:\.\d+)*$", t):
            return (space_cjk(" ".join(tokens[:i])) or " ".join(tokens),
                    re.sub(r"^[vV]", "", t),
                    " ".join(tokens[i + 1:]).strip())

    # 二、连写的：在整串里找版本号，从那儿把名字切成两段
    for rx in (_VER_DOTTED, _VER_INT):
        m = rx.search(raw)
        if not m:
            continue
        head = raw[:m.start()].strip()
        tail = raw[m.end():].strip()
        if head and tail:                # 两头都得有东西，才像个正经名字
            return space_cjk(head), re.sub(r"^[vV]", "", m.group(1)), tail

    # 三、没有版本号（文档代码库现在就不写版本）：看结尾是不是名单里的人。
    #     不认识的名字不乱切 —— 整串当工具名，负责人留空走默认联系人，
    #     总比把「WI一致性检查」的「检查」当成人名强。
    for who in sorted([p for p in (people or []) if p], key=len, reverse=True):
        if raw.endswith(who) and len(raw) > len(who):
            return space_cjk(raw[:-len(who)]), "", who

    # 四、实在认不出来：整串当名字，版本和人留空，交给默认值
    return space_cjk(raw), "", ""


def norm(s):
    return re.sub(r"[\s\-_·．.]+", "", (s or "").lower())


def pick_rule(name, rules):
    """可选的 config.json > info 表：想覆盖文件夹名算出来的名字时用。"""
    nb = norm(name)
    hit = None
    for key, val in (rules or {}).items():
        nk = norm(key)
        if nk and nk in nb and (hit is None or len(nk) > len(norm(hit[0]))):
            hit = (key, val or {})
    return hit[1] if hit else {}


# ---------------------------------------------------------------- 读包
def zip_top_names(zf):
    return [n for n in zf.namelist()
            if "/" not in n and not any(j in n for j in ZIP_JUNK)]


def zip_root(zf, prefix=""):
    """包根目录有哪些文件、哪些文件夹。
    prefix 给了就只看那一层（有的包外头又套了一层同名文件夹）。
    顺手把包里那份「操作说明书」挑出来 —— 每个版本的操作说明跟着版本走，
    就躺在各自的包里，外层那份只讲用途。"""
    files, dirs = [], []
    manuals = []
    for info in zf.infolist():
        n = info.filename
        if info.is_dir():
            continue
        if any(j in n for j in ZIP_JUNK):
            continue
        if MANUAL_RE.search(n) and MANUAL_EXT.search(n) and len(manuals) < 4:
            if n not in [m["n"] for m in manuals]:
                manuals.append({"n": n, "size": info.file_size})
        rel = n
        if prefix:
            if not rel.startswith(prefix):
                continue
            rel = rel[len(prefix):]
        if not rel:
            continue
        seg = rel.split("/")[0]
        if "/" not in rel:
            if rel not in files:
                files.append(rel)
        elif seg and seg not in dirs:
            dirs.append(seg)
    manuals.sort(key=lambda m: len(m["n"]))
    return files, dirs, manuals[:3]


def _scan_launch(files, dirs):
    launch = prep = ""
    for n in sorted(files + dirs):
        low = n.lower()
        if not low.endswith(".bat"):
            continue
        if "环境准备" in n or "setup" in low:
            prep = prep or n
        elif "启动" in n or "start" in low:
            launch = launch or n
    return launch, prep


def find_launch(zf):
    """启动器 + 环境准备。只认 .bat —— 库里的东西全是 Windows 的。
    根上找不到、又只有一个顶层文件夹时，往里再看一层：
    有的包解开后先是一个同名文件夹，启动器在里头。"""
    files, dirs, _manuals = zip_root(zf)
    launch, prep = _scan_launch(files, dirs)
    if not launch and len(dirs) == 1:
        f2, d2, _m2 = zip_root(zf, dirs[0] + "/")
        l2, p2 = _scan_launch(f2, d2)
        launch = launch or l2
        prep = prep or p2
    return launch, prep


def read_doc(folder, zf):
    """说明书：先看文件夹里那份，没有再往包里翻。"""
    for n in DOC_NAMES:
        p = os.path.join(folder, n)
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
                    txt = f.read().strip()
            except OSError:
                continue
            if txt:
                return txt

    names = zip_top_names(zf)
    for n in [x for x in names if "先看我" in x] + \
             [x for x in names if re.search(r"(使用)?说明", x) and x.lower().endswith((".txt", ".md"))]:
        try:
            txt = zf.read(n).decode("utf-8-sig", "replace").strip()
        except Exception:
            continue
        if txt:
            return txt
    return ""


def first_line(text, title=""):
    """说明文件里那句话，当卡片上的一句话简介。

    两种写法都认：
    · `说明.txt` —— 第一行就是那句话（超过 80 字就不当简介用，卡片上放不下）
    · `总说明.md` —— 按 skill `09` 的六段结构，取「## 一句话」下面那段；
      没有这一节就取第一个正文段。标题行（`# P04　…`）和紧跟的灰行
      （`效率类 · 用户 · 已完结 · v2.0 · 2026-11-06`）都要跳过，不然卡片上会
      顶着「# P04　自动铺满图片VBA」和一串分类标签。
    """
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.strip() for ln in raw.split("\n")]
    is_rule = lambda s: bool(re.match(r"^[\s=—\-_·*#]{3,}$", s))

    # 一、Markdown：总说明.md 的结构
    if any(ln.startswith("#") for ln in lines):
        start = None
        for k, ln in enumerate(lines):
            if re.match(r"^#{1,3}\s*一句话\s*$", ln):
                start = k + 1
                break
        if start is not None:
            for ln in lines[start:]:
                if ln.startswith("#"):
                    break                  # 这一节空着，交给下面的兜底
                if ln and not is_rule(ln):
                    return ln          # 「一句话」本来就为列表页写的，长一点也留
        for ln in lines:
            if not ln or ln.startswith("#") or is_rule(ln):
                continue
            if ln.count(" · ") >= 2:        # 灰行：分类 · 部门 · 状态 · 版本 · 日期
                continue
            return ln if len(ln) <= DESC_LIMIT else ""
        return ""

    # 二、纯文本：老规矩
    body = [ln for ln in lines if ln and not is_rule(ln)]
    if not body:
        return ""
    first = body[0]
    if title and (title in first or first in title) and len(body) > 1:
        first = body[1]
    return first if len(first) <= DESC_LIMIT else ""


# ---------------------------------------------------------------- 扫目录
SYS_NOISE = re.compile(r"windows|win11|win10|\bwin\b", re.I)


def ver_of(fname):
    """从文件名里捞版本号：PDF对比工具 6.0 Windows版.zip → 6.0
    带小数点的优先；只有整数时先去掉系统名，免得把「Windows 10」的 10 当版本。"""
    s0 = re.sub(r"\.zip$", "", fname or "", flags=re.I)
    m = re.search(r"(\d+(?:\.\d+)+)", s0)
    if m:
        return m.group(1)
    s1 = SYS_NOISE.sub(" ", s0)
    m = re.search(r"(?<![\d.])(\d+)(?![\d.])", s1)
    return m.group(1) if m else ""


def ver_key(v):
    """按 . 分段转成数字元组，好做比较：6.10 > 6.9"""
    out = []
    for part in str(v or "0").split("."):
        try:
            out.append(int(part))
        except ValueError:
            out.append(0)
    return tuple(out)


def collect():
    """一个文件夹里可以躺多个版本的 zip，全部收进来。"""
    found = []
    lib = dir_of("lib")
    if not os.path.isdir(lib):
        return found

    for name in sorted(os.listdir(lib)):
        p = os.path.join(lib, name)
        if name.startswith((".", "_")):
            continue

        if os.path.isdir(p):
            zips = [f for f in sorted(os.listdir(p))
                    if f.lower().endswith(".zip") and not f.startswith((".", "_"))]
            if not zips:
                continue
            items = [{"pkg": z, "path": os.path.join(p, z), "v": ver_of(z)} for z in zips]
            found.append({"name": name, "dir": name, "zips": items})
        elif name.lower().endswith(".zip"):
            # 兼容：直接丢在根目录的包，也能列出来，但不推荐
            found.append({"name": os.path.splitext(name)[0], "dir": "",
                          "zips": [{"pkg": name, "path": p, "v": ver_of(name)}]})
    return found


def scan_apps(cfg, store=None):
    rules = cfg.get("info") or {}
    default_contact = (cfg.get("contactDefault") or "").strip()
    people = cfg.get("people") or []
    tools, notes = [], []
    lib = dir_of("lib")

    if not os.path.isdir(lib):
        os.makedirs(lib, exist_ok=True)
        return [], ["没有 %s\\ 目录，已新建一个空的。按「%s」建文件夹再放包"
                    % (DIRS["lib"], FOLDER_TIP)]

    for e in collect():
        title, version, owner = parse_folder(e["name"], people)
        rule = pick_rule(e["name"], rules)
        folder = os.path.join(lib, e["dir"]) if e["dir"] else lib

        def rel(pkg):
            return DIRS["lib"] + "/" + (e["dir"] + "/" if e["dir"] else "") + pkg

        # 版本号最高的当当前版，其余进历史
        group = sorted(e["zips"], key=lambda x: ver_key(x["v"]), reverse=True)
        cur, older = group[0], group[1:]
        with zipfile.ZipFile(cur["path"]) as zf:
            launch, prep = find_launch(zf)
            doc = read_doc(folder, zf)
            _f, _d, manuals = zip_root(zf)
        st = os.stat(cur["path"])
        entry = {
            # 版本以文件夹名为准 —— 和文档代码库一个规矩：
            # 文件夹名是人手写的、跟资源管理器看得见的一致；
            # 包名里的版本只用来排历史顺序，不顺眼时脚本会提示一句。
            "version": version or cur["v"] or "?",
            "pkg": cur["pkg"],
            "pkgPath": rel(cur["pkg"]),
            "size": st.st_size,
            "sha256": "",
            "updated": time.strftime("%Y-%m-%d", time.localtime(st.st_mtime)),
            "launch": launch,
            "prep": prep,
            "manual": manuals,
            "older": [],
        }
        for o in older:
            ost = os.stat(o["path"])
            entry["older"].append({
                "v": o["v"] or "?",
                "pkg": o["pkg"],
                "pkgPath": rel(o["pkg"]),
                "size": ost.st_size,
                "updated": time.strftime("%Y-%m-%d", time.localtime(ost.st_mtime)),
            })
        try:
            entry["sha256"] = (sha256_cached(cur["path"], store) if store is not None
                               else sha256_of(cur["path"]))
        except OSError as ex:
            notes.append("算校验码失败（%s）：%s" % (cur["pkg"], ex))

        if version and cur["v"] and ver_key(cur["v"]) != ver_key(version):
            notes.append("「%s」文件夹名写 %s，包里最新的是 %s —— 页面按文件夹名显示"
                         % (e["name"], version, cur["v"]))
        if not owner:
            notes.append("「%s」的文件夹名里没写负责人（建议写成「%s」）"
                         % (e["name"], FOLDER_TIP))
        # 说明文件认 DOC_NAMES 里那一串，不只认 说明.txt。
        # 2026-11-09 起库里几个柜开始放 总说明.md（skill v2.0 定的标准名），
        # 只认 说明.txt 的话，明明有说明的文件夹也会被报「没有说明」。
        have_doc = next((n for n in DOC_NAMES
                         if os.path.isfile(os.path.join(folder, n))), "")
        if not have_doc:
            notes.append("「%s」里没有 总说明.md（老的 说明.txt 也认）" % e["name"])

        shown = doc
        if len(doc) > DOC_LIMIT:
            shown = doc[:DOC_LIMIT].rstrip() + "\n\n……（太长了，后面的看文件夹里的 %s）" \
                    % (have_doc or "说明")

        tools.append({
            "id": norm(e["name"]) or e["name"],
            "name": (rule.get("name") or "").strip() or title or e["name"],
            # 文件夹原名（工具名+版本+负责人，一个不差）。
            # 软件柜的卡片标题直接用它，这样「谁负责」不用在角落里再写一遍。
            "folder": e["name"] or title,
            "kind": "app",
            "desc": (rule.get("desc") or "").strip() or first_line(doc, title),
            "note": (rule.get("note") or "").strip(),
            "cat": (rule.get("cat") or "").strip(),
            "contact": (rule.get("contact") or owner or default_contact).strip(),
            "order": rule.get("order") if isinstance(rule.get("order"), int) else 100,
            "readme": shown,
            "docName": have_doc,
            "version": entry["version"],
            "pkg": entry["pkg"],
            "pkgPath": entry["pkgPath"],
            "size": entry["size"],
            "sha256": entry["sha256"],
            "updated": entry["updated"],
            "launch": entry["launch"],
            "prep": entry["prep"],
            "manual": entry["manual"],
            "older": entry["older"],
        })

    tools.sort(key=lambda t: (t["order"], t["name"]))
    return tools, notes


# ---------------------------------------------------------------- 扫 文档代码库
DOC_JUNK = ("._", ".DS_Store")


def doc_files(root):
    """把一个文档代码文件夹里所有文件收进来，路径照原样留着 —— skill 靠层级认东西。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith((".", "_"))]
        for fn in filenames:
            if fn.startswith(DOC_JUNK) or fn == ".DS_Store":
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            try:
                st = os.stat(full)
            except OSError:
                continue
            out.append({"n": rel, "size": st.st_size, "mtime": st.st_mtime})
    # 根目录的文件排前面，其余按路径排
    out.sort(key=lambda f: ("/" in f["n"], f["n"]))
    return out


def read_doc_plain(root, files):
    """根目录那份说明：先认固定名（总说明.md 优先），再认长得像的。"""
    roots = [f["n"] for f in files if "/" not in f["n"]]
    for want in DOC_NAMES + ["使用说明书.md", "说明.md", "总说明.txt"]:
        if want in roots:
            p = os.path.join(root, want)
            try:
                with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
                    txt = f.read().strip()
            except OSError:
                continue
            if txt:
                return txt, want
    for n in roots:
        if re.match(r"^(总说明|使用说明书|说明|先看我|readme)", n, re.I) and \
                n.lower().endswith((".txt", ".md")):
            try:
                with open(os.path.join(root, n), "r", encoding="utf-8-sig", errors="replace") as f:
                    txt = f.read().strip()
            except OSError:
                continue
            if txt:
                return txt, n
    return "", ""


def scan_docs(cfg):
    rules = cfg.get("info") or {}
    default_contact = (cfg.get("contactDefault") or "").strip()
    people = cfg.get("people") or []
    tools, notes = [], []
    doc_root = dir_of("doc")

    if not os.path.isdir(doc_root):
        return tools, notes

    for name in sorted(os.listdir(doc_root)):
        p = os.path.join(doc_root, name)
        if name.startswith((".", "_")) or not os.path.isdir(p):
            continue

        files = doc_files(p)
        if not files:
            continue

        title, _version, owner = parse_folder(name, people)
        rule = pick_rule(name, rules)
        doc, doc_name = read_doc_plain(p, files)

        # 「看文件」里只列真正要拿的东西：说明书本身不算 —— 它在「说明」弹窗里
        # 已经完整显示了，混进清单会让「一个压缩包」看着像两个文件。
        goods = [f for f in files if f["n"] != doc_name] or files

        total = sum(f["size"] for f in files)
        newest = max(f["mtime"] for f in files)
        shown = doc
        if len(doc) > DOC_LIMIT:
            shown = doc[:DOC_LIMIT].rstrip() + "\n\n……（太长了，后面的看文件夹里的 %s）" % (doc_name or "说明")

        if not doc_name:
            notes.append("「%s」里没有 总说明.md（老的 说明.txt 也认），简介和说明会空着" % name)
        if not owner:
            notes.append("「%s」的文件夹名里没认出负责人（写成「工具名+姓名」，"
                         "姓名要跟 config.json 的 people 对得上）" % name)

        tools.append({
            "id": norm(name) or name,
            "name": (rule.get("name") or "").strip() or title or name,
            "kind": "doc",
            "desc": (rule.get("desc") or "").strip() or first_line(doc, title),
            "note": (rule.get("note") or "").strip(),
            "cat": (rule.get("cat") or "").strip(),
            "contact": (rule.get("contact") or owner or default_contact).strip(),
            "order": rule.get("order") if isinstance(rule.get("order"), int) else 100,
            "readme": shown,
            "docName": doc_name,
            "updated": time.strftime("%Y-%m-%d", time.localtime(newest)),
            "size": total,
            "dir": DIRS["doc"] + "/" + name,
            "files": [{"n": f["n"], "size": f["size"],
                       "rel": DIRS["doc"] + "/" + name + "/" + f["n"]} for f in goods],
        })

    # 文档代码库不留旧版：万一有人把同名文件夹并排放着（只是大小写/空格不同），
    # 只显示内容最新改过的那一个
    keep = {}
    for t in tools:
        k = norm(t["name"])
        old = keep.get(k)
        if old is None or t["updated"] > old["updated"]:
            keep[k] = t
    if len(keep) < len(tools):
        notes.append("%s 里有同名文件夹，页面只显示最新改过的那个（旧的可以删掉）"
                     % DIRS["doc"])

    out = list(keep.values())
    out.sort(key=lambda t: (t["order"], t["name"]))
    return out, notes


def scan(cfg):
    store = cache_load()                     # 上次算过的校验码
    apps, notes = scan_apps(cfg, store)
    docs, notes2 = scan_docs(cfg)
    cache_save(store)                        # 这次新算的也一起写回去
    return apps + docs, notes + notes2


def dump_js(obj):
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return s.replace("</", "<\\/")      # 防止提前闭合 script


def page_config(cfg):
    """写进页面的 CONFIG：在 config.json 的基础上补一份 dirs。

    网页得知道两个货架叫什么（拼下载路径、认 file:// 下的上一级），
    这样改名只在 Python 这边改一处，JavaScript 不用跟着改。
    """
    out = dict(cfg or {})
    out.pop("info", None)          # info 是给人改名字用的规则表，页面用不上
    out["dirs"] = dict(DIRS)
    return out


def write_page(cfg, tools):
    with open(OUT_PATH, "r", encoding="utf-8") as f:
        page = f.read()

    i = page.find(BEGIN)
    j = page.find(END)
    if i < 0 or j < 0 or j < i:
        raise SystemExit(
            "\n[中止] %s 里找不到数据区标记 %s / %s\n"
            "        这个文件是页面本体，被改坏就只能换一份回来。\n"
            "        数据区那三行在 <script> 里，格式是：\n"
            "            %s\n"
            "            const CONFIG = {...};\n"
            "            const DATA   = {...};\n"
            "            %s\n" % (PAGE_NAME, BEGIN, END, BEGIN, END)
        )

    data = {
        "generated": datetime.now().strftime("%Y-%m-%d"),
        "tools": tools,
    }
    block = ("\nconst CONFIG = %s;\nconst DATA   = %s;\n"
             % (dump_js(page_config(cfg)), dump_js(data)))

    new = page[:i + len(BEGIN)] + block + page[j:]
    if new == page:
        return 0                     # 一模一样就不写，免得共享盘上白改一次时间戳
    # 先写 .tmp 再整体换上去。两点考虑：
    #   1) 写一半崩了，页面本体还是好的 —— 这个文件坏了只能换一份回来；
    #   2) 服务端现在扫完会自动写回，共享盘上可能有两三个人同时开着库。
    tmp = OUT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    os.replace(tmp, OUT_PATH)
    return len(new.encode("utf-8"))


def main():
    _init_console()
    say()
    say("=" * 58)
    say("  内部工具库 · 刷新页面")
    say("=" * 58)
    say("位置：%s" % HERE)

    if not os.path.isfile(OUT_PATH):
        raise SystemExit("\n[中止] 找不到 %s —— 它就是页面本体，不能删。\n" % OUT_PATH)

    cfg = {}
    if os.path.isfile(CFG_PATH):
        cfg = load_json(CFG_PATH, "config.json")
    else:
        say("  （没有 config.json，按默认标题生成）")

    apply_dirs(cfg)                      # config.json 里若指定了目录名，以它为准

    say()
    say("扫 %s\\ 和 %s\\ …" % (DIRS["lib"], DIRS["doc"]))
    tools, notes = scan(cfg)

    n_app = sum(1 for t in tools if t.get("kind") != "doc")
    n_doc = len(tools) - n_app

    say()
    if not tools:
        say("  还没有任何东西。")
        say("  %s：文件夹名「工具名+版本号+姓名」，里面放 zip + 总说明.md。" % DIRS["lib"])
        say("  %s：文件夹名「工具名+姓名」，里面放文件本体 + 总说明.md。" % DIRS["doc"])
    for t in tools:
        if t.get("kind") == "doc":
            # 文档代码库不显示版本号 —— 只在名字后面标文件数
            say("  %-22s %-12s %8s  %s  [%d 个文件]"
                % (t["name"][:22], t["contact"][:12],
                   human_size(t["size"]), t["updated"] or "-", len(t["files"])))
            continue
        extra = ("  +%d 历史" % len(t["older"])) if t.get("older") else ""
        say("  %-22s v%-6s %-12s %8s  %s%s"
            % (t["name"][:22], t["version"], t["contact"][:12],
               human_size(t["size"]), t["updated"] or "-", extra))

    n = write_page(cfg, tools)

    say()
    if n == 0:
        say("页面里的清单本来就是最新的，没动 %s。" % PAGE_NAME)
    else:
        say("已更新 %s（%.0f KB，%s %d 个 · %s %d 个）"
            % (PAGE_NAME, n / 1024.0, DIRS["lib"], n_app, DIRS["doc"], n_doc))

    if notes:
        say()
        say("-" * 58)
        for x in notes:
            say("  · " + x)

    say()
    say("-" * 58)
    say("好了，双击 启动工具库.bat 看效果。")
    say()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        say()
        say("[出错] %s: %s" % (type(e).__name__, e))
        say("把这段截图发我。")
        sys.exit(1)
