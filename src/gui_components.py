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
GUI 组件库模块
封装并实现整个 PeckTeX UI 架构中引用的各种自定义 Qt 组件。
"""

import os
from typing import List, Optional
from functools import partial
import datetime
import html as html_lib

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton, QLabel,
    QComboBox, QLineEdit, QTextEdit, QScrollArea, QFrame, QMenu,
    QSizePolicy, QDialog, QStyledItemDelegate, QStyle, QStyleOptionComboBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QEvent, QRect
from PySide6.QtGui import QPixmap, QPainter, QTextBlockFormat, QTextCursor, QColor

import theme


def _make_header_btn(text: str, tooltip: str = "", style_fn=None) -> QPushButton:
    """创建标准小按钮（header 按钮），统一样式：高 22px、无焦点、手型光标"""
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedHeight(22)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setStyleSheet((style_fn or theme.button_secondary)())
    if tooltip:
        btn.setToolTip(tooltip)
    return btn


class DeleteItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hovered_del_row: int = -1

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        rect = option.rect
        colors = theme.DELEGATE_COLORS
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_del_hovered = index.row() == self.hovered_del_row

        if is_selected:
            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(colors['brand_primary']))
            painter.drawRect(rect.left(), rect.top(), 3, rect.height())
            painter.restore()

        del_width = 14
        del_height = 14
        del_rect = QRect(rect.right() - 20, rect.top() + (rect.height() - del_height) // 2, del_width, del_height)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(Qt.PenStyle.NoPen)
        if is_del_hovered:
            bg_color = colors['brand_primary_light']
        elif is_selected:
            bg_color = colors['selected_bg']
        else:
            bg_color = colors['neutral_bg']
        painter.setBrush(QColor(bg_color))
        painter.drawRoundedRect(del_rect, 3, 3)

        text_color = colors['brand_primary'] if is_del_hovered else (colors['selected_text'] if is_selected else colors['text_hint'])
        painter.setPen(QColor(text_color))
        font = painter.font()
        font.setPixelSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(del_rect, Qt.AlignmentFlag.AlignCenter, "×")
        painter.restore()


class NonScrollComboBox(QComboBox):
    itemDeleted = Signal(str)

    def __init__(self):
        super().__init__()
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setStyleSheet(theme.combobox_style())
        self.view().viewport().installEventFilter(self)
        self.setItemDelegate(DeleteItemDelegate(self))
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        if self.lineEdit():
            self.lineEdit().setCursor(Qt.CursorShape.IBeamCursor)

    def event(self, ev: QEvent) -> bool:
        """利用 Hover 事件精确控制光标：通过 subControlRect 获取箭头按钮精确区域，实现像素级对齐"""
        if ev.type() in (QEvent.Type.HoverEnter, QEvent.Type.HoverMove):
            opt = QStyleOptionComboBox()
            self.initStyleOption(opt)
            arrow_rect = self.style().subControlRect(
                QStyle.ComplexControl.CC_ComboBox, opt, QStyle.SubControl.SC_ComboBoxArrow, self
            )
            cursor = (Qt.CursorShape.PointingHandCursor
                      if arrow_rect.contains(ev.position().toPoint())
                      else Qt.CursorShape.ArrowCursor)
            self.setCursor(cursor)
        elif ev.type() == QEvent.Type.HoverLeave:
            self.unsetCursor()
        return super().event(ev)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QColor(theme.THEME['text_secondary']))
        painter.setFont(self.font())
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        arrow_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox, opt, QStyle.SubControl.SC_ComboBoxArrow, self
        )
        painter.drawText(arrow_rect, Qt.AlignmentFlag.AlignCenter, "▼")

    def wheelEvent(self, e):
        e.ignore()

    def eventFilter(self, obj, event):
        if obj == self.view().viewport():
            if event.type() == QEvent.Type.MouseMove:
                pos = event.position().toPoint()
                index = self.view().indexAt(pos)
                new_hovered = -1
                if index.isValid():
                    rect = self.view().visualRect(index)
                    del_rect = QRect(self.view().viewport().width() - 20, rect.top() + (rect.height() - 14) // 2, 14, 14).adjusted(-3, -3, 3, 3)
                    if del_rect.contains(pos):
                        new_hovered = index.row()
                        self.view().viewport().setCursor(Qt.CursorShape.PointingHandCursor)
                    else:
                        self.view().viewport().unsetCursor()
                else:
                    self.view().viewport().unsetCursor()
                delegate = self.itemDelegate()
                if delegate.hovered_del_row != new_hovered:
                    delegate.hovered_del_row = new_hovered
                    self.view().viewport().update()
            elif event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
                if event.button() == Qt.MouseButton.LeftButton:
                    pos = event.position().toPoint()
                    index = self.view().indexAt(pos)
                    if index.isValid():
                        rect = self.view().visualRect(index)
                        vp_width = self.view().viewport().width()
                        del_rect = QRect(vp_width - 20, rect.top() + (rect.height() - 14) // 2, 14, 14).adjusted(-3, -3, 3, 3)
                        if del_rect.contains(pos):
                            if event.type() == QEvent.Type.MouseButtonRelease:
                                text = self.itemText(index.row())
                                self.hidePopup()
                                self.itemDeleted.emit(text)
                            return True
        return super().eventFilter(obj, event)


class SettingsPanel(QFrame):
    screenshotRequested = Signal()
    pasteRequested = Signal()
    openRequested = Signal()
    recognizeRequested = Signal()
    abortRecognizeRequested = Signal()
    platformChanged = Signal(str)
    functionChanged = Signal(str)
    saveSettingsRequested = Signal()
    resetSettingsRequested = Signal()
    importSettingsRequested = Signal()
    testServiceRequested = Signal()

    deletePlatformRequested = Signal(str)
    deleteModelRequested = Signal(str)
    deleteFunctionRequested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("SettingsPanel")
        self.setStyleSheet(theme.card_style("SettingsPanel"))
        self.setMinimumWidth(200)
        self.setMaximumWidth(280)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self._build_header(layout)
        self._build_form(layout)
        self._build_prompt(layout)
        self._build_actions(layout)

        self.is_running = False
        self.recognize_shortcut_text = "Alt+Return"

    def _build_header(self, layout: QVBoxLayout):
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)

        title = QLabel("设置")
        title.setStyleSheet(theme.label_title())
        title_row.addWidget(title)
        title_row.addStretch()

        self.btn_test = _make_header_btn("API 测试", "测试当前 API 配置是否可用")
        self.btn_test.clicked.connect(lambda: self.testServiceRequested.emit())
        title_row.addWidget(self.btn_test)
        layout.addLayout(title_row)

    def _build_form(self, layout: QVBoxLayout):
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(4)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.platform_combo = NonScrollComboBox()
        self.platform_combo.currentTextChanged.connect(self.platformChanged.emit)
        self.platform_combo.itemDeleted.connect(self.deletePlatformRequested.emit)

        self.api_url_entry = QLineEdit()
        self.api_url_entry.setStyleSheet(theme.input_style())

        self.api_key_entry = QLineEdit()
        self.api_key_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_entry.setStyleSheet(theme.input_style())

        self.model_combo = NonScrollComboBox()
        self.model_combo.itemDeleted.connect(self.deleteModelRequested.emit)

        self.function_combo = NonScrollComboBox()
        self.function_combo.currentTextChanged.connect(self.functionChanged.emit)
        self.function_combo.itemDeleted.connect(self.deleteFunctionRequested.emit)

        form_layout.addRow(f"<span style='{theme.label_secondary()}'>平台：</span>", self.platform_combo)
        form_layout.addRow(f"<span style='{theme.label_secondary()}'>URL：</span>", self.api_url_entry)
        form_layout.addRow(f"<span style='{theme.label_secondary()}'>Key：</span>", self.api_key_entry)
        form_layout.addRow(f"<span style='{theme.label_secondary()}'>模型：</span>", self.model_combo)
        form_layout.addRow(f"<span style='{theme.label_secondary()}'>功能：</span>", self.function_combo)

        layout.addLayout(form_layout)

    def _build_prompt(self, layout: QVBoxLayout):
        prompt_label = QLabel("提示词：")
        prompt_label.setStyleSheet(theme.label_secondary())
        prompt_label.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(prompt_label)

        self.prompt_text = QTextEdit()
        self.prompt_text.setStyleSheet(theme.input_style())
        self.prompt_text.setMaximumHeight(60)
        self.prompt_text.setAcceptRichText(False)
        layout.addWidget(self.prompt_text)

        layout.addSpacing(6)

        config_btn_row = QHBoxLayout()
        config_btn_row.setSpacing(4)

        reset_btn = _make_header_btn("重置", "重置所有配置为系统默认值")
        reset_btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        reset_btn.clicked.connect(lambda: self.resetSettingsRequested.emit())
        config_btn_row.addWidget(reset_btn)

        import_btn = _make_header_btn("导入", "从 JSON 文件导入配置")
        import_btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        import_btn.clicked.connect(lambda: self.importSettingsRequested.emit())
        config_btn_row.addWidget(import_btn)

        self.btn_save = _make_header_btn("保存配置", "保存当前配置到 config.json，可在其中设置更多内容")
        self.btn_save.clicked.connect(lambda: self.saveSettingsRequested.emit())
        config_btn_row.addWidget(self.btn_save, stretch=1)

        layout.addLayout(config_btn_row)

        layout.addStretch()

    def _build_actions(self, layout: QVBoxLayout):
        checkbox_container = QVBoxLayout()
        checkbox_container.setContentsMargins(0, 0, 0, 0)
        checkbox_container.setSpacing(2)

        checkbox_row1 = QHBoxLayout()
        checkbox_row1.setSpacing(16)

        self.check_auto_recognize = QCheckBox("自动识别")
        self.check_auto_recognize.setStyleSheet(theme.checkbox_compact_style())
        self.check_auto_recognize.setToolTip("图片更新时自动识别（连续/文本识别时不生效）")
        checkbox_row1.addWidget(self.check_auto_recognize)

        self.check_auto_copy = QCheckBox("自动复制")
        self.check_auto_copy.setStyleSheet(theme.checkbox_compact_style())
        self.check_auto_copy.setToolTip("识别完成后自动将结果复制到剪贴板")
        checkbox_row1.addWidget(self.check_auto_copy)

        checkbox_row1.addStretch()
        checkbox_container.addLayout(checkbox_row1)

        checkbox_row2 = QHBoxLayout()
        checkbox_row2.setSpacing(16)

        self.check_continuous = QCheckBox("连续识别")
        self.check_continuous.setStyleSheet(theme.checkbox_compact_style())
        self.check_continuous.setToolTip("自动识别图片文件夹中的所有图片")
        self.check_continuous.stateChanged.connect(self._on_continuous_changed)
        checkbox_row2.addWidget(self.check_continuous)

        self.check_text_recognition = QCheckBox("文本识别")
        self.check_text_recognition.setStyleSheet(theme.checkbox_compact_style())
        self.check_text_recognition.setToolTip("将识别结果区文本附在提示词后发送，不发送图片")
        self.check_text_recognition.stateChanged.connect(self._on_text_recognition_changed)
        checkbox_row2.addWidget(self.check_text_recognition)

        checkbox_row2.addStretch()
        checkbox_container.addLayout(checkbox_row2)

        layout.addLayout(checkbox_container)
        layout.addSpacing(4)
        
        action_layout = QVBoxLayout()
        action_layout.setSpacing(10)

        input_btn_layout = QHBoxLayout()
        input_btn_layout.setSpacing(4)

        self.btn_ss = QPushButton("截图")
        self.btn_ss.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ss.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_ss.setStyleSheet(theme.button_action())
        self.btn_ss.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_ss.setMinimumHeight(36)
        self.btn_ss.setToolTip("截取屏幕区域作为识别图片")
        self.btn_ss.clicked.connect(lambda: self.screenshotRequested.emit())
        input_btn_layout.addWidget(self.btn_ss)

        self.btn_paste = QPushButton("粘贴")
        self.btn_paste.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_paste.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_paste.setStyleSheet(theme.button_action())
        self.btn_paste.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_paste.setMinimumHeight(36)
        self.btn_paste.setToolTip("从剪贴板粘贴图片")
        self.btn_paste.clicked.connect(lambda: self.pasteRequested.emit())
        input_btn_layout.addWidget(self.btn_paste)

        btn_open = QPushButton("文件")
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_open.setStyleSheet(theme.button_action())
        btn_open.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_open.setMinimumHeight(36)
        btn_open.setToolTip("从文件选择图片")
        btn_open.clicked.connect(lambda: self.openRequested.emit())
        input_btn_layout.addWidget(btn_open)

        action_layout.addLayout(input_btn_layout)

        self.recognize_btn = QPushButton("开始识别")
        self.recognize_btn.setStyleSheet(theme.button_primary())
        self.recognize_btn.setMinimumHeight(44)
        self.recognize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.recognize_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.recognize_btn.setToolTip("识别当前图片中的公式")
        self.recognize_btn.clicked.connect(self._on_recognize_clicked)
        action_layout.addWidget(self.recognize_btn)

        layout.addLayout(action_layout)

    def _on_continuous_changed(self, state):
        if state:
            self.check_text_recognition.blockSignals(True)
            self.check_text_recognition.setChecked(False)
            self.check_text_recognition.blockSignals(False)

    def _on_text_recognition_changed(self, state):
        if state:
            self.check_continuous.blockSignals(True)
            self.check_continuous.setChecked(False)
            self.check_continuous.blockSignals(False)

    def _on_recognize_clicked(self):
        if self.is_running:
            self.abortRecognizeRequested.emit()
        else:
            self.recognizeRequested.emit()

    def set_recognize_shortcut_text(self, text: str):
        self.recognize_shortcut_text = text
        self._update_recognize_tooltip()
        self.toggle_recognize_state(self.is_running)

    def _update_recognize_tooltip(self):
        if self.recognize_shortcut_text:
            self.recognize_btn.setToolTip(f"识别当前图片中的公式 (快捷键：{self.recognize_shortcut_text})")
        else:
            self.recognize_btn.setToolTip("识别当前图片中的公式")

    def toggle_recognize_state(self, running: bool):
        self.is_running = running

        if self.is_running:
            self.recognize_btn.setText("终止")
            self.recognize_btn.setStyleSheet(theme.button_danger_large())
            self.recognize_btn.setToolTip("终止当前任务")
        else:
            self.recognize_btn.setText("开始识别")
            self.recognize_btn.setStyleSheet(theme.button_primary())
            self._update_recognize_tooltip()

    def set_screenshot_shortcut_text(self, text: str):
        if text:
            self.btn_ss.setToolTip(f"截取屏幕区域作为识别图片 (快捷键：{text})")
        else:
            self.btn_ss.setToolTip("截取屏幕区域作为识别图片")

    def set_paste_shortcut_text(self, text: str):
        if text:
            self.btn_paste.setToolTip(f"从剪贴板粘贴图片 (快捷键：{text})")
        else:
            self.btn_paste.setToolTip("从剪贴板粘贴图片")

    def set_save_dirty(self, dirty: bool) -> None:
        """更新保存按钮的显示状态以指示是否有未保存的更改"""
        if dirty:
            self.btn_save.setText("* 保存配置")
            self.btn_save.setToolTip("配置已修改但未保存，点击保存到 config.json")
        else:
            self.btn_save.setText("保存配置")
            self.btn_save.setToolTip("保存当前配置到 config.json，可在其中设置更多内容")


class ImageViewerDialog(QDialog):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("原图查看")
        self.resize(800, 600)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setStyleSheet(f"QScrollArea {{ {theme.image_viewer_bg()} border: none; }}")
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(theme.image_viewer_bg())
        self.image_label.setScaledContents(True)

        self.pixmap = QPixmap(image_path)
        self.pixmap.setDevicePixelRatio(self.devicePixelRatioF())
        self.image_label.setPixmap(self.pixmap)

        self.base_size = self.pixmap.size() / self.devicePixelRatioF()
        self.image_label.resize(self.base_size)

        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area)

        self.scale_factor = 1.0

    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        old_factor = self.scale_factor

        if angle > 0:
            self.scale_factor *= 1.15
        elif angle < 0:
            self.scale_factor *= 0.85

        self.scale_factor = max(0.1, min(self.scale_factor, 15.0))

        new_size = self.base_size * self.scale_factor
        self.image_label.resize(new_size)

        factor_change = self.scale_factor / old_factor
        def adjust_scrollbar(scrollbar):
            scrollbar.setValue(int(factor_change * scrollbar.value() + ((factor_change - 1) * scrollbar.pageStep() / 2)))

        adjust_scrollbar(self.scroll_area.horizontalScrollBar())
        adjust_scrollbar(self.scroll_area.verticalScrollBar())

        event.accept()


class ClickableWidget(QWidget):
    """可点击的自定义 Widget，支持独立的普通态/悬停态样式切换"""
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._normal_style = ""
        self._hover_style = ""

    def setHoverStyle(self, style: str):
        self._hover_style = style

    def enterEvent(self, event):
        super().enterEvent(event)
        if self._hover_style:
            super().setStyleSheet(self._hover_style)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if self._hover_style:
            super().setStyleSheet(self._normal_style)

    def setStyleSheet(self, style: str):
        """设置基础样式并记录，悬停态通过 enterEvent/leaveEvent 独立管理"""
        self._normal_style = style
        super().setStyleSheet(style)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class WheelEventFilter:
    """滚轮事件过滤器工厂，用于阻止滚轮事件传播到父组件"""
    
    @staticmethod
    def create(target_widget):
        def filter_event(event):
            bar = target_widget.verticalScrollBar()
            if bar:
                step = 16 if event.angleDelta().y() < 0 else -16
                bar.setValue(bar.value() + step)
                event.accept()
            else:
                event.ignore()
        return filter_event


class ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class PreviewImageLabel(ClickableLabel):
    def __init__(self, placeholder_text=""):
        super().__init__(placeholder_text)
        self.placeholder_text = placeholder_text
        self._original_pixmap = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(10, 10)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

    def set_original_pixmap(self, pixmap: QPixmap):
        self._original_pixmap = pixmap
        if not pixmap or pixmap.isNull():
            self.setText(self.placeholder_text)
            super().setPixmap(QPixmap())
        else:
            self.setText("")
            self._update_pixmap()

    def clear(self):
        self._original_pixmap = None
        super().clear()
        self.setText(self.placeholder_text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_pixmap()

    def _update_pixmap(self):
        if self._original_pixmap and not self._original_pixmap.isNull() and self.width() > 0 and self.height() > 0:
            ratio = self.devicePixelRatioF()
            target_width = int(self.width() * ratio)
            target_height = int(self.height() * ratio)

            scaled = self._original_pixmap.scaled(
                target_width, target_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            scaled.setDevicePixelRatio(ratio)
            super().setPixmap(scaled)

    def has_image(self) -> bool:
        return self._original_pixmap is not None and not self._original_pixmap.isNull()

    def get_original_pixmap(self) -> Optional[QPixmap]:
        """返回原始像素图，无图片时返回 None"""
        return self._original_pixmap


class ImagePreviewPanel(QFrame):
    imageClicked = Signal()
    imageDropped = Signal(str)
    openFolderRequested = Signal()
    nextImageRequested = Signal()
    copyImageRequested = Signal()
    clearImageRequested = Signal()
    saveImageToFolderRequested = Signal()
    screenshotRequested = Signal()
    pasteRequested = Signal()
    openFileRequested = Signal()
    recognizeRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("ImagePreviewPanel")
        self.setStyleSheet(theme.card_style("ImagePreviewPanel"))
        self.setAcceptDrops(True)
        self.setMinimumHeight(80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        title_container = QWidget()
        title_container.setFixedHeight(24)
        title_row = QHBoxLayout(title_container)
        title_row.setContentsMargins(0, 1, 0, 1)
        title_row.setSpacing(4)
        title = QLabel("识别目标")
        title.setStyleSheet(theme.label_section())
        title_row.addWidget(title)
        hint = QLabel("(待识别的图片)")
        hint.setStyleSheet(theme.label_hint())
        title_row.addWidget(hint)
        
        title_row.addStretch()
        
        btn_open_folder = _make_header_btn("图片文件夹", "打开内置图片文件夹，可暂存图片和点击“下一张”载入。\r\n勾选连续识别后会自动识别该文件夹中的所有图片")
        btn_open_folder.clicked.connect(lambda: self.openFolderRequested.emit())
        title_row.addWidget(btn_open_folder)
        
        btn_next = _make_header_btn("下一张", "加载文件夹中的下一张图片")
        btn_next.clicked.connect(lambda: self.nextImageRequested.emit())
        title_row.addWidget(btn_next)
        
        self._image_count_label = QLabel("-/-")
        self._image_count_label.setStyleSheet(theme.label_secondary())
        title_row.addWidget(self._image_count_label)
        
        layout.addWidget(title_container)

        self.image_label = PreviewImageLabel("截图、粘贴、拖入或选择图片")
        self.image_label.setMinimumHeight(0)
        self.image_label.setStyleSheet(theme.image_preview_placeholder())
        self.image_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.image_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.image_label.customContextMenuRequested.connect(self._on_context_menu)
        self.image_label.clicked.connect(self.imageClicked.emit)

        layout.addWidget(self.image_label, stretch=1)

        self._shortcut_hints: dict = {}
        
        self._folder_total = 0
        self._is_busy: bool = False
        self._supported_formats = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp'}
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                if url.isLocalFile():
                    path = url.toLocalFile()
                    ext = os.path.splitext(path)[1].lower()
                    if ext in self._supported_formats:
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                if url.isLocalFile():
                    path = url.toLocalFile()
                    ext = os.path.splitext(path)[1].lower()
                    if ext in self._supported_formats:
                        self.imageDropped.emit(path)
                        event.acceptProposedAction()
                        return
        event.ignore()
    
    def set_image_count(self, current: int, total: int):
        self._folder_total = total
        if total > 0 and current > 0:
            self._image_count_label.setText(f"{current}/{total}")
        else:
            self._image_count_label.setText(f"-/{total}" if total > 0 else "-/-")
    
    def set_folder_total(self, total: int):
        self._folder_total = total

    def set_busy(self, busy: bool) -> None:
        """设置忙碌状态；忙碌时禁用右键菜单中的"开始识别"选项"""
        self._is_busy = busy

    def set_shortcut_hints(self, hints: dict):
        """设置右键菜单中显示的快捷键提示，如 {'screenshot': 'Alt+S', 'paste': 'Ctrl+V'}"""
        self._shortcut_hints = hints

    def _on_context_menu(self, pos):
        menu = QMenu(self)
        has_img = self.image_label.has_image()
        sc = self._shortcut_hints

        act_copy = menu.addAction(f"复制图片\t{sc.get('copy', '')}" if sc.get('copy') else "复制图片")
        act_copy.setEnabled(has_img)

        act_clear = menu.addAction("清除图片")
        act_clear.setEnabled(has_img)

        act_save = menu.addAction("保存到图片文件夹")
        act_save.setEnabled(has_img)

        menu.addSeparator()

        sc_paste = sc.get('paste', '')
        act_paste = menu.addAction(f"粘贴\t{sc_paste}" if sc_paste else "粘贴")

        sc_ss = sc.get('screenshot', '')
        act_ss = menu.addAction(f"截图\t{sc_ss}" if sc_ss else "截图")

        act_file = menu.addAction("文件")

        menu.addSeparator()

        sc_rec = sc.get('recognize', '')
        act_recognize = menu.addAction(f"开始识别\t{sc_rec}" if sc_rec else "开始识别")
        act_recognize.setEnabled(not self._is_busy)

        action = menu.exec(self.image_label.mapToGlobal(pos))
        if action == act_copy:
            self.copyImageRequested.emit()
        elif action == act_clear:
            self.clearImageRequested.emit()
        elif action == act_save:
            self.saveImageToFolderRequested.emit()
        elif action == act_paste:
            self.pasteRequested.emit()
        elif action == act_ss:
            self.screenshotRequested.emit()
        elif action == act_file:
            self.openFileRequested.emit()
        elif action == act_recognize:
            self.recognizeRequested.emit()


class ResultPanel(QFrame):
    copyRequested = Signal()
    renderRequested = Signal()
    clearRequested = Signal()
    saveToHistoryRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("ResultPanel")
        self.setStyleSheet(theme.card_style("ResultPanel"))
        self.setMinimumHeight(80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        self._build_header(layout)
        self._build_content(layout)

    def _build_header(self, layout: QVBoxLayout):
        title_container = QWidget()
        title_container.setFixedHeight(24)
        header = QHBoxLayout(title_container)
        header.setContentsMargins(0, 1, 0, 1)

        title = QLabel("识别结果")
        title.setStyleSheet(theme.label_section())
        header.addWidget(title)
        hint = QLabel("(公式代码)")
        hint.setStyleSheet(theme.label_hint())
        header.addWidget(hint)
        header.addStretch()
        header.setSpacing(4)

        btn_clear = _make_header_btn("清空", "清空识别结果")
        btn_clear.clicked.connect(lambda: self.result_text.clear())
        header.addWidget(btn_clear)

        btn_save = _make_header_btn("记录", "将当前识别结果存入历史记录")
        btn_save.clicked.connect(lambda: self.saveToHistoryRequested.emit())
        header.addWidget(btn_save)

        btn_render = _make_header_btn("预览", "在浏览器中预览 LaTeX 效果（需要网络）")
        btn_render.clicked.connect(lambda: self.renderRequested.emit())
        header.addWidget(btn_render)

        self.btn_copy = _make_header_btn("复制", "复制识别结果到剪贴板")
        self.btn_copy.clicked.connect(lambda: self.copyRequested.emit())
        header.addWidget(self.btn_copy)

        layout.addWidget(title_container)

    def _build_content(self, layout: QVBoxLayout):
        self.result_text = QTextEdit()
        self.result_text.setStyleSheet(theme.result_text_style())
        self.result_text.setMinimumHeight(0)
        self.result_text.setAcceptRichText(False)
        layout.addWidget(self.result_text, stretch=1)


class HistoryPanel(QFrame):
    clearRequested = Signal()
    loadHistoryRequested = Signal(str)
    copyTextRequested = Signal(str)
    deleteHistoryRequested = Signal(int)
    exportRequested = Signal()
    importRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("HistoryPanel")
        self.setStyleSheet(theme.card_style("HistoryPanel"))
        self.setMinimumHeight(80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        title_container = QWidget()
        title_container.setFixedHeight(24)
        hist_header = QHBoxLayout(title_container)
        hist_header.setContentsMargins(0, 1, 0, 1)
        hist_header.setSpacing(4)

        hist_title = QLabel("历史记录")
        hist_title.setStyleSheet(theme.label_section())
        hist_header.addWidget(hist_title)
        hint = QLabel("(识别结果存档)")
        hint.setStyleSheet(theme.label_hint())
        hist_header.addWidget(hint)
        hist_header.addStretch()

        self._scroll_to_bottom = True
        self.btn_scroll_toggle = _make_header_btn("置底", "滚动到底部")
        self.btn_scroll_toggle.clicked.connect(self._toggle_scroll_position)
        hist_header.addWidget(self.btn_scroll_toggle)

        btn_export = _make_header_btn("导出", "将所有历史记录导出为 JSON 文件")
        btn_export.clicked.connect(lambda: self.exportRequested.emit())
        hist_header.addWidget(btn_export)

        btn_import = _make_header_btn("导入", "从 JSON 文件导入历史记录（将覆盖当前记录）")
        btn_import.clicked.connect(lambda: self.importRequested.emit())
        hist_header.addWidget(btn_import)

        self.clear_history_btn = _make_header_btn("清空", "清空所有历史记录")
        self.clear_history_btn.clicked.connect(lambda: self.clearRequested.emit())
        hist_header.addWidget(self.clear_history_btn)

        layout.addWidget(title_container)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(0)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(f"QScrollArea {{ {theme.scroll_area_bg()} }}")
        self.scroll_area.wheelEvent = WheelEventFilter.create(self.scroll_area)

        self.history_container = QWidget()
        self.history_container.setObjectName("HistoryContainer")
        self.history_container.setStyleSheet("QWidget#HistoryContainer { background: transparent; }")
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(0)
        self.scroll_area.setWidget(self.history_container)

        layout.addWidget(self.scroll_area, stretch=1)

    def _toggle_scroll_position(self):
        """在置顶和置底之间循环切换历史记录滚动位置"""
        bar = self.scroll_area.verticalScrollBar()
        if self._scroll_to_bottom:
            bar.setValue(bar.maximum())
            self.btn_scroll_toggle.setText("置顶")
            self.btn_scroll_toggle.setToolTip("滚动到顶部")
            self._scroll_to_bottom = False
        else:
            bar.setValue(bar.minimum())
            self.btn_scroll_toggle.setText("置底")
            self.btn_scroll_toggle.setToolTip("滚动到底部")
            self._scroll_to_bottom = True

    def refresh_history(self, history: List[str]):
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        for i, res in enumerate(history):
            row = QFrame()
            row.setStyleSheet(theme.history_row_style())
            h_layout = QHBoxLayout(row)
            h_layout.setContentsMargins(4, 2, 4, 2)
            h_layout.setSpacing(4)

            num_lbl = QLabel(f"{i+1}.")
            num_lbl.setStyleSheet(theme.label_history_num())
            num_lbl.setFixedWidth(20)
            h_layout.addWidget(num_lbl)

            preview_text = res.replace('\n', ' ').strip()

            le = QLineEdit(preview_text)
            le.setReadOnly(True)
            le.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            le.setCursorPosition(0)
            le.setToolTip(res)
            le.setStyleSheet(theme.history_item_style())

            h_layout.addWidget(le, stretch=1)

            btn_del = _make_header_btn("删除", "删除此条记录", style_fn=theme.button_ghost)
            btn_del.clicked.connect(partial(self.deleteHistoryRequested.emit, i))
            h_layout.addWidget(btn_del)

            btn_load = _make_header_btn("加载", "加载此条记录到结果框", style_fn=theme.button_ghost)
            btn_load.clicked.connect(partial(self.loadHistoryRequested.emit, res))
            h_layout.addWidget(btn_load)

            btn_copy = _make_header_btn("复制", "复制此条记录", style_fn=theme.button_ghost)
            btn_copy.clicked.connect(partial(self.copyTextRequested.emit, res))
            h_layout.addWidget(btn_copy)

            self.history_layout.addWidget(row)

            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet(theme.divider_line())
            self.history_layout.addWidget(line)

        self.history_layout.addStretch()


class CollapsibleChatPanel(QFrame):
    sendRequested = Signal(str)
    abortChatRequested = Signal()
    resetRequested = Signal()
    clearRequested = Signal()
    appendToResultRequested = Signal(str)
    expandStateChanged = Signal(bool)

    _COLLAPSED_HEIGHT: int = 64
    _COLLAPSE_THRESHOLD: int = 80

    def __init__(self):
        super().__init__()
        self.setObjectName("CollapsibleChatPanel")
        self.setStyleSheet(theme.card_style("CollapsibleChatPanel"))

        self._expanded = False
        self._expanded_height = 200
        self._current_status = ""
        self._max_log = 100

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(8, 6, 8, 6)
        self._main_layout.setSpacing(4)

        self._build_header()
        self._build_content()

        self.is_running = False
        self.setMinimumHeight(self._COLLAPSED_HEIGHT)
        self.setMaximumHeight(self._COLLAPSED_HEIGHT)

    def _build_header(self):
        title_container = QWidget()
        title_container.setFixedHeight(24)
        header = QHBoxLayout(title_container)
        header.setContentsMargins(0, 1, 0, 1)
        header.setSpacing(4)

        title = QLabel("运行日志")
        title.setStyleSheet(theme.label_section())
        header.addWidget(title)
        hint = QLabel("(系统消息与AI会话)")
        hint.setStyleSheet(theme.label_hint())
        header.addWidget(hint)
        header.addStretch()

        btn_reset = _make_header_btn("重置对话", "重置对话，开启新一轮")
        btn_reset.clicked.connect(lambda: self.resetRequested.emit())
        header.addWidget(btn_reset)

        btn_clear = _make_header_btn("清空", "清空消息面板内容")
        btn_clear.clicked.connect(self._on_clear_clicked)
        header.addWidget(btn_clear)

        self._main_layout.addWidget(title_container)

        self._status_bar = ClickableWidget()
        self._status_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._status_bar.setStyleSheet(theme.status_bar_style())
        self._status_bar.setHoverStyle(theme.status_bar_hover_style())
        self._status_bar.clicked.connect(self._toggle_expand)
        self._status_bar.setFixedHeight(24)
        self._status_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        status_layout = QHBoxLayout(self._status_bar)
        status_layout.setContentsMargins(6, 2, 6, 2)

        self._status_label = QLabel("ℹ️ 等待识别")
        self._status_label.setStyleSheet(theme.status_label_style())
        self._status_label.setMinimumWidth(0)
        self._status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        status_layout.addWidget(self._status_label, stretch=1)

        self._expand_hint = QLabel("展开 ▲")
        self._expand_hint.setStyleSheet(theme.label_hint())
        status_layout.addWidget(self._expand_hint)

        self._main_layout.addWidget(self._status_bar)

    def _build_content(self):
        self._content = QWidget()
        self._content.setVisible(False)
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chat_history.customContextMenuRequested.connect(self._on_chat_history_context_menu)
        self.chat_history.wheelEvent = WheelEventFilter.create(self.chat_history)

        self.chat_history.document().setDefaultStyleSheet(theme.chat_document_css())
        self.chat_history.setStyleSheet(theme.chat_history_style())
        content_layout.addWidget(self.chat_history, stretch=1)

        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)

        self.entry = QLineEdit()
        self.entry.setStyleSheet(theme.input_style())
        self.entry.setMaximumHeight(26)
        self.entry.setPlaceholderText("在此处输入内容，与AI聊天")
        self.entry.setToolTip("输入消息后按回车或点击发送")
        self.entry.returnPressed.connect(self._on_send)
        input_layout.addWidget(self.entry, stretch=1)

        self.check_attach_image = QCheckBox("附图")
        self.check_attach_image.setStyleSheet(theme.checkbox_font_style())
        self.check_attach_image.setToolTip("勾选后将当前图片随消息一起发送")
        input_layout.addWidget(self.check_attach_image)

        self.btn_send = QPushButton("发送")
        self.btn_send.setFixedHeight(26)
        self.btn_send.setStyleSheet(theme.button_secondary())
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_send.setToolTip("发送消息给AI")
        self.btn_send.clicked.connect(self._on_send_clicked)
        input_layout.addWidget(self.btn_send)

        content_layout.addLayout(input_layout)

        self._main_layout.addWidget(self._content)

    def _toggle_expand(self):
        if self._expanded:
            self._expanded_height = self.height()
            self._collapse()
        else:
            self._expand()

    def _expand(self):
        self._expanded = True
        self._content.setVisible(True)
        self._expand_hint.setText("折叠 ▼")
        self.setMinimumHeight(self._COLLAPSED_HEIGHT)
        self.setMaximumHeight(16777215)
        self.expandStateChanged.emit(True)

    def _collapse(self):
        self._expanded = False
        self._content.setVisible(False)
        self._expand_hint.setText("展开 ▲")
        self.setMinimumHeight(self._COLLAPSED_HEIGHT)
        self.setMaximumHeight(self._COLLAPSED_HEIGHT)
        self.expandStateChanged.emit(False)

    def check_splitter_resize(self, panel_height: int) -> None:
        """展开态下高度低于阈值时触发折叠（折叠态通过固定高度锁定，无需处理）"""
        if self._expanded and panel_height <= self._COLLAPSE_THRESHOLD:
            self._expanded_height = max(self._expanded_height, 150)
            self._collapse()

    def set_status(self, text: str, icon: str = "info"):
        icons = {
            "success": "✅",
            "error": "❌",
            "loading": "⏳",
            "info": "ℹ️",
            "chat": "💬"
        }
        icon_char = icons.get(icon, "ℹ️")
        time_str = datetime.datetime.now().strftime("[%H:%M:%S]")
        self._full_status_text = f"{icon_char} {time_str} {text}"
        self._current_status = text
        self._update_status_label()

    def _update_status_label(self):
        if not hasattr(self, '_full_status_text'):
            return
        fm = self._status_label.fontMetrics()
        available_width = self._status_label.width()
        elided = fm.elidedText(self._full_status_text, Qt.TextElideMode.ElideRight, available_width)
        self._status_label.setText(elided)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_status_label()

    def _on_clear_clicked(self):
        self.chat_history.clear()
        self.clearRequested.emit()

    def _on_send_clicked(self):
        if self.is_running:
            self.abortChatRequested.emit()
        else:
            self._on_send()

    def _on_send(self):
        if self.is_running or not self.btn_send.isEnabled():
            return
        text = self.entry.text().strip()
        if text:
            self.sendRequested.emit(text)

    def append_log(self, role: str, msg: str, model: str = "", icon: Optional[str] = None):
        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        colors = theme.ROLE_COLORS
        style_color = colors.get(role, colors['default'])

        escaped_msg = html_lib.escape(msg)
        formatted_msg = escaped_msg.replace("\n", "<br>")

        role_label = f"{role} [{html_lib.escape(model)}]" if role == "AI" and model else role

        time_suffix = ""
        if role in ("Task", "Sys", "User"):
            time_str = datetime.datetime.now().strftime("%H:%M:%S")
            time_suffix = f" <span style='{theme.chat_time_suffix_style()}'>[{time_str}]</span>"

        if role == "Sys":
            html_content = f"""<span style='font-family: Consolas; font-size: 12px;'>
        <b style='color: {style_color}'>{role_label}:</b>{time_suffix}
        <span style='color: {colors["Sys"]}'>{formatted_msg}</span>
        </span>"""
            self.set_status(msg, icon or self._infer_icon_from_msg(msg))
        else:
            html_content = f"""<span style='font-family: Consolas; font-size: 12px;'>
        <b style='color: {style_color}'>{role_label}:</b>{time_suffix}
        <span style='color: {colors["default"]}'>{formatted_msg}</span>
        </span>"""

        if not self.chat_history.document().isEmpty():
            block_fmt = QTextBlockFormat()
            block_fmt.setTopMargin(2)
            cursor.insertBlock(block_fmt)

        cursor.insertHtml(html_content)
        self.chat_history.setTextCursor(cursor)

        scroll_bar = self.chat_history.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())
        self.chat_history.ensureCursorVisible()

        if self._max_log > 0 and self.chat_history.document().blockCount() > self._max_log:
            self.trim_log(self._max_log)

    def toggle_chat_state(self, running: bool):
        self.is_running = running
        if self.is_running:
            self.btn_send.setText("终止")
            self.btn_send.setStyleSheet(theme.button_danger())
        else:
            self.btn_send.setText("发送")
            self.btn_send.setStyleSheet(theme.button_secondary())

    def _on_chat_history_context_menu(self, pos) -> None:
        """右键菜单：选中文本时增加「追加至识别结果」选项"""
        menu = self.chat_history.createStandardContextMenu()
        selected_text = self.chat_history.textCursor().selectedText().replace('\u2029', '\n').strip()
        if selected_text:
            menu.addSeparator()
            action = menu.addAction("追加至识别结果")
            action.triggered.connect(lambda: self.appendToResultRequested.emit(selected_text))
        menu.exec(self.chat_history.mapToGlobal(pos))

    def _infer_icon_from_msg(self, msg: str) -> str:
        if "失败" in msg or "错误" in msg or "异常" in msg or "取消" in msg:
            return "error"
        if "成功" in msg or "正常" in msg:
            return "success"
        if "正在" in msg or "测试" in msg:
            return "loading"
        return "info"

    def update_status_from_sys(self, msg: str):
        self.set_status(msg, self._infer_icon_from_msg(msg))

    def trim_log(self, max_entries: int) -> int:
        """移除超出上限的旧日志条目，返回移除的条目数"""
        doc = self.chat_history.document()
        excess = doc.blockCount() - max_entries
        if excess <= 0:
            return 0
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(excess):
            cursor.movePosition(
                QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.KeepAnchor
            )
        cursor.removeSelectedText()
        return excess
