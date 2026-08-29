# The Chronicle — 迁移包

> 从"每日新闻总结"升级为"个人数字报刊网站"的完整项目资料。

---

## 项目定位

**The Chronicle** 是一个参考《纽约客》(The New Yorker) 网站风格的个人数字报刊平台。

- **首页**：横向栏目导航 + Hero头条 + 文章卡片网格
- **栏目页**：8个固定栏目（国际政治、科技动态、军事观察、经济金融、文化艺术、自然地理、科学前沿、音乐专题）
- **文章页**：单篇深度报道，带侧边栏增强模块
- **飞书推送**：每日一期自动生成，作为网站的"通讯订阅"功能

---

## 一、编辑风格手册（STYLE_GUIDE）

### 刊物定位
- **语调**：严肃、深度、编辑级，拒绝轻浮和网络用语
- **视角**：全球视野，中国关切，独立思考
- **长度**：每篇1200-1500字，共8篇/期
- **期号格式**：Vol.XXX · Month Day, Year

### 8个固定栏目

| 序号 | 栏目 | 英文名 | 核心关注点 |
|------|------|--------|-----------|
| 1 | 国际政治 | World | 地缘政治、大国关系、区域冲突 |
| 2 | 科技动态 | Technology | AI、半导体、航天、生物科技 |
| 3 | 军事观察 | Defense | 军力部署、战略博弈、武器装备 |
| 4 | 经济金融 | Economy | 宏观经济、货币政策、市场动态 |
| 5 | 文化艺术 | Culture | 艺术展览、文化现象、美学讨论 |
| 6 | 自然地理 | Nature | 气候、环境、地理奇观、生态危机 |
| 7 | 科学前沿 | Science | 物理、天文、生物、重大科学发现 |
| 8 | 音乐专题 | Music | 爵士、古典、音乐史、跨界融合 |

### 文章结构（10个元素）
1. 栏目色带标题栏
2. 头图（真实配图，必须标注来源）
3. 分类标签（kicker）
4. 主标题（20字以内）
5. 副标题（一句话概括核心论点）
6. 元信息：作者名、来源、阅读时间
7. 正文（8段左右，1200-1500字）
8. 侧边栏：本期目录导航 + 增强模块
9. 相关阅读：3篇关联文章推荐
10. 底部导航：上一篇/下一篇

### 配色方案
- 主色：`#1a1a2e`（深蓝黑）
- 强调色：`#c41e3a`（深红）
- 背景：`#faf8f5`（暖白）
- 正文：`#1a1a1a`

### 作者池
- 国际政治：张明远
- 科技动态：李晓峰
- 军事观察：陈建军
- 经济金融：王财经
- 文化艺术：林雅文
- 自然地理：陈思雨
- 科学前沿：林雅文
- 音乐专题：王乐然

### 时间校验（强制规则）
- **搜索阶段**：优先48小时内，可放宽至7天，禁止超30天
- **生成阶段**：每篇文章开头必须标注真实日期
- **自检函数**：提取所有4位年份，旧新闻需标注"历史回顾"或"此前"

---

## 二、构建器规范（BUILDER_SPEC）

### 核心逻辑
- **主脚本**：`chronicle_builder_final.py`
- **输入**：`articles_input.json`（8篇文章数据）
- **输出**：
  - `index.html` — 在线版杂志（依赖外部图片URL）
  - `articles_latest.json` — 数据归档
  - `chronicle-volXXX.tar.gz` — 打包分发
- **离线版**：`build_offline.py` → `index_offline.html`（单文件，base64嵌入所有图片）

### 图片策略（3级优先级）
1. `source_image` — 新闻来源配图（最优先）
2. `search_image` — AI搜索到的相关配图（次要）
3. SVG渐变fallback（兜底，无网络依赖）

### Extras增强模块（8种）

