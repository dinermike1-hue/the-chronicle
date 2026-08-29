#!/usr/bin/env python3
"""
The Chronicle — 静态站点生成器
================================
读取 data/site.json 与 data/issues/*.json，生成完整静态站点到 site/：

  site/index.html            首页（Hero 头条 + 卡片网格 + 往期期刊带）
  site/sections/<id>.html    8 个栏目聚合页
  site/articles/<vol>-<slug>.html  单篇文章页（10 元素结构 + 8 种侧边栏模块）
  site/archive.html          历史归档（按期号索引）
  site/search.html           前端全文检索页
  site/search-index.json     检索索引（构建期生成）

用法：python build.py
"""

import base64
import html
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
ISSUES_DIR = DATA_DIR / "issues"
ASSETS_DIR = ROOT / "assets"
OUT_DIR = ROOT / "site"

FONTS = '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&display=swap" rel="stylesheet">'


def log(msg):
    print(f"[BUILD] {msg}", flush=True)


def esc(s):
    return html.escape(str(s or ""), quote=True)


def vol_slug(vol):
    """'Vol.028' -> 'vol-028'"""
    return vol.lower().replace(".", "-")


def fmt_date_cn(iso):
    """'2026-08-29' -> '2026年8月29日'"""
    y, m, d = iso.split("-")
    return f"{y}年{int(m)}月{int(d)}日"


def article_filename(issue, article):
    return f"{vol_slug(issue['vol'])}-{article['slug']}.html"


def article_url(issue, article, root=""):
    return f"{root}articles/{article_filename(issue, article)}"


def section_url(section_id, root=""):
    return f"{root}sections/{section_id}.html"


# ===== Markdown 正文转 HTML =====

def markdown_to_html(text):
    if not text:
        return ""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    paragraphs = re.split(r"\n\s*\n", text.strip())
    parts = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith("<") and p.endswith(">"):
            parts.append(p)
        else:
            p = p.replace("\n", "<br>\n")
            parts.append(f"<p>{p}</p>")
    return "\n".join(parts)


def plain_text(markdown_text):
    """去掉 Markdown 标记，供搜索索引使用"""
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", markdown_text or "")
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ===== SVG 兜底头图（无网络依赖） =====

SECTION_VISUAL_COLORS = {
    "world": ("#1a1a2e", "#16213e", "#0f3460", "#e94560"),
    "technology": ("#0f3460", "#533483", "#e94560", "#16c79a"),
    "defense": ("#2c3e50", "#8e44ad", "#c0392b", "#f39c12"),
    "economy": ("#c0392b", "#e74c3c", "#f39c12", "#27ae60"),
    "culture": ("#8e44ad", "#e74c3c", "#f39c12", "#f1c40f"),
    "nature": ("#27ae60", "#16a085", "#2980b9", "#8e44ad"),
    "science": ("#2c3e50", "#34495e", "#7f8c8d", "#3498db"),
    "music": ("#e67e22", "#f39c12", "#f1c40f", "#e74c3c"),
}


def section_visual_fallback(section_id):
    c1, c2, c3, accent = SECTION_VISUAL_COLORS.get(
        section_id, ("#1a1a2e", "#16213e", "#0f3460", "#e94560"))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 600">
