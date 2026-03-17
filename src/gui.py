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
主应用界面模块
实现 PeckTeX 的主窗体生命周期控制、子组件组装（左右分割窗格）、
全局快捷键绑定，以及多线程请求任务的调度。
"""

import datetime
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List, Iterator, Callable, Tuple

from copy import deepcopy
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QFileDialog, QWidget, QHBoxLayout, QApplication,
    QLineEdit, QTextEdit, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QEvent
from PySide6.QtGui import QPixmap, QShortcut, QKeySequence

from .settings import SettingsManager, CONFIG_DIR, IMAGES_DIR, HISTORY_DIR, USER_DATA_ROOT
from .api_client import FormulaAPIClient
from .screenshot import ScreenCapture
from .renderer import FormulaRenderer
from .gui_components import SettingsPanel, ImagePreviewPanel, ResultPanel, HistoryPanel, CollapsibleChatPanel, ImageViewerDialog
from . import theme


_TERMINATORS = ("。", "！", "？", ".", "!", "?", "...", "…", "）", ")")

HISTORY_REFRESH_DEBOUNCE_MS = 100
CHAT_PANEL_MIN_EXPANDED_HEIGHT = 150
WORKER_WAIT_TIMEOUT_MS = 200
SCREENSHOT_MINIMIZE_DELAY_MS = 400
CONTINUOUS_RECOGNIZE_DELAY_MS = 500

def _ensure_punctuation(text: str) -> str:
    """确保文本以标点结尾"""
    return text if text.endswith(_TERMINATORS) else text + "。"


@dataclass
class APIConfig:
    """API 请求配置数据类"""
    api_key: str
    platform: str
    api_url: str
    timeout: float
    model: str
    system_prompt: str
    prompt: str
    img_path: Optional[str] = None


class APIWorker(QThread):
    chunk_signal = Signal(str)
    finished_signal = Signal()
    error_signal = Signal(str)

    def __init__(self, api: FormulaAPIClient, config: APIConfig, parent=None):
        super().__init__(parent)
        self.api = api
        self.config = config
        self._is_aborted: bool = False

    def abort(self) -> None:
        self._is_aborted = True
        if hasattr(self.api, 'interrupt'):
            self.api.interrupt()

    def run(self) -> None:
        try:
            self.api.set_credentials(
                self.config.api_key, 
                self.config.api_url, 
                self.config.timeout
            )
            generator: Iterator[str]
            if self.config.img_path:
                generator = self.api.chat_with_image(
                    self.config.img_path, 
                    self.config.prompt, 
                    self.config.model, 
                    self.config.system_prompt
                )
            else:
                generator = self.api.chat_text(
                    self.config.prompt, 
                    self.config.model, 
                    self.config.system_prompt
                )

            for chunk in generator:
                if self._is_aborted:
                    break
                self.chunk_signal.emit(chunk)

            if not self._is_aborted:
                self.finished_signal.emit()

        except Exception as e:
            if not self._is_aborted:
                self.error_signal.emit(str(e) or "未知错误")


class TestWorker(QThread):
    success_signal = Signal(str)
    error_signal = Signal(str)

    def __init__(self, api_key, platform, api_url, timeout, model, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.platform = platform
        self.api_url = api_url
        self.timeout = timeout
        self.model = model
        self._api = FormulaAPIClient()
        self._is_aborted = False

    def abort(self):
        self._is_aborted = True
        self._api.interrupt()

    def run(self):
        try:
            self._api.set_credentials(self.api_key, self.api_url, self.timeout)
            result = self._api.test_connection(self.model)
            if not self._is_aborted:
                self.success_signal.emit(result)
        except Exception as e:
            if not self._is_aborted:
                self.error_signal.emit(str(e) or "未知错误")


class PeckTeXMainWindow(QMainWindow):
    def __init__(self, window_title: str = "PeckTeX"):
        super().__init__()
        self.setWindowTitle(window_title)
        self.resize(720, 520)
        self.setStyleSheet(
            f"QMainWindow {{ background-color: {theme.THEME['window_bg']}; }}\n"
            + theme.splitter_handle()
        )

        self.settings = SettingsManager()
        self.draft = deepcopy(self.settings.settings_data)
        self.draft_last_models = {}
        self.api = FormulaAPIClient()
        self.aborted = False
        self.response_started = False
        self._config_dirty = False

        self.current_image_path: Optional[str] = None
        self.history = []
        self._temp_files = set()
        
        self._folder_images: List[str] = []
        self._folder_image_index = -1
        self._continuous_mode_active = False
        self._is_continuous_mode = False
        self._is_text_mode = False
        self._last_rec_char = ""
        self._last_chat_char = ""

        self.sc = None
        self.api_worker = None
        self._active_workers = set()
        self._adjusting_splitter = False

        self.shortcut_ss = None
        self.shortcut_rec = None
        self.paste_key_seq = None
        self._last_shortcut_conflict_signature: Optional[Tuple[str, ...]] = None

        self._history_refresh_timer = QTimer(self)
        self._history_refresh_timer.setSingleShot(True)
        self._history_refresh_timer.setInterval(HISTORY_REFRESH_DEBOUNCE_MS)
        self._history_refresh_timer.timeout.connect(self._do_history_refresh)

        self.setup_ui()
        self.load_settings()
        self._mark_clean()

        if self.settings.last_error:
            err = self.settings.last_error
            self.chat_panel.append_log("Sys", _ensure_punctuation(err), icon="error")
            self.settings.last_error = None

        QApplication.instance().installEventFilter(self)

        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._initial_shown = False

    @staticmethod
    def _key_event_to_sequence(event) -> QKeySequence:
        """兼容不同 PySide6 版本的按键组合 API。"""
        if hasattr(event, "keyCombination"):
            return QKeySequence(event.keyCombination().toCombined())
        return QKeySequence(int(event.key()) | int(event.modifiers()))

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if self.paste_key_seq and not self.paste_key_seq.isEmpty():
                if obj is self or (isinstance(obj, QWidget) and self.isAncestorOf(obj)):
                    key_sequence = self._key_event_to_sequence(event)
                    if key_sequence == self.paste_key_seq:
                        clipboard = QApplication.clipboard()
                        if clipboard.mimeData().hasImage():
                            self.paste_image(silent=True)
                            return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._show_image()

    def _on_right_splitter_moved(self, pos: int, index: int) -> None:
        """right_splitter 拖动时处理图片重布局和日志面板折叠检测"""
        if self._adjusting_splitter:
            return
        self._show_image()
        if self.chat_panel._expanded:
            sizes = self.right_splitter.sizes()
            if sizes:
                self.chat_panel.check_splitter_resize(sizes[-1])

    def _on_chat_panel_expand_state_changed(self, expanded: bool) -> None:
        """日志面板展开/折叠时按比例调整 splitter 各面板尺寸"""
        sizes = list(self.right_splitter.sizes())
        if len(sizes) != 4:
            return
        total = sum(sizes)
        collapsed_h = self.chat_panel._COLLAPSED_HEIGHT
        min_panel = 36

        self._adjusting_splitter = True
        try:
            if expanded:
                target = min(self.chat_panel._expanded_height, total - 3 * min_panel)
                target = max(target, CHAT_PANEL_MIN_EXPANDED_HEIGHT)
                need = target - sizes[-1]
                if need > 0:
                    others = sizes[:-1]
                    other_total = sum(others)
                    if other_total > 0:
                        for i in range(3):
                            give = round(need * others[i] / other_total)
                            sizes[i] = max(min_panel, sizes[i] - give)
                        sizes[-1] = total - sum(sizes[:-1])
                        self.right_splitter.setSizes(sizes)
            else:
                freed = sizes[-1] - collapsed_h
                if freed > 0:
                    others = sizes[:-1]
                    other_total = sum(others)
                    if other_total > 0:
                        for i in range(3):
                            sizes[i] += round(freed * others[i] / other_total)
                        sizes[-1] = collapsed_h
                        diff = total - sum(sizes)
                        if diff:
                            idx = max(range(3), key=lambda i: sizes[i])
                            sizes[idx] += diff
                        self.right_splitter.setSizes(sizes)
        finally:
            self._adjusting_splitter = False

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initial_shown:
            self._initial_shown = True
            QTimer.singleShot(0, lambda: self.setFocus(Qt.FocusReason.OtherFocusReason))

    def closeEvent(self, event):
        for worker in list(self._active_workers):
            if worker.isRunning():
                worker.abort()
                if not worker.wait(WORKER_WAIT_TIMEOUT_MS):
                    worker.terminate()
                    worker.wait()

        for tmp_file in self._temp_files:
            try:
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
            except Exception:
                pass

        event.accept()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(8)
        main_layout.addWidget(self.splitter)

        self.settings_panel = SettingsPanel()
        self.splitter.addWidget(self.settings_panel)

        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        self.right_splitter.setHandleWidth(4)
        self.right_splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.right_splitter)

        self.preview_panel = ImagePreviewPanel()
        self.right_splitter.addWidget(self.preview_panel)

        self.result_panel = ResultPanel()
        self.right_splitter.addWidget(self.result_panel)

        self.history_panel = HistoryPanel()
        self.right_splitter.addWidget(self.history_panel)

        self.chat_panel = CollapsibleChatPanel()
        self.right_splitter.addWidget(self.chat_panel)

        self.splitter.setSizes([200, 500])
        self.right_splitter.setSizes([120, 140, 100, 64])

        self.splitter.splitterMoved.connect(lambda *_: self._show_image())
        self.right_splitter.splitterMoved.connect(self._on_right_splitter_moved)
        self.chat_panel.expandStateChanged.connect(self._on_chat_panel_expand_state_changed)

        self.preview_panel.imageClicked.connect(self._open_original_image)
        self.preview_panel.imageDropped.connect(self._on_image_dropped)
        self.preview_panel.openFolderRequested.connect(self._open_image_folder)
        self.preview_panel.nextImageRequested.connect(self._load_next_folder_image)
        self.preview_panel.copyImageRequested.connect(self._copy_image)
        self.preview_panel.clearImageRequested.connect(self._clear_image)
        self.preview_panel.saveImageToFolderRequested.connect(self._save_image_to_folder)
        self.preview_panel.screenshotRequested.connect(self.start_screenshot)
        self.preview_panel.pasteRequested.connect(self.paste_image)
        self.preview_panel.openFileRequested.connect(self.open_image)
        self.preview_panel.recognizeRequested.connect(self.start_recognition)

        self.settings_panel.screenshotRequested.connect(self.start_screenshot)
        self.settings_panel.pasteRequested.connect(self.paste_image)
        self.settings_panel.openRequested.connect(self.open_image)
        self.settings_panel.recognizeRequested.connect(self.start_recognition)
        self.settings_panel.abortRecognizeRequested.connect(self.abort_recognition)

        self.settings_panel.platformChanged.connect(self._on_platform_change)
        self.settings_panel.functionChanged.connect(self._on_function_change)
        self.settings_panel.saveSettingsRequested.connect(self._save_settings_from_ui)
        self.settings_panel.resetSettingsRequested.connect(self._reset_settings)
        self.settings_panel.importSettingsRequested.connect(self._import_settings)

        self.settings_panel.api_key_entry.textChanged.connect(self._on_api_key_changed)
        self.settings_panel.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.settings_panel.prompt_text.textChanged.connect(self._on_prompt_changed)
        self.settings_panel.api_url_entry.textChanged.connect(self._on_api_url_changed)

        self.settings_panel.platform_combo.lineEdit().editingFinished.connect(self._commit_platform_combo)
        self.settings_panel.model_combo.lineEdit().editingFinished.connect(self._commit_model_combo)
        self.settings_panel.function_combo.lineEdit().editingFinished.connect(self._commit_function_combo)

        self.settings_panel.deletePlatformRequested.connect(self._on_delete_platform)
        self.settings_panel.deleteModelRequested.connect(self._on_delete_model)
        self.settings_panel.deleteFunctionRequested.connect(self._on_delete_function)

        for cb in (self.settings_panel.check_continuous,
                   self.settings_panel.check_text_recognition,
                   self.settings_panel.check_auto_recognize,
                   self.settings_panel.check_auto_copy):
            cb.stateChanged.connect(self._mark_dirty)

        self.result_panel.copyRequested.connect(self.copy_result)
        self.result_panel.renderRequested.connect(self.render_result)
        self.result_panel.saveToHistoryRequested.connect(
            lambda: self.save_text_to_history(self.result_panel.result_text.toPlainText())
        )

        self.history_panel.clearRequested.connect(self.clear_history)
        self.history_panel.deleteHistoryRequested.connect(self.delete_history_item)
        self.history_panel.loadHistoryRequested.connect(self.load_history_item)
        self.history_panel.copyTextRequested.connect(self._copy_to_clip)
        self.history_panel.exportRequested.connect(self._export_history)
        self.history_panel.importRequested.connect(self._import_history)

        self.chat_panel.sendRequested.connect(self.send_chat)
        self.chat_panel.abortChatRequested.connect(self.abort_chat)
        self.chat_panel.resetRequested.connect(self.reset_chat)
        self.chat_panel.clearRequested.connect(self._on_chat_clear)
        self.chat_panel.appendToResultRequested.connect(self._on_append_to_result)
        self.settings_panel.testServiceRequested.connect(self.test_service)

        ss_key = self.settings.get_shortcut("screenshot")
        if ss_key:
            self.shortcut_ss = QShortcut(QKeySequence(ss_key), self)
            self.shortcut_ss.activated.connect(self.start_screenshot)

        paste_key = self.settings.get_shortcut("paste")
        if paste_key:
            self.paste_key_seq = QKeySequence(paste_key)

        rec_key = self.settings.get_shortcut("recognize")
        if rec_key:
            self.shortcut_rec = QShortcut(QKeySequence(rec_key), self)
            self.shortcut_rec.setContext(Qt.ShortcutContext.ApplicationShortcut)
            self.shortcut_rec.activated.connect(self._on_recognize_shortcut)

    def mousePressEvent(self, event):
        focus_w = QApplication.focusWidget()
        if focus_w and isinstance(focus_w, (QLineEdit, QTextEdit, QComboBox)):
            focus_w.clearFocus()
        super().mousePressEvent(event)

    def load_settings(self):
        self.settings_panel.platform_combo.blockSignals(True)
        self.settings_panel.function_combo.blockSignals(True)
        self.settings_panel.model_combo.blockSignals(True)
        self.settings_panel.api_url_entry.blockSignals(True)
        self.settings_panel.api_key_entry.blockSignals(True)
        self.settings_panel.prompt_text.blockSignals(True)

        ss_sc = self.settings.get_shortcut('screenshot')
        paste_sc = self.settings.get_shortcut('paste')
        rec_sc = self.settings.get_shortcut('recognize')

        self.settings_panel.set_screenshot_shortcut_text(ss_sc)
        self.settings_panel.set_paste_shortcut_text(paste_sc)
        self.settings_panel.set_recognize_shortcut_text(rec_sc)

        self.preview_panel.set_shortcut_hints({
            'screenshot': ss_sc,
            'paste': paste_sc,
            'recognize': rec_sc,
        })
        self._warn_shortcut_conflicts({
            "screenshot": ss_sc,
            "paste": paste_sc,
            "recognize": rec_sc,
        })

        platforms = list(self.draft.get('platforms', {}).keys())
        self.settings_panel.platform_combo.clear()
        self.settings_panel.platform_combo.addItems(platforms)

        current_platform = self.draft.get('default', {}).get('platform', '')
        idx = self.settings_panel.platform_combo.findText(current_platform)
        if idx >= 0: self.settings_panel.platform_combo.setCurrentIndex(idx)
        elif platforms: self.settings_panel.platform_combo.setCurrentIndex(0)

        current_platform_text = self.settings_panel.platform_combo.currentText()
        self._on_platform_change(current_platform_text)

        funcs = list(self.draft.get('functions', {}).keys())
        self.settings_panel.function_combo.clear()
        self.settings_panel.function_combo.addItems(funcs)

        current_func = self.draft.get('default', {}).get('function', '')
        idx = self.settings_panel.function_combo.findText(current_func)
        if idx >= 0: self.settings_panel.function_combo.setCurrentIndex(idx)
        elif funcs: self.settings_panel.function_combo.setCurrentIndex(0)

        current_func_text = self.settings_panel.function_combo.currentText()
        self._on_function_change(current_func_text)

        self.settings_panel.platform_combo.blockSignals(False)
        self.settings_panel.function_combo.blockSignals(False)
        self.settings_panel.model_combo.blockSignals(False)
        self.settings_panel.api_url_entry.blockSignals(False)
        self.settings_panel.api_key_entry.blockSignals(False)
        self.settings_panel.prompt_text.blockSignals(False)
        
        self.settings_panel.check_continuous.blockSignals(True)
        self.settings_panel.check_text_recognition.blockSignals(True)
        self.settings_panel.check_auto_recognize.blockSignals(True)
        self.settings_panel.check_auto_copy.blockSignals(True)
        self.settings_panel.check_continuous.setChecked(self.draft.get('continuous_recognition', False))
        self.settings_panel.check_text_recognition.setChecked(self.draft.get('text_recognition', False))
        self.settings_panel.check_auto_recognize.setChecked(self.draft.get('auto_recognize', False))
        self.settings_panel.check_auto_copy.setChecked(self.draft.get('auto_copy', False))
        self.settings_panel.check_continuous.blockSignals(False)
        self.settings_panel.check_text_recognition.blockSignals(False)
        self.settings_panel.check_auto_recognize.blockSignals(False)
        self.settings_panel.check_auto_copy.blockSignals(False)

        self.chat_panel._max_log = self.draft.get('max_log', 100)

    def _warn_shortcut_conflicts(self, shortcuts: dict) -> None:
        """检测并提示快捷键冲突，避免同一按键绑定到多个动作。"""
        normalized = {}
        for action, value in shortcuts.items():
            key = (value or "").strip()
            if key:
                normalized.setdefault(key, []).append(action)

        conflicts = {key: actions for key, actions in normalized.items() if len(actions) > 1}
        if not conflicts:
            self._last_shortcut_conflict_signature = None
            return

        alias = {
            "screenshot": "截图",
            "paste": "粘贴",
            "recognize": "识别",
        }
        signature = tuple(
            sorted(
                f"{key}:{','.join(sorted(actions))}"
                for key, actions in conflicts.items()
            )
        )
        if signature == self._last_shortcut_conflict_signature:
            return

        parts = []
        for key, actions in sorted(conflicts.items()):
            labels = "、".join(alias.get(action, action) for action in sorted(actions))
            parts.append(f"{key} -> {labels}")
        self.chat_panel.append_log("Sys", f"快捷键冲突：{'; '.join(parts)}。", icon="error")
        self._last_shortcut_conflict_signature = signature

    def _create_api_worker(
        self,
        config: APIConfig,
        chunk_handler: Callable[[str], None],
        done_handler: Callable[[], None],
    ) -> None:
        """统一创建并连接 APIWorker，减少重复连接逻辑。"""
        worker = APIWorker(self.api, config, parent=self)
        self.api_worker = worker
        self._active_workers.add(worker)
        worker.chunk_signal.connect(chunk_handler)
        worker.finished_signal.connect(done_handler)
        worker.error_signal.connect(self._on_api_error)
        worker.finished.connect(self._cleanup_worker)
        worker.start()

    def _ensure_platform_draft(self, plat: str):
        if not plat: return
        self.draft.setdefault('platforms', {})
        if plat not in self.draft['platforms']:
            self.draft['platforms'][plat] = {"api_key": "", "api_url": "", "models": []}

    def _commit_platform_combo(self):
        text = self.settings_panel.platform_combo.currentText().strip()
        if text and self.settings_panel.platform_combo.findText(text) == -1:
            self.settings_panel.platform_combo.addItem(text)
            self._ensure_platform_draft(text)
            self._mark_dirty()

    def _commit_model_combo(self):
        text = self.settings_panel.model_combo.currentText().strip()
        plat = self.settings_panel.platform_combo.currentText().strip()
        if text and self.settings_panel.model_combo.findText(text) == -1:
            self.settings_panel.model_combo.addItem(text)
            if plat:
                self._ensure_platform_draft(plat)
                if text not in self.draft['platforms'][plat]['models']:
                    self.draft['platforms'][plat]['models'].append(text)
            self._mark_dirty()

    def _commit_function_combo(self):
        text = self.settings_panel.function_combo.currentText().strip()
        if text and self.settings_panel.function_combo.findText(text) == -1:
            self.settings_panel.function_combo.addItem(text)
            if 'functions' not in self.draft: self.draft['functions'] = {}
            if text not in self.draft['functions']:
                self.draft['functions'][text] = ""
            self._mark_dirty()

    def _on_api_url_changed(self, text):
        plat = self.settings_panel.platform_combo.currentText().strip()
        if plat:
            self._ensure_platform_draft(plat)
            self.draft['platforms'][plat]['api_url'] = text
            self._mark_dirty()

    def _on_api_key_changed(self, text):
        plat = self.settings_panel.platform_combo.currentText().strip()
        if plat:
            self._ensure_platform_draft(plat)
            self.draft['platforms'][plat]['api_key'] = text
            self._mark_dirty()

    def _on_model_changed(self, text):
        plat = self.settings_panel.platform_combo.currentText().strip()
        if plat:
            self._ensure_platform_draft(plat)
            self.draft_last_models[plat] = text

    def _on_prompt_changed(self):
        func = self.settings_panel.function_combo.currentText().strip()
        if func:
            if 'functions' not in self.draft: self.draft['functions'] = {}
            self.draft['functions'][func] = self.settings_panel.prompt_text.toPlainText()
            self._mark_dirty()

    def _on_platform_change(self, plat: str):
        self.settings_panel.api_url_entry.blockSignals(True)
        self.settings_panel.api_key_entry.blockSignals(True)
        self.settings_panel.model_combo.blockSignals(True)

        plat = plat.strip()

        has_plat = bool(plat)
        self.settings_panel.api_url_entry.setEnabled(has_plat)
        self.settings_panel.api_key_entry.setEnabled(has_plat)
        self.settings_panel.model_combo.setEnabled(has_plat)

        p_data = self.draft.get('platforms', {}).get(plat, {})

        if p_data:
            self.settings_panel.api_url_entry.setText(p_data.get('api_url', ''))
            self.settings_panel.api_key_entry.setText(p_data.get('api_key', ''))
            models = p_data.get('models', [])
            self.settings_panel.model_combo.clear()
            self.settings_panel.model_combo.addItems(models)
            last_m = self.draft_last_models.get(plat, models[0] if models else "")
            self.settings_panel.model_combo.setCurrentText(last_m)
        else:
            self.settings_panel.api_url_entry.setText("")
            self.settings_panel.api_key_entry.setText("")
            self.settings_panel.model_combo.clear()
            self.settings_panel.model_combo.setCurrentText("")

        self.settings_panel.api_url_entry.blockSignals(False)
        self.settings_panel.api_key_entry.blockSignals(False)
        self.settings_panel.model_combo.blockSignals(False)

    def _on_function_change(self, func: str):
        self.settings_panel.prompt_text.blockSignals(True)
        func = func.strip()

        self.settings_panel.prompt_text.setEnabled(bool(func))

        if func in self.draft.get('functions', {}):
            self.settings_panel.prompt_text.setText(self.draft['functions'][func])
        else:
            self.settings_panel.prompt_text.setText("")

        self.settings_panel.prompt_text.blockSignals(False)

    def _on_delete_platform(self, plat: str):
        if not plat: return
        if plat in self.draft.get('platforms', {}):
            del self.draft['platforms'][plat]
        while True:
            idx = self.settings_panel.platform_combo.findText(plat)
            if idx >= 0:
                self.settings_panel.platform_combo.removeItem(idx)
            else:
                break
        self._mark_dirty()

    def _on_delete_model(self, model: str):
        plat = self.settings_panel.platform_combo.currentText().strip()
        if not plat or not model: return
        if plat in self.draft.get('platforms', {}):
            models = self.draft['platforms'][plat].get('models', [])
            while model in models:
                models.remove(model)
        while True:
            idx = self.settings_panel.model_combo.findText(model)
            if idx >= 0:
                self.settings_panel.model_combo.removeItem(idx)
            else:
                break
        self._mark_dirty()

    def _on_delete_function(self, func: str):
        if not func: return
        if func in self.draft.get('functions', {}):
            del self.draft['functions'][func]
        while True:
            idx = self.settings_panel.function_combo.findText(func)
            if idx >= 0:
                self.settings_panel.function_combo.removeItem(idx)
            else:
                break
        self._mark_dirty()

    def _mark_dirty(self) -> None:
        """标记配置已修改未保存"""
        if not self._config_dirty:
            self._config_dirty = True
            self.settings_panel.set_save_dirty(True)

    def _mark_clean(self) -> None:
        """标记配置已保存"""
        self._config_dirty = False
        self.settings_panel.set_save_dirty(False)

    def _check_history_limit(self) -> None:
        """检查历史记录是否超限，超出时静默移除最早条目"""
        max_history = self.draft.get('max_history', 100)
        if len(self.history) > max_history:
            self.history = self.history[-max_history:]

    def _schedule_history_refresh(self) -> None:
        """防抖：合并短时间内的多次历史记录 UI 刷新为一次"""
        self._history_refresh_timer.start()

    def _do_history_refresh(self) -> None:
        """执行历史记录面板的实际 UI 刷新"""
        self.history_panel.refresh_history(self.history)

    def _save_settings_from_ui(self):
        plat = self.settings_panel.platform_combo.currentText().strip()
        model = self.settings_panel.model_combo.currentText().strip()
        func = self.settings_panel.function_combo.currentText().strip()
        api_url = self.settings_panel.api_url_entry.text().strip()
        apik = self.settings_panel.api_key_entry.text().strip()
        prompt = self.settings_panel.prompt_text.toPlainText().strip()

        if not plat or not func:
            self.chat_panel.append_log("Sys", "保存失败：平台和功能不能为空。", icon="error")
            return

        self._ensure_platform_draft(plat)
        self.draft['platforms'][plat]['api_url'] = api_url
        self.draft['platforms'][plat]['api_key'] = apik
        if model:
            if model not in self.draft['platforms'][plat]['models']:
                self.draft['platforms'][plat]['models'].insert(0, model)

        if 'functions' not in self.draft: self.draft['functions'] = {}
        self.draft['functions'][func] = prompt

        self.draft.setdefault('default', {})
        self.draft['default']['platform'] = plat
        self.draft['default']['model'] = model
        self.draft['default']['function'] = func
        
        self.draft['continuous_recognition'] = self.settings_panel.check_continuous.isChecked()
        self.draft['text_recognition'] = self.settings_panel.check_text_recognition.isChecked()
        self.draft['auto_recognize'] = self.settings_panel.check_auto_recognize.isChecked()
        self.draft['auto_copy'] = self.settings_panel.check_auto_copy.isChecked()

        self.settings.settings_data = deepcopy(self.draft)
        success = self.settings.save()

        if not success and self.settings.last_error:
            err = self.settings.last_error
            self.chat_panel.append_log("Sys", f"保存配置失败：{_ensure_punctuation(err)}", icon="error")
            self.settings.last_error = None
        else:
            self.chat_panel.append_log("Sys", "配置已保存。", icon="success")

        self.load_settings()
        if success:
            self._mark_clean()

    def _reset_settings(self):
        """重置所有配置为系统默认值（带二次确认）"""
        reply = QMessageBox.question(
            self, "确认重置",
            "确定要将所有配置重置为系统默认值吗？\n此操作将覆盖当前所有设置。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        success = self.settings.reset_to_defaults()
        if success:
            self.draft = deepcopy(self.settings.settings_data)
            self.draft_last_models.clear()
            self.load_settings()
            self._mark_clean()
            self.chat_panel.append_log("Sys", "配置已重置为默认值。", icon="success")
        else:
            err = self.settings.last_error or "未知错误"
            self.chat_panel.append_log("Sys", f"重置失败：{_ensure_punctuation(err)}", icon="error")
            self.settings.last_error = None

    def _import_settings(self):
        """从外部 JSON 文件导入配置（仅加载为草稿，需手动保存）"""
        path, _ = QFileDialog.getOpenFileName(
            self, "导入配置文件", str(CONFIG_DIR),
            "JSON 配置文件 (*.json);;所有文件 (*.*)"
        )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("文件内容不是有效的 JSON 对象。")
            cleaned = self.settings.validate_config(data)
            self.draft = cleaned
            self.draft_last_models.clear()
            self.load_settings()
            self._mark_dirty()
            self.chat_panel.append_log(
                "Sys",
                f"配置已从 {os.path.basename(path)} 导入（未保存）。",
                icon="success"
            )
        except json.JSONDecodeError:
            self.chat_panel.append_log("Sys", "导入失败：文件不是有效的 JSON 格式。", icon="error")
        except ValueError as e:
            self.chat_panel.append_log("Sys", f"导入失败：{_ensure_punctuation(str(e))}", icon="error")
        except Exception as e:
            self.chat_panel.append_log("Sys", f"导入失败：{_ensure_punctuation(str(e))}", icon="error")

    def set_gui_processing_state(self, is_running: bool, mode: str = 'recognize', status_text: Optional[str] = None):
        self.preview_panel.set_busy(is_running)
        if is_running:
            if mode == 'recognize':
                self.settings_panel.toggle_recognize_state(True)
                self.chat_panel.btn_send.setEnabled(False)
                self.settings_panel.btn_test.setEnabled(False)
                self.chat_panel.set_status(status_text or "正在识别...", "loading")
            elif mode == 'chat':
                self.chat_panel.toggle_chat_state(True)
                self.settings_panel.toggle_recognize_state(True)
                self.settings_panel.btn_test.setEnabled(False)
                self.chat_panel.set_status(status_text or "正在对话...", "loading")
            elif mode == 'test':
                self.settings_panel.btn_test.setEnabled(False)
                self.settings_panel.toggle_recognize_state(True)
                self.chat_panel.btn_send.setEnabled(False)
                self.chat_panel.set_status(status_text or "正在测试服务...", "loading")
        else:
            self.settings_panel.toggle_recognize_state(False)
            self.chat_panel.toggle_chat_state(False)
            self.settings_panel.recognize_btn.setEnabled(True)
            self.chat_panel.btn_send.setEnabled(True)
            self.settings_panel.btn_test.setEnabled(True)

    def _resolve_platform_api_url(self, platform_name: str) -> str:
        """优先读取草稿缓存，其次读取 UI 输入框，避免未保存配置导致误判。"""
        draft_url = self.draft.get('platforms', {}).get(platform_name, {}).get('api_url', '').strip()
        if draft_url:
            return draft_url
        return self.settings_panel.api_url_entry.text().strip()

    def _validate_api_params(self, action: str) -> Optional[dict]:
        """校验通用 API 参数（平台、Key、模型、URL）。通过返回参数字典，失败返回 None 并记录日志"""
        platform = self.settings_panel.platform_combo.currentText().strip()
        if not platform:
            self.chat_panel.append_log("Sys", f"{action}：请先选择一个平台。", icon="error")
            return None

        api_key = self.settings_panel.api_key_entry.text().strip()
        if not api_key:
            self.chat_panel.append_log("Sys", f"{action}：请先填写当前平台的 API Key。", icon="error")
            return None

        model = self.settings_panel.model_combo.currentText().strip()
        if not model:
            self.chat_panel.append_log("Sys", f"{action}：请先选择或填写一个模型。", icon="error")
            return None

        api_url = self._resolve_platform_api_url(platform)
        if not api_url:
            self.chat_panel.append_log("Sys", f"{action}：请先填写当前平台的 API URL。", icon="error")
            return None

        return {
            'platform': platform,
            'api_key': api_key,
            'model': model,
            'api_url': api_url,
            'timeout': self.draft.get('api_timeout', 30.0),
            'system_prompt': self.draft.get('system_prompt', ''),
        }

    def _show_image(self, path: Optional[str] = None) -> bool:
        if path is not None:
            self.current_image_path = path
            if self._folder_images and path in self._folder_images:
                self._folder_image_index = self._folder_images.index(path)
                self.preview_panel.set_image_count(self._folder_image_index + 1, len(self._folder_images))
            else:
                self._folder_image_index = -1
                if self._folder_images:
                    self.preview_panel.set_image_count(0, len(self._folder_images))
                else:
                    total = len(self._scan_folder_images())
                    self.preview_panel.set_image_count(0, total)

        if not self.current_image_path:
            return False

        try:
            pixmap = QPixmap(self.current_image_path)

            if pixmap.isNull():
                self.current_image_path = None
                self.preview_panel.image_label.clear()
                self.chat_panel.append_log("Sys", "图片加载失败：图片格式不支持或文件已损坏。", icon="error")
                return False

            self.preview_panel.image_label.set_original_pixmap(pixmap)
            
            if path is not None:
                return self._try_auto_recognize()
            return False
        except Exception:
            self.preview_panel.image_label.clear()
            self.chat_panel.append_log("Sys", "图片加载失败。", icon="error")
            return False

    def _has_running_worker(self) -> bool:
        """判断是否存在正在执行的后台任务。"""
        return any(worker.isRunning() for worker in self._active_workers)

    def _try_auto_recognize(self) -> bool:
        if not self.settings_panel.check_auto_recognize.isChecked():
            return False
        if self.settings_panel.check_continuous.isChecked():
            return False
        if self.settings_panel.check_text_recognition.isChecked():
            return False
        if self.settings_panel.is_running:
            return False
        if not self.current_image_path:
            return False
        self.start_recognition()
        return True

    def _open_original_image(self):
        if self.current_image_path:
            viewer = ImageViewerDialog(self.current_image_path, self)
            viewer.exec()

    def _copy_image(self):
        pixmap = self.preview_panel.image_label.get_original_pixmap()
        if pixmap and not pixmap.isNull():
            QApplication.clipboard().setPixmap(pixmap)

    def _clear_image(self):
        self.current_image_path = None
        self.preview_panel.image_label.clear()
        self.chat_panel.set_status("图片已清除。", "info")

    def _save_image_to_folder(self):
        if not self.current_image_path:
            return
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        src = Path(self.current_image_path)
        dest = IMAGES_DIR / src.name
        if dest.exists():
            stem, suffix = src.stem, src.suffix
            counter = 1
            while dest.exists():
                dest = IMAGES_DIR / f"{stem}_{counter}{suffix}"
                counter += 1
        try:
            shutil.copy2(str(src), str(dest))
            self.chat_panel.append_log("Sys", f"图片已保存至 {dest.name}。", icon="success")
        except Exception as e:
            self.chat_panel.append_log("Sys", f"保存失败：{_ensure_punctuation(str(e))}", icon="error")

    def _on_image_dropped(self, path: str):
        auto_started = self._show_image(path)
        if not auto_started:
            self.chat_panel.set_status("图片已加载。", "success")

    def start_screenshot(self):
        self.showMinimized()
        QTimer.singleShot(SCREENSHOT_MINIMIZE_DELAY_MS, self._do_screenshot)

    def _do_screenshot(self):
        if not self.sc:
            self.sc = ScreenCapture()
        self.sc.start_capture(self._on_screenshot_callback)

    def _on_screenshot_callback(self, path: Optional[str]):
        self.showNormal()
        self.activateWindow()
        if path:
            self._temp_files.add(path)
            auto_started = self._show_image(path)
            if not auto_started:
                self.chat_panel.set_status("图片已加载。", "success")
        else:
            self.chat_panel.append_log("Sys", "截图已取消。", icon="error")

    def paste_image(self, silent=False):
        clipboard = QApplication.clipboard()
        if clipboard.mimeData().hasImage():
            img = clipboard.image()
            if not img.isNull():
                fd, path = tempfile.mkstemp(suffix='.png')
                os.close(fd)
                self._temp_files.add(path)
                img.save(path, "PNG")
                auto_started = self._show_image(path)
                if not auto_started:
                    self.chat_panel.set_status("图片已加载。", "success")
            else:
                if not silent:
                    self.chat_panel.append_log("Sys", "粘贴失败：剪贴板图片无法解析。", icon="error")
        else:
            if not silent:
                self.chat_panel.append_log("Sys", "粘贴失败：剪贴板中没有图片。", icon="error")

    def open_image(self):
        initial_dir = str(IMAGES_DIR) if IMAGES_DIR.exists() else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", initial_dir, "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;所有文件 (*.*)"
        )
        if path:
            auto_started = self._show_image(path)
            if not auto_started:
                self.chat_panel.set_status("图片已加载。", "success")

    def _open_image_folder(self):
        if not IMAGES_DIR.exists():
            IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        abs_path = str(IMAGES_DIR.resolve())
        try:
            if platform.system() == "Windows":
                os.startfile(abs_path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", abs_path], check=True)
            else:
                subprocess.run(["xdg-open", abs_path], check=True)
        except Exception as e:
            self.chat_panel.append_log("Sys", f"打开图片文件夹失败：{_ensure_punctuation(str(e))}", icon="error")

    def _scan_folder_images(self) -> List[str]:
        if not IMAGES_DIR.exists():
            return []
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp'}

        def _safe_mtime(path: str) -> float:
            try:
                return os.path.getmtime(path)
            except OSError:
                return 0.0

        try:
            files = [str(f) for f in IMAGES_DIR.iterdir() if f.suffix.lower() in image_extensions]
        except OSError as e:
            self.chat_panel.append_log("Sys", f"读取图片文件夹失败：{_ensure_punctuation(str(e))}", icon="error")
            return []
        if self.draft.get('image_sort', 'time') == 'name':
            return sorted(files, key=lambda x: os.path.basename(x).lower())
        return sorted(files, key=_safe_mtime)

    def _load_next_folder_image(self):
        if not IMAGES_DIR.exists():
            IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            self.chat_panel.set_status("用户图片文件夹已创建。", "info")
            self.preview_panel.set_image_count(0, 0)
            return
        
        images = self._scan_folder_images()
        
        if not images:
            self.chat_panel.set_status("用户图片文件夹为空。", "info")
            self.preview_panel.set_image_count(0, 0)
            self.preview_panel.set_folder_total(0)
            return
        
        if self._folder_images != images:
            self._folder_images = images
            self._folder_image_index = -1
            self.preview_panel.set_folder_total(len(images))
        
        self._folder_image_index += 1
        if self._folder_image_index >= len(self._folder_images):
            self._folder_image_index = 0
        
        if self._folder_images:
            image_path = self._folder_images[self._folder_image_index]
            auto_started = self._show_image(image_path)
            self.preview_panel.set_image_count(self._folder_image_index + 1, len(self._folder_images))
            if not auto_started:
                self.chat_panel.set_status("图片已加载。", "success")

    def _on_recognize_shortcut(self) -> None:
        """识别快捷键处理：与 UI 按钮等价——忙时中止，闲时开始识别"""
        if self.settings_panel.is_running:
            self.abort_recognition()
        else:
            self.start_recognition()

    def start_recognition(self):
        if self._has_running_worker():
            self.chat_panel.append_log("Sys", "识别失败：已有任务正在执行，请先终止当前任务。", icon="error")
            return

        self._is_text_mode = self.settings_panel.check_text_recognition.isChecked()
        self._is_continuous_mode = self.settings_panel.check_continuous.isChecked()
        
        if self._is_continuous_mode and self._is_text_mode:
            self.chat_panel.append_log("Sys", "识别失败：连续识别与文本识别不能同时启用。", icon="error")
            return

        if not self._is_text_mode and self._is_continuous_mode and not self._continuous_mode_active:
            self._folder_images = self._scan_folder_images()
            if not self._folder_images:
                self.chat_panel.append_log("Sys", "识别失败：用户图片文件夹为空。", icon="error")
                return
            
            if self.current_image_path and self.current_image_path in self._folder_images:
                self._folder_image_index = self._folder_images.index(self.current_image_path)
            else:
                self._folder_image_index = 0
                self.current_image_path = self._folder_images[0]
                self.preview_panel.image_label.set_original_pixmap(QPixmap(self.current_image_path))
            
            self._continuous_mode_active = True
            self.preview_panel.set_image_count(self._folder_image_index + 1, len(self._folder_images))

        if not self._is_text_mode and not self.current_image_path:
            self.chat_panel.append_log("Sys", "识别失败：请先选择或截取一张图片。", icon="error")
            return

        params = self._validate_api_params("识别失败")
        if not params:
            return

        func = self.settings_panel.function_combo.currentText().strip()
        if not func:
            self.chat_panel.append_log("Sys", "识别失败：请先选择一个功能。", icon="error")
            return

        base_prompt = self.settings_panel.prompt_text.toPlainText().strip()
        if not base_prompt:
            self.chat_panel.append_log("Sys", "识别失败：当前功能的提示词为空。", icon="error")
            return

        text_content = self.result_panel.result_text.toPlainText().strip()
        if self._is_text_mode and not text_content:
            self.chat_panel.append_log("Sys", "识别失败：文本识别模式下，识别结果区不能为空。", icon="error")
            return
        
        if not self.draft.get('continuous_chat', False):
            self.api.clear_history()

        model = params['model']
        if self._is_text_mode:
            prompt = f"{base_prompt}\n识别文本：{text_content}。"
            img_path = None
            display_prefix = "{文本}"
            display_content = base_prompt
            status_text = f"正在处理文本 [{model}]..."
        else:
            prompt = base_prompt
            img_path = self.current_image_path
            display_prefix = "{图片}"
            display_content = prompt
            status_text = f"正在识别 [{model}]..."

        self.result_panel.result_text.clear()
        self.set_gui_processing_state(True, 'recognize', status_text)
        self.aborted = False

        self.chat_panel.append_log("Task", f"{display_prefix} {display_content}")
        self.response_started = False
        self.chat_panel.append_log("AI", "", model=model)
        
        config = APIConfig(
            api_key=params['api_key'],
            platform=params['platform'],
            api_url=params['api_url'],
            timeout=params['timeout'],
            model=model,
            system_prompt=params['system_prompt'],
            prompt=prompt,
            img_path=img_path
        )
        self._create_api_worker(config, self._on_recognize_chunk, self._on_recognize_done)

    def abort_recognition(self):
        self.aborted = True
        self._continuous_mode_active = False
        for worker in list(self._active_workers):
            worker.abort()
        self.chat_panel.append_log("Sys", "操作已取消。", icon="error")
        self.set_gui_processing_state(False, 'recognize')

    @staticmethod
    def _append_to_text_edit(text_edit: QTextEdit, text: str) -> None:
        """向 QTextEdit 末尾追加文本并滚动到可见区域"""
        cursor = text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        text_edit.setTextCursor(cursor)
        text_edit.ensureCursorVisible()

    def _on_recognize_chunk(self, chunk: str):
        if self.aborted:
            return

        if not self.response_started:
            chunk = chunk.lstrip('\n\r ')
            if not chunk:
                return
            self.response_started = True
            self._last_rec_char = ""

        filtered_chunk, self._last_rec_char = self._filter_newlines(chunk, self._last_rec_char)

        if not filtered_chunk:
            return

        self._append_to_text_edit(self.result_panel.result_text, filtered_chunk)
        self._append_to_text_edit(self.chat_panel.chat_history, filtered_chunk)

    def _on_recognize_done(self):
        if self.aborted:
            self._continuous_mode_active = False
            return
        
        res = self.result_panel.result_text.toPlainText().strip()
        recognition_success = res and "无法识别" not in res and "无法辨认" not in res

        if recognition_success:
            self.chat_panel.append_log("Sys", "识别成功。", icon="success")
            self.chat_panel.set_status("识别成功。", "success")
            if self.settings_panel.check_auto_copy.isChecked():
                QApplication.clipboard().setText(res)
                self.chat_panel.append_log("Sys", "已自动复制到剪贴板。", icon="success")
        else:
            self.chat_panel.set_status("识别完成。", "info")

        if res:
            self.history.append(res)
            self._check_history_limit()
            self._schedule_history_refresh()

        if self._continuous_mode_active and self._is_continuous_mode:
            if recognition_success:
                QTimer.singleShot(CONTINUOUS_RECOGNIZE_DELAY_MS, self._continue_next_image)
            else:
                self._continuous_mode_active = False
                self.set_gui_processing_state(False, 'recognize')
                self.chat_panel.set_status("连续识别已停止。", "info")
        else:
            self.set_gui_processing_state(False, 'recognize')

    def _continue_next_image(self):
        if self.aborted or not self._continuous_mode_active:
            self._continuous_mode_active = False
            self.set_gui_processing_state(False, 'recognize')
            return

        if self._has_running_worker():
            return

        self._folder_images = self._scan_folder_images()
        if not self._folder_images:
            self._continuous_mode_active = False
            self.set_gui_processing_state(False, 'recognize')
            self.chat_panel.set_status("连续识别已停止：用户图片文件夹为空。", "info")
            return

        next_index = self._folder_image_index + 1
        if next_index >= len(self._folder_images):
            self._continuous_mode_active = False
            self.set_gui_processing_state(False, 'recognize')
            self.chat_panel.set_status("连续识别完成。", "success")
            return
        
        self._folder_image_index = next_index
        image_path = self._folder_images[self._folder_image_index]
        self.current_image_path = image_path
        self.preview_panel.image_label.set_original_pixmap(QPixmap(image_path))
        self.preview_panel.set_image_count(self._folder_image_index + 1, len(self._folder_images))
        
        self.result_panel.result_text.clear()
        self.start_recognition()

    def _on_api_error(self, err_msg: str):
        if not self.aborted:
            self.chat_panel.append_log("Sys", _ensure_punctuation(err_msg), icon="error")
            self.chat_panel.set_status("请求失败。", "error")
        
        if self._continuous_mode_active:
            self._continuous_mode_active = False
            self.chat_panel.append_log("Sys", "连续识别已取消。", icon="error")
        
        self.set_gui_processing_state(False)

    def send_chat(self, msg: str):
        if not msg:
            return

        if self._has_running_worker():
            self.chat_panel.append_log("Sys", "发送失败：已有任务正在执行，请先终止当前任务。", icon="error")
            return

        params = self._validate_api_params("发送失败")
        if not params:
            return

        self.chat_panel.entry.clear()
        model = params['model']

        img_path = self.current_image_path if self.chat_panel.check_attach_image.isChecked() else None
        display_msg = f"{{图片}} {msg}" if img_path else msg
        self.chat_panel.append_log("User", display_msg)

        self.set_gui_processing_state(True, 'chat', f"正在对话 [{model}]...")
        self.aborted = False

        self.response_started = False
        self.chat_panel.append_log("AI", "", model=model)
        
        config = APIConfig(
            api_key=params['api_key'],
            platform=params['platform'],
            api_url=params['api_url'],
            timeout=params['timeout'],
            model=model,
            system_prompt=params['system_prompt'],
            prompt=msg,
            img_path=img_path
        )
        self._create_api_worker(config, self._on_chat_chunk, self._on_chat_done)

    def abort_chat(self):
        self.aborted = True
        for worker in list(self._active_workers):
            worker.abort()
        self.chat_panel.append_log("Sys", "会话已取消。", icon="error")
        self.set_gui_processing_state(False, 'chat')

    def _on_chat_chunk(self, chunk: str):
        if self.aborted:
            return

        if not self.response_started:
            chunk = chunk.lstrip('\n\r ')
            if not chunk:
                return
            self.response_started = True
            self._last_chat_char = ""

        filtered_chunk, self._last_chat_char = self._filter_newlines(chunk, self._last_chat_char)

        if not filtered_chunk:
            return

        self._append_to_text_edit(self.chat_panel.chat_history, filtered_chunk)

    def _on_chat_done(self):
        if self.aborted:
            return
        self.chat_panel.set_status("对话完成。", "info")
        self.set_gui_processing_state(False, 'chat')

    def _on_chat_clear(self):
        self.chat_panel.set_status("消息已清空。", "info")

    def _cleanup_worker(self):
        worker = self.sender()
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        if worker is self.api_worker:
            self.api_worker = None
        if worker:
            worker.deleteLater()

    def _filter_newlines(self, chunk: str, last_char: str) -> tuple[str, str]:
        filtered = []
        prev_char = last_char
        for char in chunk:
            if not (char == '\n' and prev_char == '\n'):
                filtered.append(char)
            prev_char = char
        return "".join(filtered), prev_char

    def copy_result(self):
        txt = self.result_panel.result_text.toPlainText().strip()
        self._copy_to_clip(txt)

    def _copy_to_clip(self, txt: str):
        if not txt:
            return
        QApplication.clipboard().setText(txt)

    def render_result(self):
        txt = self.result_panel.result_text.toPlainText().strip()
        if txt:
            try:
                path = FormulaRenderer.render(txt)
                if path:
                    self._temp_files.add(path)
                else:
                    self.chat_panel.append_log("Sys", "预览失败：识别结果为空。", icon="error")
            except Exception as e:
                err_str = str(e)
                self.chat_panel.append_log("Sys", f"预览失败：{_ensure_punctuation(err_str)}", icon="error")
        else:
            self.chat_panel.append_log("Sys", "预览失败：识别结果为空。", icon="error")

    def clear_history(self):
        self.history.clear()
        self.history_panel.refresh_history(self.history)

    def delete_history_item(self, index: int):
        if 0 <= index < len(self.history):
            self.history.pop(index)
            self.history_panel.refresh_history(self.history)

    def load_history_item(self, txt: str):
        self.result_panel.result_text.setText(txt)

    def save_text_to_history(self, txt: str):
        if not txt.strip():
            self.chat_panel.append_log("Sys", "记录失败：识别结果为空。", icon="error")
            self.chat_panel.set_status("记录失败：识别结果为空。", "error")
            return
        self.history.append(txt)
        self._check_history_limit()
        self._schedule_history_refresh()

    def _on_append_to_result(self, text: str):
        """将运行日志中选中的文本写入识别结果区（先清空），并存入历史记录"""
        self.result_panel.result_text.setPlainText(text)
        self.save_text_to_history(text)

    def _export_history(self):
        """将当前历史记录直接导出为带时间戳的 JSON 文件"""
        if not self.history:
            self.chat_panel.append_log("Sys", "导出失败：历史记录为空。", icon="error")
            return
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%m%d_%H%M%S")
        path = HISTORY_DIR / f"pecktex_history_{timestamp}.json"
        try:
            data = {
                "version": 1.0,
                "exported_at": datetime.datetime.now().isoformat(),
                "history": self.history
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.chat_panel.append_log("Sys", f"已导出 {len(self.history)} 条历史记录至 {path.name}。", icon="success")
        except Exception as e:
            self.chat_panel.append_log("Sys", f"导出失败：{_ensure_punctuation(str(e))}", icon="error")

    def _import_history(self):
        """从 JSON 文件导入历史记录，覆盖当前记录"""
        initial_dir = str(HISTORY_DIR) if HISTORY_DIR.exists() else str(USER_DATA_ROOT)
        path, _ = QFileDialog.getOpenFileName(
            self, "导入历史记录",
            initial_dir,
            "历史记录文件 (*.json);;所有文件 (*.*)"
        )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict) or not isinstance(data.get('history'), list):
                raise ValueError("文件格式不正确，缺少有效的 history 字段。")
            items = [str(item) for item in data['history'] if str(item).strip()]
            self.history = items
            self._check_history_limit()
            self._schedule_history_refresh()
            self.chat_panel.append_log("Sys", f"已导入 {len(items)} 条历史记录。", icon="success")
        except json.JSONDecodeError:
            self.chat_panel.append_log("Sys", "导入失败：文件不是有效的 JSON 格式。", icon="error")
        except ValueError as e:
            self.chat_panel.append_log("Sys", f"导入失败：{_ensure_punctuation(str(e))}", icon="error")
        except Exception as e:
            self.chat_panel.append_log("Sys", f"导入失败：{_ensure_punctuation(str(e))}", icon="error")

    def reset_chat(self):
        if self._active_workers:
            self.aborted = True
            for worker in list(self._active_workers):
                if hasattr(worker, 'abort'):
                    worker.abort()
            self.set_gui_processing_state(False)
        self.api.clear_history()
        self.chat_panel.append_log("Sys", "对话已重置。", icon="success")

    def test_service(self):
        if self._has_running_worker():
            self.chat_panel.append_log("Sys", "测试失败：已有任务正在执行，请先终止当前任务。", icon="error")
            return

        params = self._validate_api_params("测试失败")
        if not params:
            return

        plat_name, model = params['platform'], params['model']
        self.chat_panel.append_log("Sys", f"正在测试服务 [{plat_name} / {model}]...", icon="loading")
        self.set_gui_processing_state(True, 'test', f"正在测试 [{model}]...")

        test_worker = TestWorker(
            params['api_key'], plat_name, params['api_url'],
            params['timeout'], model, parent=self
        )
        self._active_workers.add(test_worker)
        test_worker.finished.connect(self._cleanup_worker)
        test_worker.finished.connect(lambda: self.set_gui_processing_state(False, 'test'))
        test_worker.success_signal.connect(self._on_test_success)
        test_worker.error_signal.connect(self._on_test_error)
        test_worker.start()

    def _on_test_success(self, resp: str) -> None:
        self.chat_panel.append_log("Sys", f"服务正常。模型响应：{_ensure_punctuation(resp)}", icon="success")
        self.chat_panel.set_status("服务测试成功。", "success")

    def _on_test_error(self, err: str) -> None:
        self.chat_panel.append_log("Sys", f"服务测试失败：{_ensure_punctuation(err)}", icon="error")
        self.chat_panel.set_status("服务测试失败。", "error")
