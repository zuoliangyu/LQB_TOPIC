"""生成 GitHub Pages 用的 docsify 站点。

用法：python scripts/build_site.py [输出目录，默认 dist]

扫描 `蓝桥杯电子类真题/<届>/<赛道>/<省赛|国赛>/...`，生成：
  README.md          首页：说明 + 届 × 赛道 总览表
  years/<届号>.md     按届浏览
  tracks/<赛道>.md    按赛道浏览
  _sidebar.md / index.html / .nojekyll
并把真题目录原样复制到输出目录，文件链接指向 Pages 直链（可在页内 iframe 预览）。
"""

import os
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
DATA = "蓝桥杯电子类真题"
BASE_URL = "https://zuoliangyu.github.io/LQB_TOPIC"
REPO_URL = "https://github.com/zuoliangyu/LQB_TOPIC"

# 赛道展示顺序与页面文件名；未列出的赛道排在后面，文件名用 URL 编码的原名。
TRACKS = {"单片机": "mcu", "嵌入式": "embedded", "物联网": "iot", "EDA": "eda", "FPGA": "fpga"}
STAGES = ["省赛", "国赛"]


def year_no(name: str) -> int:
    m = re.match(r"\d+", name)
    return int(m.group()) if m else 0


def year_label(name: str) -> str:
    # "16 第十六届" -> "第十六届"
    return name.split(" ", 1)[1] if " " in name else name


def track_slug(track: str) -> str:
    return TRACKS.get(track, quote(track))


def ordered(names, preferred):
    return sorted(names, key=lambda n: (preferred.index(n) if n in preferred else len(preferred), n))


def subdirs(p: Path):
    return [d.name for d in p.iterdir() if d.is_dir()]


def file_link(f: Path) -> str:
    rel = f.relative_to(ROOT).as_posix()
    return f"{BASE_URL}/{quote(rel)}"


def file_lines(stage_dir: Path):
    """阶段目录下的文件列表（含子目录，子目录名作为前缀）。"""
    files = sorted(
        (f for f in stage_dir.rglob("*") if f.is_file()),
        key=lambda f: f.relative_to(stage_dir).as_posix(),
    )
    lines = []
    for f in files:
        label = f.relative_to(stage_dir).as_posix()
        lines.append(f"- [{label}]({file_link(f)})")
    return lines


def scan():
    """返回 {届目录名: {赛道: [阶段, ...]}}，届按届号倒序。"""
    data_dir = ROOT / DATA
    years = sorted(subdirs(data_dir), key=year_no, reverse=True)
    result = {}
    for y in years:
        tracks = ordered(subdirs(data_dir / y), list(TRACKS))
        result[y] = {t: ordered(subdirs(data_dir / y / t), STAGES) for t in tracks}
    return result


def count_files(p: Path) -> int:
    return sum(1 for f in p.rglob("*") if f.is_file())


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build(out: Path):
    data_dir = ROOT / DATA
    tree = scan()
    all_tracks = ordered({t for ts in tree.values() for t in ts}, list(TRACKS))

    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(data_dir, out / DATA)

    # 按届
    for y, tracks in tree.items():
        lines = [f"# {year_label(y)}蓝桥杯电子类真题", ""]
        for t, stages in tracks.items():
            lines += [f"## {t}", ""]
            for s in stages:
                lines += [f"### {s}", "", *file_lines(data_dir / y / t / s), ""]
        write(out / "years" / f"{year_no(y)}.md", "\n".join(lines))

    # 按赛道
    for t in all_tracks:
        lines = [f"# {t} 历年真题", ""]
        for y, tracks in tree.items():
            if t not in tracks:
                continue
            lines += [f"## {year_label(y)}", ""]
            for s in tracks[t]:
                lines += [f"### {s}", "", *file_lines(data_dir / y / t / s), ""]
        write(out / "tracks" / f"{track_slug(t)}.md", "\n".join(lines))

    # 首页总览表：届 × 赛道，单元格为文件数
    pdf_total = sum(1 for f in data_dir.rglob("*") if f.is_file() and f.suffix.lower() == ".pdf")
    head = "| 届 | " + " | ".join(f"[{t}](tracks/{track_slug(t)}.md)" for t in all_tracks) + " |"
    sep = "|---|" + "---|" * len(all_tracks)
    rows = []
    for y, tracks in tree.items():
        cells = []
        for t in all_tracks:
            if t in tracks:
                stages = "、".join(tracks[t])
                cells.append(f"{stages}（{count_files(data_dir / y / t)}）")
            else:
                cells.append("—")
        rows.append(f"| [{year_label(y)}](years/{year_no(y)}.md) | " + " | ".join(cells) + " |")

    newest, oldest = year_label(next(iter(tree))), year_label(list(tree)[-1])
    home = f"""# 蓝桥杯电子类历年真题

收录{oldest}至{newest}蓝桥杯大赛电子类真题，涵盖{"、".join(all_tracks)}赛道，共 {pdf_total} 份 PDF。

- 从左侧栏**按届**或**按赛道**进入，点击文件名在新标签页打开，点「预览」可直接在页面内查看 PDF。
- EDA 赛道的工程文件（`.zip` / `.eprj` / `.epro` / `.json`）需下载后用对应软件打开。

## 总览

单元格为该届该赛道包含的比赛阶段及文件数，点击表头或届名进入对应页面。

{head}
{sep}
{chr(10).join(rows)}
"""
    write(out / "README.md", home)

    # 侧边栏
    side = ["* [🏠 首页](/)", "", "* 📅 按届浏览"]
    side += [f"  * [{year_label(y)}](years/{year_no(y)}.md)" for y in tree]
    side += ["", "* 🧭 按赛道浏览"]
    side += [f"  * [{t}](tracks/{track_slug(t)}.md)" for t in all_tracks]
    side += ["", "* 🔗 项目链接", f"  * [GitHub 仓库]({REPO_URL})", "  * [左岚的站点导航](https://zuoliangyu.github.io/)", ""]
    write(out / "_sidebar.md", "\n".join(side))

    updated = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    index = (ROOT / "scripts" / "index.template.html").read_text(encoding="utf-8")
    write(out / "index.html", index.replace("{{UPDATED}}", updated))
    write(out / ".nojekyll", "")

    print(f"站点已生成到 {out}：{len(tree)} 届，{len(all_tracks)} 个赛道，{pdf_total} 份 PDF")


if __name__ == "__main__":
    build(ROOT / (sys.argv[1] if len(sys.argv) > 1 else "dist"))