<defs>
<linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="100%">
<stop offset="0%" style="stop-color:{c1}"/><stop offset="50%" style="stop-color:{c2}"/><stop offset="100%" style="stop-color:{c3}"/>
</linearGradient>
<linearGradient id="g2" x1="0%" y1="100%" x2="100%" y2="0%">
<stop offset="0%" style="stop-color:{accent};stop-opacity:0.2"/><stop offset="100%" style="stop-color:{accent};stop-opacity:0"/>
</linearGradient>
</defs>
<rect width="1200" height="600" fill="url(#g1)"/><rect width="1200" height="600" fill="url(#g2)"/>
<circle cx="100" cy="100" r="200" fill="{accent}" opacity="0.05"/>
<circle cx="1100" cy="500" r="300" fill="{accent}" opacity="0.03"/>
<path d="M0,500 Q300,400 600,450 T1200,400 L1200,600 L0,600Z" fill="{accent}" opacity="0.08"/>
</svg>'''
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def article_image(article):
    """返回 (src, credit)。优先真实配图 URL，缺省用 SVG 渐变兜底。"""
    url = (article.get("source_image") or "").strip()
    if url.startswith("http"):
        return url, (article.get("image_credit") or "").strip()
    return section_visual_fallback(article.get("section", "")), "图示：程序生成"


# ===== SVG 图表 =====

def render_svg_bar_chart(labels, values, bar_color="#8b1538", height=120):
    if not values:
        return ""
    max_v = max(values) or 1
    n = len(values)
    bar_w, gap = 30, 15
    total_w = n * (bar_w + gap) + gap
    svg_h = height + 40
    parts = []
    for i, (label, val) in enumerate(zip(labels, values)):
        h = (val / max_v) * height
        x = gap + i * (bar_w + gap)
        y = height - h + 20
        parts.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" fill="{bar_color}" rx="3"/>')
        parts.append(f'<text x="{x + bar_w / 2}" y="{y - 5}" text-anchor="middle" font-size="10">{esc(val)}</text>')
        parts.append(f'<text x="{x + bar_w / 2}" y="{svg_h - 5}" text-anchor="middle" font-size="9">{esc(label)}</text>')
    return f'<svg width="{total_w}" height="{svg_h}">' + "".join(parts) + "</svg>"


def render_svg_line_chart(points, labels, line_color="#8b1538", height=100):
    if len(points) < 2:
        return ""
    n = len(points)
    max_v, min_v = max(points), min(points)
    rng = max_v - min_v if max_v != min_v else 1
    w, padding = 260, 20
    coords = []
    for i, v in enumerate(points):
        x = padding + (i / (n - 1)) * (w - 2 * padding)
        y = padding + height - ((v - min_v) / rng) * height
        coords.append((x, y))
    path_d = "M" + " L".join(f"{x},{y}" for x, y in coords)
    circles = "".join(f'<circle cx="{x}" cy="{y}" r="3" fill="{line_color}"/>' for x, y in coords)
    label_txt = ""
    if labels:
        label_txt = (f'<text x="{padding}" y="{height + padding + 12}" font-size="9">{esc(labels[0])}</text>'
                     f'<text x="{w - padding}" y="{height + padding + 12}" text-anchor="end" font-size="9">{esc(labels[-1])}</text>')
    return (f'<svg width="{w}" height="{height + padding + 20}">'
            f'<path d="{path_d}" fill="none" stroke="{line_color}" stroke-width="2"/>{circles}{label_txt}</svg>')


# ===== Extras 增强模块渲染（8 种） =====

def render_extras(article):
    extras = article.get("extras", [])
    if not extras:
        return ""
    parts = []
    for module in extras:
        mtype = module.get("type", "")
        title = esc(module.get("title", ""))

        if mtype == "terms":
            parts.append(f'<div class="sidebar-section"><div class="sidebar-section-title">{title}</div>')
            for term in module.get("items", []):
                parts.append(
                    f'<div class="term-item"><div class="term-name">{esc(term.get("name"))}</div>'
                    f'<div class="term-def">{esc(term.get("definition"))}</div></div>')
            parts.append('</div>')

        elif mtype == "timeline":
            parts.append(f'<div class="sidebar-section"><div class="sidebar-section-title">{title}</div><div class="timeline">')
            for ev in module.get("events", []):
                parts.append(
                    f'<div class="timeline-item"><div class="timeline-date">{esc(ev.get("date"))}</div>'
                    f'<div class="timeline-event">{esc(ev.get("description"))}</div></div>')
            parts.append('</div></div>')

        elif mtype == "data_table":
            parts.append(f'<div class="sidebar-section"><div class="sidebar-section-title">{title}</div><table class="data-table">')
            if module.get("headers"):
                parts.append("<tr>" + "".join(f"<th>{esc(h)}</th>" for h in module["headers"]) + "</tr>")
            for row in module.get("rows", []):
                parts.append("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>")
            parts.append('</table></div>')

        elif mtype == "chart_bar":
            parts.append(f'<div class="sidebar-section"><div class="sidebar-section-title">{title}</div>')
            if module.get("labels") and module.get("values"):
                parts.append(render_svg_bar_chart(module["labels"], module["values"],
                                                  bar_color=module.get("color", "#8b1538")))
            parts.append('</div>')

        elif mtype == "chart_line":
            parts.append(f'<div class="sidebar-section"><div class="sidebar-section-title">{title}</div>')
            if module.get("points") and module.get("labels"):
                parts.append(render_svg_line_chart(module["points"], module["labels"],
                                                   line_color=module.get("color", "#8b1538")))
            parts.append('</div>')

        elif mtype == "entity_cards":
            parts.append(f'<div class="sidebar-section"><div class="sidebar-section-title">{title}</div>')
            for ent in module.get("entities", []):
                name = esc(ent.get("name", "?"))
                initial = (ent.get("name") or "?")[0]
                parts.append(
                    f'<div class="entity-card"><div class="entity-avatar">{esc(initial)}</div>'
                    f'<div class="entity-name">{name}</div>'
                    f'<div class="entity-role">{esc(ent.get("role"))}</div>'
                    f'<div class="entity-desc">{esc(ent.get("description"))}</div></div>')
            parts.append('</div>')

        elif mtype == "recommendations":
            parts.append(f'<div class="sidebar-section"><div class="sidebar-section-title">{title}</div>')
            for rec in module.get("items", []):
                parts.append(
                    f'<div class="rec-item"><div class="rec-title">{esc(rec.get("title"))}</div>'
                    f'<div class="rec-note">{esc(rec.get("note"))}</div></div>')
            parts.append('</div>')

        elif mtype == "audio":
            parts.append(f'<div class="sidebar-section"><div class="sidebar-section-title">{title}</div>')
            for au in module.get("tracks", []):
                src = (au.get("src") or "").strip()
                inner = (f'<audio controls><source src="{esc(src)}"></audio>' if src
                         else '<div class="audio-placeholder">音频将在通讯版中提供</div>')
                parts.append(
                    f'<div class="audio-track"><div class="audio-title">{esc(au.get("title"))}</div>{inner}</div>')
            parts.append('</div>')

    return "\n".join(parts)


# ===== 时间校验（迁移指南强制规则） =====

def time_check(article_text, current_year):
    errors = []
    for y in re.findall(r"\b(?:19|20)\d{2}\b", article_text):
        year = int(y)
        if year < current_year - 1:
            if not any(k in article_text for k in ("回顾", "历史", "此前", "当年", "百年")):
                errors.append(f"发现 {year} 年内容但未标注历史框架")
        elif year > current_year:
            errors.append(f"发现未来年份 {year}")
    return errors


# ===== 页面骨架 =====

def render_page(*, site, sections, title, description, body, root="", active=None,
                section_color=None, latest_vol="", extra_scripts=""):
    nav_links = "\n".join(
        f'<li><a href="{section_url(s["id"], root)}"{" class=\"active\"" if active == s["id"] else ""}>'
        f'{esc(s["name"])} <span class="en">{esc(s["en"])}</span></a></li>'
        for s in sections
    )
    style_attr = f' style="--section-color:{section_color}"' if section_color else ""
    footer_cols_1 = "\n".join(f'<a href="{section_url(s["id"], root)}">{esc(s["name"])}</a>' for s in sections[:4])
    footer_cols_2 = "\n".join(f'<a href="{section_url(s["id"], root)}">{esc(s["name"])}</a>' for s in sections[4:])
    try:
        vol_number = int(str(latest_vol).split(".")[-1])
    except (ValueError, IndexError):
        vol_number = latest_vol
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="stylesheet" href="{root}assets/css/style.css">
{FONTS}
</head>
<body data-root="{root}"{style_attr}>

<header class="top-bar">
  <div class="top-bar-inner">
    <a href="{root}index.html" class="logo">The Chronicle<span>每日全球视野</span></a>
    <div class="top-actions">
      <a href="{root}archive.html" class="hide-mobile">归档</a>
      <a href="{root}search.html" class="hide-mobile">搜索</a>
      <a href="#subscribe" class="subscribe-btn">订阅</a>
      <a href="{root}search.html" class="search-btn" aria-label="搜索">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
      </a>
    </div>
  </div>
</header>

<nav class="nav-bar">
  <div class="nav-bar-inner">
    <ul class="nav-list">
{nav_links}
    </ul>
  </div>
</nav>

<div class="subscribe-banner" id="subscribe">
  《The Chronicle》由念兹与 AI 共同编辑，每周刊发八篇深度报道。
  <a href="{root}archive.html">浏览过刊 &rarr;</a>
</div>

{body}

<footer class="footer">
  <div class="footer-inner">
    <div>
      <div class="footer-logo">The Chronicle</div>
      <p class="footer-desc">每日全球视野，独立思考的声音。<br>由念兹与 AI 共同编辑，已持续 {vol_number} 期。<br>飞书推送只是开始，网站才是归宿。</p>
    </div>
    <div class="footer-col"><h4>栏目</h4>{footer_cols_1}</div>
    <div class="footer-col"><h4>更多</h4>{footer_cols_2}</div>
    <div class="footer-col"><h4>关于</h4>
      <a href="{root}archive.html">历史归档</a>
      <a href="{root}search.html">站内搜索</a>
      <a href="{root}index.html">返回首页</a>
    </div>
  </div>
  <div class="footer-bottom">&copy; 2026 The Chronicle. All rights reserved. · {esc(latest_vol)} · 用心制作</div>
</footer>

<script src="{root}assets/js/main.js"></script>
{extra_scripts}
</body>
</html>'''


