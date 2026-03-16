# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 RiverDu.  All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.
# SPDX-License-Identifier: MIT
#
# Project: PeckTeX
# Author: RiverDu
# Date: 2026-03-12

"""
KaTeX 渲染模块
生成带有 KaTeX 依赖的 HTML 预览页面，并通过系统默认浏览器进行展示。
"""

import os
import time
import tempfile
import webbrowser
import re
import html
import base64
from pathlib import Path
from typing import Optional
from .settings import ICONS_DIR


_BRAND_NAME_CN = "啄玛"
_BRAND_NAME_EN = "PeckTeX"
_BRAND_SLOGAN_CN = "AI驱动的图片转LaTeX助手"
_BRAND_SLOGAN_EN = "From Image to LaTeX, just a peck away"


class FormulaRenderer:
    """
    轻量级原生 HTML + KaTeX 公式渲染器。
    调用系统默认浏览器新标签页，展示高排版质量的 KaTeX 渲染界面。
    """
    
    # KaTeX HTML 渲染模板
    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PeckTeX — 公式预览</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
        onload="renderMathInElement(document.body, {{
            delimiters: [
                {{left: '$$', right: '$$', display: true}},
                {{left: '$', right: '$', display: false}},
                {{left: '\\\\[', right: '\\\\]', display: true}},
                {{left: '\\\\(', right: '\\\\)', display: false}}
            ]
        }});"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: #F0F4F8;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 32px 4%;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            color: #334155;
        }}
        .card {{
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.06);
            width: 100%;
            max-width: 1200px;
            overflow: hidden;
        }}
        .formula-section {{
            padding: 24px 48px 16px;
            font-size: 20px;
            min-height: 80px;
        }}
        /* 每个独立公式块可横向滚动，多个块纵向排列 */
        .formula-block {{
            margin: 12px 0;
            overflow-x: auto;
            text-align: center;
        }}
        /* 公式间的说明文字段落 */
        .formula-text {{
            margin: 8px 0;
            text-align: center;
            color: #475569;
            font-size: 14px;
            line-height: 1.6;
        }}
        .katex-display {{ overflow-x: auto; padding: 4px 0; margin: 0 !important; }}
        .divider {{ height: 1px; background: #e8ecf0; }}
        .source-section {{
            padding: 20px 28px;
            background: #f8fafc;
        }}
        .source-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 12px;
        }}
        .source-label {{ font-size: 13px; font-weight: 600; color: #FF6B6B; flex: 1; }}
        .btn-copy {{
            padding: 5px 16px;
            background: #FF6B6B;
            color: #fff;
            border: none;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
        }}
        .btn-copy:hover {{ background: #E85A5A; }}
        .source-code {{
            display: block;
            padding: 14px 18px;
            background: #1E293B;
            color: #E2E8F0;
            border: none;
            font-family: "Fira Code", Consolas, "Courier New", monospace;
            font-size: 13.5px;
            line-height: 1.8;
            white-space: pre-wrap;
            word-break: break-all;
            border-radius: 8px;
        }}
        .toast {{
            position: fixed;
            bottom: 28px;
            left: 50%;
            transform: translateX(-50%);
            background: #FF6B6B;
            color: #fff;
            padding: 8px 20px;
            border-radius: 8px;
            font-size: 13px;
            opacity: 0;
            transition: opacity 0.25s;
            pointer-events: none;
        }}
        .toast.show {{ opacity: 1; }}
        .footer {{ margin-top: 16px; font-size: 12px; color: #B0A1A1; }}
        .card-header {{
            padding: 16px 24px 0;
            display: flex;
            align-items: center;
            gap: 12px;
            background: transparent;
        }}
        .logo-icon {{ width: 32px; height: 32px; object-fit: contain; flex-shrink: 0; }}
        .logo-info {{ display: grid; grid-template-columns: auto 1fr; column-gap: 8px; row-gap: 2px; align-items: baseline; }}
        .logo-name-cn {{ font-size: 15px; font-weight: 700; color: #FF6B6B; }}
        .logo-slogan-cn {{ font-size: 13px; color: #64748B; }}
        .logo-name-en {{ font-size: 12px; font-weight: 600; color: #FF6B6B; }}
        .logo-slogan-en {{ font-size: 11.5px; color: #94A3B8; font-style: italic; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="card-header">
            {icon_html}
            <div class="logo-info">
                <span class="logo-name-cn">{name_cn}</span><span class="logo-slogan-cn">{slogan_cn}</span>
                <span class="logo-name-en">{name_en}</span><span class="logo-slogan-en">{slogan_en}</span>
            </div>
        </div>
        <div class="formula-section">{formula}</div>
        <div class="divider"></div>
        <div class="source-section">
            <div class="source-header">
                <span class="source-label">LaTeX 源码</span>
                <button class="btn-copy" onclick="downloadPage()">下载页面</button>
                <button class="btn-copy" onclick="copyLatex()">复制 LaTeX</button>
            </div>
            <pre class="source-code" id="sourceCode">{source}</pre>
        </div>
    </div>
    <p class="footer">Copyright © 2026 RiverDu · PeckTeX<br>LaTeX 渲染由 <a href="https://katex.org" style="color:#B0A1A1;">KaTeX</a> (MIT License) 提供 </p>
    <div class="toast" id="toast"></div>
    <script>
        const rawLatex = document.getElementById('sourceCode').textContent;

        function downloadPage() {{
            const blob = new Blob(['<!DOCTYPE html>' + document.documentElement.outerHTML], {{type: 'text/html;charset=utf-8'}});
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'pecktex_formula.html';
            a.click();
            URL.revokeObjectURL(a.href);
        }}

        function copyLatex() {{
            navigator.clipboard.writeText(rawLatex).then(
                () => showToast('✓ 已复制'),
                () => {{
                    const ta = document.createElement('textarea');
                    ta.value = rawLatex;
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand('copy');
                    document.body.removeChild(ta);
                    showToast('✓ 已复制');
                }}
            );
        }}

        function showToast(msg) {{
            const el = document.getElementById('toast');
            el.textContent = msg;
            el.classList.add('show');
            setTimeout(() => el.classList.remove('show'), 1800);
        }}
    </script>
</body>
</html>
"""

    _icon_data_uri_cache: Optional[str] = None

    @classmethod
    def _load_icon_data_uri(cls) -> str:
        """将应用图标转换为 PNG base64 data URI（确保浏览器兼容），缓存结果；失败时返回空字符串"""
        if cls._icon_data_uri_cache is not None:
            return cls._icon_data_uri_cache
        icon_path = ICONS_DIR / "app_32.ico"
        try:
            from PySide6.QtGui import QPixmap
            from PySide6.QtCore import QBuffer, QIODevice
            pixmap = QPixmap(str(icon_path))
            if pixmap.isNull():
                cls._icon_data_uri_cache = ""
                return ""
            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            pixmap.save(buf, "PNG")
            png_bytes = bytes(buf.data())
            data = base64.b64encode(png_bytes).decode('ascii')
            cls._icon_data_uri_cache = f"data:image/png;base64,{data}"
        except Exception:
            cls._icon_data_uri_cache = ""
        return cls._icon_data_uri_cache

    @classmethod
    def _split_formula_blocks(cls, raw_code: str, has_delimiters: bool, is_inline: bool) -> str:
        """
        将公式内容分割并包装到独立的块级容器中，保证多个公式竖向排列而非并排。
        - 无定界符：整体补 $$ 触发块级渲染。
        - 单个公式：整体包装为一个可横向滚动的块。
        - 多个 $$...$$ 块：各自包装，公式间的文字作为段落独立渲染。
        """
        if not has_delimiters and not is_inline:
            return f'<div class="formula-block">$$\n{html.escape(raw_code)}\n$$</div>'

        # 尝试按 $$...$$ 分割，统计独立公式块数量
        parts = re.split(r'(\$\$.*?\$\$)', raw_code, flags=re.DOTALL)
        display_blocks = [p for p in parts if re.fullmatch(r'\$\$.*\$\$', p, re.DOTALL)]

        if len(display_blocks) <= 1:
            # 单个公式块（或使用 \[ \] 等其它定界符），整体包装
            return f'<div class="formula-block">{html.escape(raw_code)}</div>'

        # 多个 $$..$$ 公式块：各自包装成独立行，文本段落单独渲染
        result = []
        for part in parts:
            if not part:
                continue
            if re.fullmatch(r'\$\$.*\$\$', part, re.DOTALL):
                result.append(f'<div class="formula-block">{html.escape(part)}</div>')
            elif part.strip():
                result.append(f'<p class="formula-text">{html.escape(part.strip())}</p>')
        return '\n'.join(result)

    @classmethod
    def render(cls, latex_code: str) -> Optional[str]:
        """
        生成 LaTeX 公式渲染并在默认浏览器中打开
        :param latex_code: 原始的 LaTeX 公式代码
        :return: 生成的临时 HTML 文件路径，若失败则返回 None
        """
        if not latex_code or not latex_code.strip():
            return None
            
        try:
            # 去掉代码最外层可能附带的 Markdown 重复外壳，防止 KaTeX 解析出双重 $$
            raw_code = re.sub(
                r'^\s*```(?:latex)?\s*(.*?)\s*```\s*$', r'\1',
                latex_code.strip(), flags=re.DOTALL | re.IGNORECASE
            ).strip()

            # HTML 安全转义。KaTeX auto-render 通过读取 textContent 解析，浏览器自动还原实体，
            # 转义可防止公式中的 <, >, & 破坏 DOM 结构。源码区展示和复制同用此值。
            escaped = html.escape(raw_code)

            # 环境自适应补全：若大模型未提供定界符，则主动补上 $$ 触发块级渲染
            has_delimiters = any(d in raw_code for d in ['$$', '\\[', '\\(', '\\begin{'])
            # 行内公式：以单 $ 包裹，且内部不含 $$ 双符
            is_inline = raw_code.startswith('$') and raw_code.endswith('$') and '$$' not in raw_code
            # 构建公式 HTML：多公式竖排，单公式或行内公式直接包装
            formula_html = cls._split_formula_blocks(raw_code, has_delimiters, is_inline)

            # 构建图标 HTML：通过 QPixmap 将 ICO 转为 PNG base64 嵌入，确保浏览器兼容
            icon_uri = cls._load_icon_data_uri()
            icon_html = (
                f'<img class="logo-icon" src="{icon_uri}" alt="PeckTeX">'
                if icon_uri else '<span class="logo-icon"></span>'
            )

            # 生成独立的临时 HTML 文件，防止高频预览时产生并发覆写冲突
            filename = f"pecktex_preview_{int(time.time() * 1000)}.html"
            path = os.path.join(tempfile.gettempdir(), filename)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(cls.HTML_TEMPLATE.format(
                    formula=formula_html, source=escaped, icon_html=icon_html,
                    name_cn=_BRAND_NAME_CN, name_en=_BRAND_NAME_EN,
                    slogan_cn=_BRAND_SLOGAN_CN, slogan_en=_BRAND_SLOGAN_EN,
                ))

            webbrowser.open(Path(path).resolve().as_uri())
            return path

        except Exception as e:
            raise RuntimeError(f"打开失败: {e}")