| 模块 | 类型 | 用途 |
|------|------|------|
| terms | 术语解释 | 关键概念说明 |
| timeline | 时间线 | 事件发展脉络 |
| data_table | 数据表格 | 结构化数据展示 |
| chart_bar | SVG柱状图 | 数据对比 |
| chart_line | SVG折线图 | 趋势变化 |
| entity_cards | 实体卡片 | 人物/组织简介（带头像色块+首字母） |
| recommendations | 推荐资源 | 延伸阅读 |
| audio | 音频播放器 | 音乐专题（支持base64嵌入） |

### 每期推荐Extras配置

| 栏目 | 推荐模块组合 |
|------|-------------|
| 国际政治 | timeline + entity_cards |
| 科技动态 | chart_bar + terms |
| 军事观察 | entity_cards + terms |
| 经济金融 | terms + chart_line |
| 文化艺术 | recommendations + entity_cards |
| 自然地理 | data_table + terms |
| 科学前沿 | terms + timeline |
| 音乐专题 | audio + entity_cards / recommendations |

---

## 三、构建器核心代码

### 主入口逻辑

```python
#!/usr/bin/env python3
"""
The Daily Chronicle - 构建器
负责：时间校验、图片下载(base64)、HTML组装、打包
调用方（AI Agent）负责：新闻搜索、文章撰写
"""

import os, re, sys, json, shutil, base64, subprocess, tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import urllib.request

BASE_DIR = Path("/workspace/chronicle")  # 改为你自己的路径
IMG_DIR = BASE_DIR / "images"
OUTPUT_DIR = Path("/tmp/chronicle_daily")
ARCHIVE_DIR = Path("/workspace/chronicle_archives")

def log(msg):
    print(f"[CHRONICLE] {msg}", flush=True)

def ensure_dirs():
    for d in [IMG_DIR, OUTPUT_DIR, ARCHIVE_DIR]:
        d.mkdir(exist_ok=True)

# ===== 图片处理（核心）=====

def download_image_to_base64(url, timeout=20):
    """下载图片转为base64 data URI，失败返回None"""
    if not url or not url.startswith('http'):
        return None, None
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            if len(data) < 3000:  # 图片至少3KB
                return None, None
            mime = resp.headers.get('Content-Type', 'image/jpeg')
            # 标准化MIME类型
            if 'svg' in mime: mime = 'image/svg+xml'
            elif 'png' in mime: mime = 'image/png'
            elif 'gif' in mime: mime = 'image/gif'
            elif 'webp' in mime: mime = 'image/webp'
            else: mime = 'image/jpeg'
            b64 = base64.b64encode(data).decode('ascii')
            return f"data:{mime};base64,{b64}", mime
    except Exception:
        return None, None

def resolve_article_image(item, section_id, title):
    """
    3级优先级解析配图：
    1. source_image（新闻来源配图，最优先）
    2. search_image（AI搜索配图，次要）
    3. SVG渐变fallback（兜底，无网络依赖）
    """
    for field, credit_field in [
        ('source_image', 'image_credit'),
        ('search_image', 'search_credit')
    ]:
        url = item.get(field, '')
        if url and url.startswith('http'):
            uri, mime = download_image_to_base64(url)
            if uri:
                credit = item.get(credit_field, '')
                if not credit:
                    domain = urlparse(url).netloc.replace('www.', '')
                    credit = f"图片来源：{domain}"
                return uri, credit, False  # (data_uri, credit, is_svg)
    
    # SVG fallback（无网络依赖）
    svg_uri = get_section_visual(section_id, title)
    return svg_uri, "图示：程序生成", True

def markdown_to_html(text):
    """Markdown转HTML：粗体、斜体、分段"""
    if not text:
        return ""
    # 粗体 **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # 斜体 *text*（排除**的情况）
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    # 按空行分段
    paragraphs = re.split(r'\n\s*\n', text.strip())
    html_parts = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # 如果已经是HTML标签，不包裹
        if p.startswith('<') and p.endswith('>'):
            html_parts.append(p)
        else:
            # 单换行转 <br>
            p = p.replace('\n', '<br>\n')
            html_parts.append(f'<p>{p}</p>')
    return '\n'.join(html_parts)

# ===== SVG图表渲染 =====

def render_svg_bar_chart(labels, values, max_val=None, height=120, bar_color='#8b1538'):
    """渲染SVG柱状图"""
    if not values:
        return ""
    max_v = max_val or max(values)
    n = len(values)
    bar_w, gap = 30, 15
    total_w = n * (bar_w + gap) + gap
    svg_h = height + 40
    
    bars = []
    for i, (label, val) in enumerate(zip(labels, values)):
        h = (val / max_v) * height if max_v > 0 else 0
        x = gap + i * (bar_w + gap)
        y = height - h + 20
        bars.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" fill="{bar_color}" rx="3"/>')
        bars.append(f'<text x="{x + bar_w/2}" y="{y - 5}" text-anchor="middle" font-size="10">{val}</text>')
        bars.append(f'<text x="{x + bar_w/2}" y="{svg_h - 5}" text-anchor="middle" font-size="9">{label}</text>')
    
    return f'<svg width="{total_w}" height="{svg_h}">'+ ''.join(bars)+'</svg>'

def render_svg_line_chart(data_points, labels, height=100, line_color='#8b1538'):
    """渲染SVG折线图"""
    if len(data_points) < 2:
        return ""
    n = len(data_points)
    max_v, min_v = max(data_points), min(data_points)
    range_v = max_v - min_v if max_v != min_v else 1
    w, padding = 240, 20
    
    points = []
    for i, v in enumerate(data_points):
        x = padding + (i / (n - 1)) * (w - 2 * padding)
        y = padding + height - ((v - min_v) / range_v) * height
        points.append(f"{x},{y}")
    
    path_d = "M" + " L".join(points)
    circles = ""
    for x_y, v in zip(points, data_points):
        x, y = x_y.split(",")
        circles += f'<circle cx="{x}" cy="{y}" r="3" fill="{line_color}"/>'
    
    return f'<svg width="{w}" height="{height + padding + 25}"><path d="{path_d}" fill="none" stroke="{line_color}" stroke-width="2"/>{circles}</svg>'

# ===== Extras增强模块渲染 =====

def render_extras(item):
    """渲染文章增强模块（extras）为HTML侧边栏内容"""
    extras = item.get('extras', [])
    if not extras:
        return ""
    
    html_parts = []
    for module in extras:
        mtype = module.get('type', '')
        title = module.get('title', '')
        
        if mtype == 'terms':  # 术语解释
            html_parts.append(f'<div class="sidebar-section"><div class="sidebar-section-title">{title}</div>')
            for term in module.get('items', []):
                html_parts.append(
                    f'<div class="term-item">'
                    f'<div class="term-name">{term["name"]}</div>'
                    f'<div class="term-def">{term["definition"]}</div>'
                    f'</div>'
                )
            html_parts.append('</div>')
            
        elif mtype == 'timeline':  # 时间线
            html_parts.append(f'<div class="sidebar-section"><div class="sidebar-section-title">{title}</div><div class="timeline">')
            for event in module.get('events', []):
                html_parts.append(
                    f'<div class="timeline-item">'
                    f'<div class="timeline-date">{event["date"]}</div>'
                    f'<div class="timeline-event">{event["description"]}</div>'
                    f'</div>'
                )
            html_parts.append('</div></div>')
            
        elif mtype == 'data_table':  # 数据表格
            html_parts.append(f'<div class="sidebar-section"><div class="sidebar-section-title">{title}</div><table class="data-table">')
            if module.get('headers'):
                html_parts.append('<tr>' + ''.join(f'<th>{h}</th>' for h in module['headers']) + '</tr>')
            for row in module.get('rows', []):
                html_parts.append('<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>')
            html_parts.append('</table></div>')
            
        elif mtype == 'chart_bar':  # SVG柱状图
            html_parts.append(f'<div class="sidebar-section"><div class="sidebar-section-title">{title}</div>')
            if module.get('labels') and module.get('values'):
                html_parts.append(render_svg_bar_chart(module['labels'], module['values'], bar_color=module.get('color', '#8b1538')))
            html_parts.append('</div>')
            
        elif mtype == 'chart_line':  # SVG折线图
            html_parts.append(f'<div class="sidebar-section"><div class="sidebar-section-title">{title}</div>')
            if module.get('points') and module.get('labels'):
                html_parts.append(render_svg_line_chart(module['points'], module['labels'], line_color=module.get('color', '#8b1538')))
            html_parts.append('</div>')
            
        elif mtype == 'entity_cards':  # 实体卡片（带头像色块+首字母）
            html_parts.append(f'<div class="sidebar-section"><div class="sidebar-section-title">{title}</div>')
            for ent in module.get('entities', []):
                initial = ent.get('name', '?')[0]
                html_parts.append(
                    f'<div class="entity-card">'
                    f'<div class="entity-avatar">{initial}</div>'
                    f'<div class="entity-name">{ent["name"]}</div>'
                    f'<div class="entity-role">{ent.get("role", "")}</div>'
                    f'<div class="entity-desc">{ent.get("description", "")}</div>'
                    f'</div>'
                )
            html_parts.append('</div>')
            
        elif mtype == 'recommendations':  # 延伸阅读
            html_parts.append(f'<div class="sidebar-section"><div class="sidebar-section-title">{title}</div>')
            for rec in module.get('items', []):
                html_parts.append(
                    f'<div class="rec-item">'
                    f'<div class="rec-title">{rec["title"]}</div>'
                    f'<div class="rec-note">{rec.get("note", "")}</div>'
                    f'</div>'
                )
            html_parts.append('</div>')
            
        elif mtype == 'audio':  # 音频播放器
            html_parts.append(f'<div class="sidebar-section"><div class="sidebar-section-title">{title}</div>')
            for au in module.get('tracks', []):
                src = au.get('src', '')
                if src:
                    html_parts.append(
                        f'<div class="audio-track">'
                        f'<div class="audio-title">{au["title"]}</div>'
                        f'<audio controls style="width:100%"><source src="{src}"></audio>'
                        f'</div>'
                    )
                else:
                    html_parts.append(
                        f'<div class="audio-track">'
                        f'<div class="audio-title">{au["title"]}</div>'
                        f'<div class="audio-placeholder">音频加载中...</div>'
                        f'</div>'
                    )
            html_parts.append('</div>')
    
    return '\n'.join(html_parts)

# ===== SVG Fallback（无网络依赖）=====

def get_section_visual(section_id, title=""):
    """
    生成栏目视觉背景 - 使用内嵌SVG，不依赖外部网络
    作为图片下载失败时的 fallback
    返回可嵌入CSS的data URI
    """
    colors = {
        "world": ("#1a1a2e", "#16213e", "#0f3460", "#e94560"),
        "tech": ("#0f3460", "#533483", "#e94560", "#16c79a"),
        "defense": ("#2c3e50", "#8e44ad", "#c0392b", "#f39c12"),
        "economy": ("#c0392b", "#e74c3c", "#f39c12", "#27ae60"),
        "culture": ("#8e44ad", "#e74c3c", "#f39c12", "#f1c40f"),
        "nature": ("#27ae60", "#16a085", "#2980b9", "#8e44ad"),
        "science": ("#2c3e50", "#34495e", "#7f8c8d", "#3498db"),
        "music": ("#e67e22", "#f39c12", "#f1c40f", "#e74c3c"),
    }
    c1, c2, c3, accent = colors.get(section_id, ("#1a1a2e", "#16213e", "#0f3460", "#e94560"))
    
    # 封面/头图用的大尺寸SVG
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 600">
        <defs>
            <linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:{c1}"/>
                <stop offset="50%" style="stop-color:{c2}"/>
                <stop offset="100%" style="stop-color:{c3}"/>
            </linearGradient>
            <linearGradient id="g2" x1="0%" y1="100%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color:{accent};stop-opacity:0.2"/>
                <stop offset="100%" style="stop-color:{accent};stop-opacity:0"/>
            </linearGradient>
        </defs>
        <rect width="1200" height="600" fill="url(#g1)"/>
        <rect width="1200" height="600" fill="url(#g2)"/>
        <circle cx="100" cy="100" r="200" fill="{accent}" opacity="0.05"/>
        <circle cx="1100" cy="500" r="300" fill="{accent}" opacity="0.03"/>
        <path d="M0,500 Q300,400 600,450 T1200,400 L1200,600 L0,600Z" fill="{accent}" opacity="0.08"/>
    </svg>'''
    b64 = base64.b64encode(svg.encode('utf-8')).decode('ascii')
    return f"data:image/svg+xml;base64,{b64}"

# ===== 时间校验（核心）=====

def time_check(article_text, current_year, current_date_str):
    """
    严格时间校验
    返回: (is_valid, errors_list)
    """
    errors = []
    
    # 提取所有4位年份数字
    years_found = re.findall(r'\b(19|20)\d{2}\b', article_text)
    for year in [int(y) for y in years_found]:
        if year < current_year - 1:
            # 超过1年前的内容需要明确标注为历史回顾
            if "回顾" not in article_text and "历史" not in article_text and "此前" not in article_text:
                errors.append(f"发现 {year} 年的内容，但文章未明确说明是历史回顾")
        elif year > current_year:
            errors.append(f"发现 {year} 年的内容，这是未来时间！当前是 {current_year} 年")
    
    # 检查相对时间表述是否合理
    for pattern, unit, max_val in [
        (r'(\d+)天前', 'days', 60),
        (r'(\d+)周前', 'weeks', 8),
        (r'(\d+)个月前', 'months', 3)
    ]:
        for match in re.findall(pattern, article_text):
            if int(match) > max_val:
                errors.append(f"发现'{match}{unit[:-1]}前'的表述，超过{max_val}{unit}应给出具体日期")
    
    return len(errors) == 0, errors

# ===== 主入口 =====

def main():
    ensure_dirs()
    
    input_path = BASE_DIR / "articles_input.json"
    if not input_path.exists():
        log("错误: 未找到输入文件 articles_input.json")
        sys.exit(1)
    
    with open(input_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    # 数据规范化
    articles_data = []
    for i, item in enumerate(raw_data):
        normalized = {
            'id': i,
            'page_id': 5 + i,  # 封面0 + 目录1-4 + 文章从5开始
            'section_name': item.get('section', ''),
            'section_title': item.get('section_title', ''),
            'title': item.get('title', ''),
            'subtitle': item.get('subtitle', ''),
            'kicker': item.get('kicker', ''),
            'caption': item.get('caption', '图示：' + item.get('title', '')),
            'author': item.get('author', '本刊编辑部'),
            'source': item.get('source', '综合报道'),
            'read_time': item.get('read_time', '8 min'),
            'content': item.get('content', ''),
            'source_image': item.get('source_image', ''),
            'image_credit': item.get('image_credit', ''),
            'search_image': item.get('search_image', ''),
            'search_credit': item.get('search_credit', ''),
            'extras': item.get('extras', []),
        }
        articles_data.append(normalized)
    
    now = datetime.now()
    date_info = {
        "date": now.strftime("%B %d, %Y"),
        "date_cn": now.strftime("%Y年%m月%d日"),
        "weekday": now.strftime("%A"),
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "vol_num": (now - datetime(2026, 8, 1)).days + 1,
    }
    
    log(f"构建日期: {date_info['date_cn']}")
    log(f"期号: Vol.{date_info['vol_num']:03d}")
    
    # 时间校验
    for item in articles_data:
        valid, errors = time_check(item['content'], date_info['year'], date_info['date'])
        if not valid:
            log(f"⚠️ [{item['section_title']}] 时间校验失败:")
            for err in errors:
                log(f"   - {err}")
    
    # 构建HTML（build_html函数约300行，包含完整杂志布局CSS+JS）
    # ... 
    
    log("✓ 构建完成!")

if __name__ == "__main__":
    main()
```