# ===== 卡片 =====

def render_card(issue, article, root=""):
    src, _credit = article_image(article)
    return f'''    <article class="article-card" onclick="location.href='{article_url(issue, article, root)}'">
      <div class="card-image">
        <img src="{src}" alt="{esc(article['section_title'])}" loading="lazy">
        <span class="section-tag">{esc(article['section_title'])}</span>
      </div>
      <div class="card-body">
        <h3 class="card-title">{esc(article['title'])}</h3>
        <p class="card-summary">{esc(article['subtitle'])}</p>
        <div class="card-meta"><span class="author">{esc(article['author'])}</span><span class="card-date">{esc(issue['vol'])}</span></div>
      </div>
    </article>'''


# ===== 首页 =====

def build_home(site, sections, issues, latest, warnings):
    hero_a = latest["articles"][0]
    src, _ = article_image(hero_a)
    hero = f'''  <article class="hero" onclick="location.href='{article_url(latest, hero_a)}'">
    <div class="hero-image">
      <img src="{src}" alt="{esc(hero_a['section_title'])}">
      <span class="hero-tag">头条</span>
    </div>
    <div class="hero-content">
      <div class="hero-kicker">{esc(hero_a['section_title'])} · 深度报道</div>
      <h2 class="hero-title">{esc(hero_a['title'])}</h2>
      <p class="hero-summary">{esc(hero_a['subtitle'])}</p>
      <div class="hero-meta"><span class="author">{esc(hero_a['author'])}</span> · {esc(hero_a['source'])} · {esc(hero_a['read_time'])}阅读 · {esc(latest['vol'])}</div>
    </div>
  </article>'''

    cards = "\n".join(render_card(latest, a) for a in latest["articles"][1:])

    band_rows = []
    for issue in reversed(issues[:-1]):
        lead = issue["articles"][0]
        band_rows.append(f'''      <a class="issue-row" href="archive.html#{vol_slug(issue['vol'])}">
        <div class="issue-vol">{esc(issue['vol'])}<small>{fmt_date_cn(issue['date'])}</small></div>
        <div class="issue-line">头条：{esc(lead['title'])} —— {esc(lead['subtitle'])}</div>
        <div class="issue-count">{len(issue['articles'])} 篇</div>
      </a>''')
    band = f'''
  <div class="issue-band">
    <div class="issue-band-head"><h2>往期期刊</h2><a href="archive.html">全部归档 &rarr;</a></div>
    <div class="issue-rows">
{chr(10).join(band_rows)}
    </div>
  </div>'''

    body = f'''<main class="main">
  <h1 class="section-title">今日精选</h1>
  <p class="section-sub">{esc(latest['vol'])} · {fmt_date_cn(latest['date'])} · {len(latest['articles'])} 篇深度报道</p>
{hero}
  <hr class="divider">
  <div class="article-grid">
{cards}
  </div>
{band}
</main>'''
    return render_page(site=site, sections=sections,
                       title="The Chronicle · 每日全球视野",
                       description=site["site"]["description"],
                       body=body, latest_vol=latest["vol"])


