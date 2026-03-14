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
主题管理模块
统一管理 PeckTeX 的全局颜色变量与样式模板函数。
所有样式均通过 THEME 字典引用颜色值，确保视觉一致性。
函数返回 Qt StyleSheet 字符串，供组件 setStyleSheet() 使用。
"""

THEME = {
    "brand_primary": "#FF6B6B",
    "brand_primary_hover": "#E85A5A",
    "brand_primary_light": "#FFE8E8",
    "brand_primary_pressed": "#D84848",
    "brand_secondary": "#FFB4B4",

    "neutral_bg": "#F5F5F5",
    "neutral_bg_hover": "#EBEBEB",
    "neutral_text": "#424242",
    "neutral_border": "#E0E0E0",
    "neutral_surface": "#E8E8E8",

    "aux_success": "#4CAF50",
    "aux_danger": "#FFCDD2",
    "aux_danger_text": "#C62828",
    "aux_info": "#2196F3",
    "aux_task": "#512DA8",

    "text_primary": "#212121",
    "text_secondary": "#757575",
    "text_hint": "#9E9E9E",

    "card_bg": "#FFFFFF",
    "card_radius": "10px",

    "window_bg": "#F5F5F5",
    "input_bg": "#EFEFEF",
    "input_bg_hover": "#EEEEEE",
    "input_bg_disabled": "#E0E0E0",

    "divider": "#E8E8E8",

    "viewer_bg": "#2E2E2E",
}


def button_primary() -> str:
    """主要操作按钮样式，用于开始识别等核心操作。"""
    return f"""
        QPushButton {{
            background: {THEME['brand_primary']};
            color: white;
            padding: 10px 16px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            border: none;
        }}
        QPushButton:hover {{
            background: {THEME['brand_primary_hover']};
        }}
        QPushButton:pressed {{
            background: {THEME['brand_primary_pressed']};
        }}
        QPushButton:disabled {{
            background: {THEME['brand_secondary']};
        }}
    """


def button_secondary() -> str:
    """次要按钮样式，用于发送等辅助操作。"""
    return f"""
        QPushButton {{
            background: {THEME['neutral_surface']};
            color: {THEME['neutral_text']};
            padding: 4px 10px;
            border-radius: 5px;
            font-size: 11px;
            font-weight: 500;
            border: none;
        }}
        QPushButton:hover {{
            background: {THEME['brand_primary_light']};
            color: {THEME['brand_primary']};
        }}
        QPushButton:pressed {{
            background: {THEME['brand_secondary']};
        }}
    """


def button_action() -> str:
    """操作按钮样式，用于设置区按钮（添加/删除平台、模型等）。"""
    return f"""
        QPushButton {{
            background: {THEME['neutral_surface']};
            color: {THEME['neutral_text']};
            padding: 4px 8px;
            border-radius: 5px;
            font-size: 14px;
            font-weight: bold;
            border: none;
        }}
        QPushButton:hover {{
            background: {THEME['brand_primary_light']};
            color: {THEME['brand_primary']};
        }}
        QPushButton:pressed {{
            background: {THEME['brand_secondary']};
        }}
    """


def button_ghost() -> str:
    """幽灵按钮样式，无背景的轻量化按钮，用于展开/折叠图标。"""
    return f"""
        QPushButton {{
            background: transparent;
            color: {THEME['text_hint']};
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            border: none;
        }}
        QPushButton:hover {{
            background: {THEME['brand_primary_light']};
            color: {THEME['brand_primary']};
        }}
    """


def button_danger() -> str:
    """危险按钮样式（小尺寸），用于终止发送/对话等取消操作。"""
    return f"""
        QPushButton {{
            background: {THEME['aux_danger']};
            color: {THEME['aux_danger_text']};
            padding: 4px 10px;
            border-radius: 5px;
            font-size: 11px;
            font-weight: 500;
            border: none;
        }}
        QPushButton:hover {{
            background: {THEME['brand_secondary']};
        }}
    """


def button_danger_large() -> str:
    """危险按钮样式（大尺寸），用于终止识别操作。"""
    return f"""
        QPushButton {{
            background: {THEME['aux_danger']};
            color: {THEME['aux_danger_text']};
            padding: 10px 16px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            border: none;
        }}
        QPushButton:hover {{
            background: {THEME['brand_secondary']};
        }}
    """


def card_style(object_name: str) -> str:
    """卡片容器样式，用于设置面板、结果面板等区域。"""
    return f"""
        QFrame#{object_name} {{
            background-color: {THEME['card_bg']};
            border-radius: {THEME['card_radius']};
            border: none;
        }}
    """


def input_style() -> str:
    """输入框样式，用于 QLineEdit 和 QTextEdit。"""
    return f"""
        QLineEdit, QTextEdit {{
            background-color: {THEME['input_bg']};
            border: none;
            border-radius: 6px;
            padding: 4px 6px;
            color: {THEME['text_primary']};
            font-size: 12px;
        }}
        QLineEdit:hover, QTextEdit:hover {{
            background-color: {THEME['input_bg_hover']};
        }}
        QLineEdit:focus, QTextEdit:focus {{
            background-color: white;
            border: 1px solid {THEME['brand_primary']};
        }}
        QLineEdit:disabled, QTextEdit:disabled {{
            background-color: {THEME['input_bg_disabled']};
            color: {THEME['text_hint']};
        }}
    """


def combobox_style() -> str:
    """下拉框样式，包含下拉箭头和弹出列表。"""
    return f"""
        QComboBox {{
            background-color: {THEME['input_bg']};
            border: none;
            border-radius: 6px;
            padding: 4px 6px;
            color: {THEME['text_primary']};
            font-size: 12px;
        }}
        QComboBox:hover {{
            background-color: {THEME['input_bg_hover']};
        }}
        QComboBox:focus {{
            background-color: white;
            border: 1px solid {THEME['brand_primary']};
        }}
        QComboBox:on {{
            background-color: white;
            border: 1px solid {THEME['brand_primary']};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: right center;
            width: 20px;
            border: none;
            background: transparent;
        }}
        QComboBox::down-arrow {{
            image: none;
        }}
        QComboBox QAbstractItemView {{
            background-color: white;
            border: 1px solid {THEME['neutral_border']};
            border-radius: 6px;
            selection-background-color: {THEME['brand_primary_light']};
            selection-color: {THEME['text_primary']};
            outline: none;
        }}
        QComboBox QAbstractItemView::item {{
            padding: 4px 8px;
            min-height: 20px;
        }}
        QComboBox:disabled {{
            background-color: {THEME['input_bg_disabled']};
            color: {THEME['text_hint']};
        }}
        QLineEdit {{
            background: transparent;
            border: none;
            color: {THEME['text_primary']};
        }}
        QLineEdit:disabled {{
            color: {THEME['text_hint']};
        }}
    """


def result_text_style() -> str:
    """结果文本框样式，用于显示识别结果的 LaTeX 代码。"""
    return f"""
        QTextEdit {{
            background-color: {THEME['input_bg']};
            border: none;
            border-radius: 6px;
            padding: 6px 8px;
            color: {THEME['text_primary']};
            font-family: Consolas, 'Courier New', monospace;
            font-size: 13px;
        }}
        QTextEdit:focus {{
            background-color: white;
            border: 1px solid {THEME['brand_primary']};
        }}
    """


def history_item_style() -> str:
    """历史记录项样式，只读输入框。"""
    return f"""
        QLineEdit {{
            color: {THEME['text_secondary']};
            font-family: Consolas, 'Courier New', monospace;
            font-size: 11px;
            border: none;
            background: transparent;
            selection-background-color: {THEME['brand_primary_light']};
            selection-color: {THEME['text_primary']};
        }}
    """


def tooltip_style() -> str:
    """全局工具提示样式。"""
    return f"""
        QToolTip {{
            color: {THEME['text_primary']};
            background-color: white;
            border: 1px solid {THEME['neutral_border']};
            font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            font-size: 12px;
            padding: 0 3px;
        }}
    """


def label_title() -> str:
    """标题标签样式，用于面板主标题。"""
    return f"font-size: 14px; font-weight: bold; color: {THEME['brand_primary']};"


def label_section() -> str:
    """章节标签样式，用于设置区分组标题。"""
    return f"font-size: 14px; font-weight: 600; color: {THEME['brand_primary']};"


def label_secondary() -> str:
    """次要标签样式，用于普通说明文字。"""
    return f"color: {THEME['text_secondary']}; font-size: 12px;"


def label_hint() -> str:
    """提示标签样式，用于辅助提示文字。"""
    return f"color: {THEME['text_hint']}; font-size: 11px;"


def label_history_num() -> str:
    """历史记录编号标签样式。"""
    return f"color: {THEME['text_hint']}; font-family: Consolas; font-size: 11px; border: none; background: transparent;"


def checkbox_font_style() -> str:
    """复选框字体样式。"""
    return "QCheckBox { font-size: 12px; }"


def checkbox_compact_style() -> str:
    """紧凑型复选框样式，用于多个复选框并排显示。"""
    return """
        QCheckBox {
            font-size: 11px;
            spacing: 4px;
            padding: 2px 0px;
        }
        QCheckBox::indicator {
            width: 14px;
            height: 14px;
        }
    """


def image_viewer_bg() -> str:
    """图片查看器背景样式。"""
    return f"background-color: {THEME['viewer_bg']};"


def image_preview_placeholder() -> str:
    """图片预览占位符样式。"""
    return f"""
        background: {THEME['input_bg']};
        color: {THEME['text_hint']};
        font-size: 12px;
        border-radius: 6px;
    """


def scroll_area_bg() -> str:
    """滚动区域背景样式。"""
    return f"border: none; background: {THEME['input_bg']}; border-radius: 6px;"


def splitter_handle() -> str:
    """分割器手柄样式。"""
    return f"QSplitter::handle {{ background-color: transparent; }}"


def history_row_style() -> str:
    """历史记录行样式，包含悬停效果。"""
    return f"""
        QFrame {{ background: transparent; border: none; outline: none; }}
        QFrame:hover {{ background: {THEME['brand_primary_light']}; border-radius: 4px; }}
    """


def divider_line() -> str:
    """分隔线样式。"""
    return f"background-color: {THEME['divider']}; border: none; max-height: 1px;"


def status_bar_style() -> str:
    """状态栏样式。"""
    return f"""
        background-color: {THEME['input_bg']};
        border-radius: 6px;
    """


def status_bar_hover_style() -> str:
    """状态栏悬停样式。"""
    return f"""
        background-color: {THEME['brand_primary_light']};
        border-radius: 6px;
    """


def status_label_style() -> str:
    """状态标签样式。"""
    return f"""
        QLabel {{
            color: {THEME['brand_primary']};
            font-size: 12px;
            border: none;
            background: transparent;
        }}
    """


def chat_history_style() -> str:
    """聊天历史区域样式。"""
    return f"""
        QTextEdit {{
            color: {THEME['text_secondary']};
            background: {THEME['input_bg']};
            border: none;
            border-radius: 6px;
            font-family: Consolas;
            font-size: 12px;
            padding: 6px;
        }}
    """


def chat_document_css() -> str:
    """聊天文档 CSS 样式，用于 HTML 渲染。"""
    return (
        f"p {{ margin: 2px 0; line-height: 1.2; font-family: Consolas; }} "
        f".role-user {{ color: {THEME['aux_success']}; font-weight: bold; }} "
        f".role-ai {{ color: {THEME['aux_info']}; font-weight: bold; }} "
        f".role-task {{ color: {THEME['aux_task']}; font-weight: bold; }} "
        f".msg-content {{ color: {THEME['text_secondary']}; }} "
    )


def chat_time_suffix_style() -> str:
    """聊天时间后缀样式。"""
    return f"color: {THEME['text_hint']}; font-weight: normal;"


DELEGATE_COLORS = {
    "brand_primary": THEME['brand_primary'],
    "brand_primary_light": THEME['brand_primary_light'],
    "neutral_bg": THEME['neutral_bg'],
    "text_hint": THEME['text_hint'],
    "selected_bg": THEME['neutral_bg_hover'],
    "selected_text": THEME['text_secondary'],
}
"""委托绘制颜色常量，用于自定义下拉框项渲染。"""

ROLE_COLORS = {
    "User": THEME['aux_success'],
    "Task": THEME['aux_task'],
    "Sys": THEME['brand_primary'],
    "AI": THEME['aux_info'],
    "default": THEME['text_secondary'],
}
"""角色颜色常量，用于聊天消息的角色标签着色。"""