---

## 四、输入JSON格式示例

```json
[
  {
    "section": "World",
    "section_title": "国际政治",
    "title": "塔利班掌权五周年：阿富汗女性权利的至暗时刻",
    "subtitle": "56国联合声明未能阻止240万女孩失学，联合国称正经历近代史上最严重人权倒退",
    "kicker": "Afghanistan · Women's Rights · Vol.028",
    "caption": "喀布尔街头，一名女性在塔利班禁令下艰难求生",
    "author": "张明远",
    "source": "综合报道",
    "read_time": "12 min",
    "content": "**2026年8月15日，喀布尔**——五年前这一天，塔利班武装以惊人的速度重新占领阿富汗首都。\n\n第二段正文...",
    "source_image": "https://example.com/afghanistan-photo.jpg",
    "image_credit": "图片来源：Reuters",
    "extras": [
      {
        "type": "timeline",
        "title": "塔利班掌权时间线",
        "events": [
          {"date": "2021年8月15日", "description": "塔利班占领喀布尔"},
          {"date": "2022年12月", "description": "禁止女性上大学"},
          {"date": "2024年8月", "description": "联合国谴责系统性压迫"}
        ]
      },
      {
        "type": "entity_cards",
        "title": "关键人物",
        "entities": [
          {"name": "海巴图拉·阿洪扎达", "role": "塔利班最高领导人", "description": "以严苛教法统治阿富汗，拒绝国际社会所有改革呼吁"},
          {"name": "希芭·阿卜杜拉", "role": "阿富汗女性权益活动家", "description": "在地下秘密组织女子学校，面临死刑威胁仍坚持发声"}
        ]
      }
    ]
  },
  {
    "section": "Technology",
    "section_title": "科技动态",
    "title": "AI Agent接管华尔街：算法交易的下一个十年",
    "subtitle": "从高频交易到宏观预测，人工智能正在重塑全球金融市场的每一个角落",
    "kicker": "AI · Finance · Vol.028",
    "caption": "纽约证券交易所交易大厅，电子屏幕上的算法正在每秒执行数千笔交易",
    "author": "李晓峰",
    "source": "综合报道",
    "read_time": "10 min",
    "content": "**正文内容...**",
    "source_image": "https://example.com/ai-trading.jpg",
    "image_credit": "图片来源：Bloomberg",
    "extras": [
      {
        "type": "chart_bar",
        "title": "AI交易占比变化",
        "labels": ["2020", "2021", "2022", "2023", "2024", "2025"],
        "values": [35, 42, 51, 58, 67, 74],
        "color": "#8b1538"
      },
      {
        "type": "terms",
        "title": "关键术语",
        "items": [
          {"name": "高频交易(HFT)", "definition": "利用计算机算法在毫秒级时间内执行大量交易的策略"},
          {"name": "Alpha捕捉", "definition": "通过数据分析寻找能跑赢市场的超额收益来源"}
        ]
      }
    ]
  }
]
```