# ===== 栏目聚合页 =====

def build_section_page(site, sections, issues, section, latest):
    sid = section["id"]
    entries = []  # (issue, article) 新→旧
    for issue in reversed(issues):
        for a in issue["articles"]:
            if a.get("section") == sid:
                entries.append((issue, a))
    if not entries:
        return None

    f_issue, f_a = entries[0]
    src, _ = article_image(f_a)
    rest = "\n".join(render_card(iss, a, root="../") for iss, a in entries[1:])
    author_bio = site.get("authors", {}).get(section["author"], "")

    body = f'''<div class="section-band"></div>
<div class="section-head">
  <div class="section-head-band"></div>
  <h1>{esc(section['name'])}</h1>
  <div class="en-name">{esc(section['en'])}</div>
  <p class="desc">{esc(section['description'])}</p>
  <div class="editor">栏目主编：<b>{esc(section['author'])}</b> · {esc(author_bio)}</div>
</div>
<main class="main">
  <article class="section-feature" onclick="location.href='{article_url(f_issue, f_a, '../')}'">
    <div class="card-image"><img src="{src}" alt="{esc(f_a['title'])}"></div>
    <div class="feature-body">
      <div class="feature-vol">{esc(f_issue['vol'])} · 最新报道</div>
      <h2 class="feature-title">{esc(f_a['title'])}</h2>
      <p class="feature-summary">{esc(f_a['subtitle'])}</p>
      <div class="feature-meta"><span class="author">{esc(f_a['author'])}</span> · {fmt_date_cn(f_issue['date'])} · {esc(f_a['read_time'])}阅读</div>
    </div>
  </article>
  <div class="section-list-label">本栏目全部报道 · {len(entries)} 篇</div>
  <div class="article-grid">
{rest}
  </div>
</main>'''
    return render_page(site=site, sections=sections,
                       title=f"{section['name']} · The Chronicle",
                       description=section["description"],
                       body=body, root="../", active=sid,
                       section_color=section["color"], latest_vol=latest["vol"])


