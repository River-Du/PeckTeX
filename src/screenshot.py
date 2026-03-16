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
截图模块
提供多屏幕支持的局部区域屏幕截取功能，基于 PySide6 构建无边框全屏透明遮罩。
通过截取原屏幕并通过鼠标框选截取指定坐标范围内的图像，最终生成临时截图文件。
"""

import os
import tempfile
from typing import Callable, Optional, List

from PySide6.QtWidgets import QWidget, QApplication, QLabel
from PySide6.QtGui import QCursor, QPixmap, QMouseEvent, QKeyEvent
from PySide6.QtCore import Qt, QRect, QPoint


def _event_pos_to_point(event) -> QPoint:
    """兼容 PySide6 新旧版本事件坐标接口。"""
    if hasattr(event, "position"):
        return event.position().toPoint()
    return event.pos()


class CaptureWindow(QWidget):
    """
    针对单一显示器的浮层。多显示器环境下，每块屏分别独占一个 CaptureWindow。
    底层展示屏幕静态原图，顶层使用纯色透明遮罩构成选区外框。
    """
    def __init__(self, screen_obj, controller):
        super().__init__()
        self.screen_obj = screen_obj
        self.controller = controller
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        
        # 将窗口卡在该显示器的逻辑坐标系内
        self.setGeometry(screen_obj.geometry())
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        
        # 抓取原图物理像素及其设备像素比
        self.pixmap: QPixmap = screen_obj.grabWindow(0)
        self.ratio: float = self.pixmap.devicePixelRatio()

        self._init_ui()

        self.start_point = QPoint()
        self.end_point = QPoint()
        self.is_drawing = False

    def _init_ui(self) -> None:
        """初始化 UI 图层和遮罩"""
        self.bg_label = QLabel(self)
        
        # 兼容高分屏的高清展示
        self.bg_label.setPixmap(self.pixmap)
        self.bg_label.setGeometry(0, 0, self.width(), self.height())

        # 创建四个方向的遮罩矩形以及选区虚线框
        mask_style = "background-color: rgba(0, 0, 0, 100);"
        
        self.top_mask = QWidget(self)
        self.bottom_mask = QWidget(self)
        self.left_mask = QWidget(self)
        self.right_mask = QWidget(self)
        
        for mask in (self.top_mask, self.bottom_mask, self.left_mask, self.right_mask):
            mask.setStyleSheet(mask_style)
            
        self.border_box = QWidget(self)
        self.border_box.setStyleSheet("border: 2px dashed #F44336; background-color: transparent;")
        self.border_box.hide()

        # 初始遮盖全屏状态
        self.top_mask.setGeometry(0, 0, self.width(), self.height())
        self.bottom_mask.setGeometry(0, 0, 0, 0)
        self.left_mask.setGeometry(0, 0, 0, 0)
        self.right_mask.setGeometry(0, 0, 0, 0)

    def update_masks(self) -> None:
        """根据当前鼠标拖拽生成的矩形，严丝合缝地更新四周遮挡层"""
        if not self.is_drawing or self.start_point.isNull() or self.end_point.isNull():
            return
            
        rect = QRect(self.start_point, self.end_point).normalized()
        w, h = self.width(), self.height()
        rx, ry, rw, rh = rect.x(), rect.y(), rect.width(), rect.height()
        
        self.top_mask.setGeometry(0, 0, w, ry)
        self.bottom_mask.setGeometry(0, ry + rh, w, h - (ry + rh))
        self.left_mask.setGeometry(0, ry, rx, rh)
        self.right_mask.setGeometry(rx + rw, ry, w - (rx + rw), rh)
        
        self.border_box.setGeometry(rect)
        if self.border_box.isHidden():
            self.border_box.show()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """鼠标按下，确定起点并初始化选区状态"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_point = _event_pos_to_point(event)
            self.end_point = self.start_point
            self.is_drawing = True
            self.update_masks()
        elif event.button() == Qt.MouseButton.RightButton:
            self.controller.cancel_capture()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """鼠标拖拽移动，纯图形推移"""
        if self.is_drawing:
            self.end_point = _event_pos_to_point(event)
            self.update_masks()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """鼠标松开，换算至物理高分屏坐标，从内存原始图像获取无损裁切"""
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.is_drawing = False
            self.end_point = _event_pos_to_point(event)
            
            rect = QRect(self.start_point, self.end_point).normalized()
            
            # 限制最小拖拽防误触
            if rect.width() > 5 and rect.height() > 5:
                # 换算至 QPixmap 的物理坐标系剪裁高清片段
                physical_rect = QRect(
                    int(rect.x() * self.ratio),
                    int(rect.y() * self.ratio),
                    int(rect.width() * self.ratio),
                    int(rect.height() * self.ratio)
                )
                cropped = self.pixmap.copy(physical_rect)
                
                fd, path = tempfile.mkstemp(suffix='.png', prefix='pecktex_')
                os.close(fd)
                
                cropped.save(path, "PNG", 100)
                self.controller.finish_capture(path)
            else:
                self.controller.cancel_capture()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """按键事件：支持 Esc 直退"""
        if event.key() == Qt.Key.Key_Escape:
            self.controller.cancel_capture()


class ScreenCapture:
    """截图呼叫中枢组件，负责拉画多屏遮罩并在截图成功或取消时销毁所有悬浮窗"""
    def __init__(self):
        self.callback: Optional[Callable[[Optional[str]], None]] = None
        self.capture_windows: List[CaptureWindow] = []
        self.temp_file: Optional[str] = None

    def start_capture(self, callback: Callable[[Optional[str]], None]) -> None:
        self.callback = callback
        self.capture_windows = []
        
        screens = QApplication.screens()
        if not screens:
            self.cancel_capture()
            return

        # 为每一块现存屏幕一对一分配透明截图版底
        for s in screens:
            w = CaptureWindow(s, self)
            self.capture_windows.append(w)
            
        for w in self.capture_windows:
            w.show()
            w.raise_()
            w.activateWindow()

    def _dispose_windows(self) -> None:
        """集中释放截图浮层，避免多路径清理不一致。"""
        for w in self.capture_windows:
            w.hide()
            w.close()
            w.deleteLater()
        self.capture_windows.clear()

    def finish_capture(self, path: str) -> None:
        # 卸载所有屏罩
        self._dispose_windows()
        
        self.temp_file = path
        if self.callback:
            cb = self.callback
            self.callback = None
            cb(path)

    def cancel_capture(self) -> None:
        self._dispose_windows()
        
        if self.callback:
            cb = self.callback
            self.callback = None
            cb(None)

    def cleanup(self) -> None:
        """主叫或退出销毁时释放物理磁盘图片缓存"""
        if self.temp_file and os.path.exists(self.temp_file):
            try:
                os.remove(self.temp_file)
                self.temp_file = None
            except Exception:
                pass
