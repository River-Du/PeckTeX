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
啄玛 -- AI驱动的图片转LaTeX助手
PeckTeX -- From Image to LaTeX, just a peck away

啄玛 (PeckTeX) 是一款基于 Python 与 PySide6 开发的轻量级图片转 LaTeX 桌面工具。
软件通过调用视觉语言大模型（VLM）API，提取图片中的数学公式、化学方程式及手写草稿等，
输出精确的 LaTeX 格式代码，或可由用户提示词灵活定义其他输出格式。
软件设计了直观精美的界面，内置截图、历史记录管理、本地 KaTeX 网页预览等功能，
可设置截图后自动识别、完成后自动复制，并具有批量识别、文本识别、AI 问答等功能。
"""

import sys
import os

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QIcon

from src.settings import ICONS_DIR
from src.gui import PeckTeXMainWindow
import src.theme as theme


def main():
    """主程序入口"""
    app = QApplication(sys.argv)
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    app.setStyleSheet(theme.tooltip_style())
    icon_path = os.path.join(str(ICONS_DIR), "app_64.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = PeckTeXMainWindow("啄玛 PeckTeX -- AI驱动的图片转LaTeX助手 v1.0")
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