# ===== 单篇文章页 =====

def build_article_page(site, sections, issues, issue, article, prev_entry, next_entry, latest):
    section = next(s for s in sections if s["id"] == article.get("section"))
    src, credit = article_image(article)
    body_html = markdown_to_html(article.get("content", ""))

    # 侧边栏：本期目录 + extras
    toc_items = []
    for a in issue["articles"]:
        cur = " current" if a["slug"] == article["slug"] else ""
        toc_items.append(
            f'<a class="toc-item{cur}" href="{article_url(issue, a, "../")}">'
            f'<span class="toc-sec">{esc(a["section_title"])}</span>{esc(a["title"])}</a>')
    toc = ('<div class="sidebar-section"><div class="sidebar-section-title">本期目录 · '
           f'{esc(issue["vol"])}</div>' + "\n".join(toc_items) + "</div>")
    extras_html = render_extras(article)

    # 相关阅读：先同栏目他期，再最新期其他文章
    related = []
    for iss in reversed(issues):
        for a in iss["articles"]:
            if a["slug"] == article["slug"] and iss["vol"] == issue["vol"]:
                continue
            if a.get("section") == article.get("section"):
                related.append((iss, a))
    for a in latest["articles"]:
        if len(related) >= 3:
            break
        if a["slug"] != article["slug"] and all(a["slug"] != r[1]["slug"] for r in related):
            related.append((latest, a))
    related = related[:3]
    related_html = "\n".join(render_card(iss, a, root="../") for iss, a in related)

    def pn_cell(entry, label, cls):
        if not entry:
            return f'<div class="{cls} spacer"></div>'
        iss, a = entry
        return (f'<a class="{cls}" href="{article_url(iss, a, '../')}">'
                f'<div class="pn-label">{label} · {esc(iss["vol"])}</div>'
                f'<div class="pn-title">{esc(a["title"])}</div></a>')

    body = f'''<div class="section-band"></div>
<header class="article-head">
  <div class="article-kicker">{esc(article.get('kicker') or article['section_title'])}</div>
  <h1 class="article-title">{esc(article['title'])}</h1>
  <p class="article-subtitle">{esc(article['subtitle'])}</p>
  <div class="article-meta">
    <span class="author">{esc(article['author'])}</span><span class="sep">·</span>{esc(article['source'])}<span class="sep">·</span>{esc(article['read_time'])}阅读<span class="sep">·</span>{fmt_date_cn(issue['date'])}<span class="sep">·</span>{esc(issue['vol'])}
  </div>
</header>
<figure class="article-hero">
  <img src="{src}" alt="{esc(article.get('caption') or article['title'])}">
  <figcaption><span>{esc(article.get('caption'))}</span><span>{esc(credit)}</span></figcaption>
</figure>
<div class="article-layout">
  <article class="article-body">
{body_html}
    <div class="article-end-mark">◆ ◆ ◆</div>
  </article>
  <aside class="article-sidebar">
{toc}
{extras_html}
  </aside>
</div>
<section class="related">
  <h2 class="related-title">相关阅读</h2>
  <div class="related-grid">
{related_html}
  </div>
</section>
<nav class="prevnext">
  {pn_cell(prev_entry, "上一篇", "prev")}
  {pn_cell(next_entry, "下一篇", "next")}
</nav>'''
    return render_page(site=site, sections=sections,
                       title=f"{article['title']} · The Chronicle",
                       description=article["subtitle"],
                       body=body, root="../", active=article.get("section"),
                       section_color=section["color"], latest_vol=latest["vol"])