---

## 五、快速开始（Kimi Work环境）

```bash
# 1. 创建项目目录
mkdir -p ~/the-chronicle-web/{sections,articles,assets/{css,js,images},data}

# 2. 保存构建器代码为 chronicle_builder.py

# 3. 准备文章数据 articles_input.json

# 4. 运行构建
python3 chronicle_builder.py
# 输出: index.html（在线版）

# 5. 本地预览
python3 -m http.server 8080
# 打开 http://localhost:8080
```

---

## 六、待办清单（给Kimi Work的迭代方向）

- [ ] 单篇文章页模板（article.html）
- [ ] 栏目聚合页模板（section.html）
- [ ] 历史归档页（archive.html，按日期/期号索引）
- [ ] 搜索功能（前端全文检索）
- [ ] 数据驱动：用JSON自动生成所有静态页面
- [ ] 响应式优化（手机端导航、字体适配）
- [ ] 暗色模式切换
- [ ] RSS/Atom订阅
- [ ] GitHub Actions自动部署到GitHub Pages
- [ ] 飞书推送：从"发完整HTML"改为"发链接+摘要"

---

*迁移包版本：2026-08-29*
*原项目运行期数：Vol.001 - Vol.028*
*目标：升级为参考纽约客风格的个人数字报刊网站*