# ===== 历史归档页 =====

def build_archive(site, sections, issues, latest):
    total_articles = sum(len(i["articles"]) for i in issues)
    sec_color = {s["id"]: s["color"] for s in sections}
    blocks = []
    for issue in reversed(issues):
        items = []
        for a in issue["articles"]:
            items.append(f'''        <a class="archive-item" href="{article_url(issue, a)}" style="--item-color:{sec_color.get(a.get('section'), '#1a1a2e')}">
          <span class="a-sec">{esc(a['section_title'])}</span>
          <span class="a-title">{esc(a['title'])}</span>
          <span class="a-meta">{esc(a['author'])} · {esc(a['read_time'])}阅读</span>
        </a>''')
        blocks.append(f'''  <div class="archive-issue" id="{vol_slug(issue['vol'])}">
    <div class="archive-issue-head">
      <div><span class="vol">{esc(issue['vol'])}</span><span class="date">{fmt_date_cn(issue['date'])}</span></div>
      <div class="count">{len(issue['articles'])} 篇文章</div>
    </div>
    <div class="archive-list">
{chr(10).join(items)}
    </div>
  </div>''')

    body = f'''<main class="main">
  <h1 class="section-title">历史归档</h1>
  <p class="section-sub">自创刊以来的全部期刊，按期号倒序</p>
  <div class="archive-stats">
    <div><span class="num">{len(issues)}</span><span class="lbl">期</span></div>
    <div><span class="num">{total_articles}</span><span class="lbl">篇报道</span></div>
    <div><span class="num">{len(sections)}</span><span class="lbl">个栏目</span></div>
  </div>
{chr(10).join(blocks)}
</main>'''
    return render_page(site=site, sections=sections,
                       title="历史归档 · The Chronicle",
                       description="The Chronicle 全部过刊，按期号倒序索引。",
                       body=body, latest_vol=latest["vol"])


# ===== 搜索页 + 索引 =====

def build_search_page(site, sections, latest):
    body = '''<main class="main">
  <h1 class="section-title">站内检索</h1>
  <p class="section-sub">检索全部期刊的标题、作者、栏目与正文</p>
  <div class="search-wrap">
    <form class="search-box" id="search-form">
      <input type="search" id="search-input" placeholder="搜索文章、栏目或作者……" autocomplete="off" autofocus>
      <button type="submit">搜索</button>
    </form>
    <div class="search-hint">支持多关键词（空格分隔） · 在任意页面按 <kbd>/</kbd> 唤起搜索</div>
    <div class="search-status" id="search-status">正在加载检索索引……</div>
    <div id="search-results"></div>
    <noscript><div class="search-empty">检索功能需要启用 JavaScript；您也可以到 <a href="archive.html">历史归档</a> 浏览全部文章。</div></noscript>
  </div>
</main>'''
    return render_page(site=site, sections=sections,
                       title="站内检索 · The Chronicle",
                       description="检索 The Chronicle 全部期刊文章。",
                       body=body, latest_vol=latest["vol"],
                       extra_scripts='<script src="assets/js/search.js"></script>')


def build_search_index(sections, issues):
    sec_color = {s["id"]: s["color"] for s in sections}
    out = []
    for issue in issues:
        for a in issue["articles"]:
            out.append({
                "title": a["title"],
                "subtitle": a.get("subtitle", ""),
                "kicker": a.get("kicker", ""),
                "author": a.get("author", ""),
                "section": a.get("section", ""),
                "section_title": a.get("section_title", ""),
                "section_en": a.get("section_en", ""),
                "section_color": sec_color.get(a.get("section"), "#1a1a2e"),
                "vol": issue["vol"],
                "date": issue["date"],
                "url": article_url(issue, a),
                "content": plain_text(a.get("content", "")),
            })
    return {"generated": datetime.now().isoformat(timespec="seconds"), "articles": out}


# ===== 主流程 =====

def main():
    site = json.loads((DATA_DIR / "site.json").read_text(encoding="utf-8"))
    sections = site["sections"]

    issues = []
    for path in sorted(ISSUES_DIR.glob("*.json")):
        issue = json.loads(path.read_text(encoding="utf-8"))
        issues.append(issue)
    issues.sort(key=lambda i: i["date"])
    if not issues:
        log("错误：data/issues/ 下没有任何期刊数据")
        sys.exit(1)
    latest = issues[-1]
    log(f"载入 {len(issues)} 期、共 {sum(len(i['articles']) for i in issues)} 篇文章；最新期 {latest['vol']} ({latest['date']})")

    # 时间校验
    year = datetime.now().year
    warn_count = 0
    for issue in issues:
        for a in issue["articles"]:
            for err in time_check(a.get("content", ""), year):
                log(f"⚠️  [{issue['vol']}/{a.get('slug')}] {err}")
                warn_count += 1
    if warn_count == 0:
        log("✓ 时间校验全部通过")

    # 清理并重建输出目录
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    (OUT_DIR / "articles").mkdir(parents=True)
    (OUT_DIR / "sections").mkdir(parents=True)
    shutil.copytree(ASSETS_DIR, OUT_DIR / "assets")

    written = []

    # 首页
    (OUT_DIR / "index.html").write_text(build_home(site, sections, issues, latest, warn_count), encoding="utf-8")
    written.append("index.html")

    # 栏目页
    for s in sections:
        html_text = build_section_page(site, sections, issues, s, latest)
        if html_text:
            (OUT_DIR / "sections" / f"{s['id']}.html").write_text(html_text, encoding="utf-8")
            written.append(f"sections/{s['id']}.html")

    # 文章页（跨期顺序用于上一篇/下一篇）
    flat = [(iss, a) for iss in issues for a in iss["articles"]]
    for idx, (iss, a) in enumerate(flat):
        prev_entry = flat[idx - 1] if idx > 0 else None
        next_entry = flat[idx + 1] if idx < len(flat) - 1 else None
        html_text = build_article_page(site, sections, issues, iss, a, prev_entry, next_entry, latest)
        (OUT_DIR / "articles" / article_filename(iss, a)).write_text(html_text, encoding="utf-8")
    written.append(f"articles/ × {len(flat)}")

    # 归档 + 搜索
    (OUT_DIR / "archive.html").write_text(build_archive(site, sections, issues, latest), encoding="utf-8")
    (OUT_DIR / "search.html").write_text(build_search_page(site, sections, latest), encoding="utf-8")
    (OUT_DIR / "search-index.json").write_text(
        json.dumps(build_search_index(sections, issues), ensure_ascii=False), encoding="utf-8")
    written += ["archive.html", "search.html", "search-index.json"]

    log(f"✓ 构建完成，输出 {len(flat) + len(sections) + 3} 个页面到 {OUT_DIR}")
    for w in written:
        log(f"  - {w}")


if __name__ == "__main__":
    main()
