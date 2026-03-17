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
配置管理模块
负责加载、保存和管理 config.json 用户配置文件，支持出厂默认配置，并自动补全缺失字段。
"""

import sys
import json
import os
import copy
from pathlib import Path
from typing import Dict, Any, List, Optional


# 区分内置资源目录与用户数据目录，适配 PyInstaller 打包
if getattr(sys, 'frozen', False):
    RESOURCE_ROOT = Path(sys._MEIPASS)
    USER_DATA_ROOT = Path(sys.executable).parent
else:
    RESOURCE_ROOT = Path(__file__).resolve().parent.parent
    USER_DATA_ROOT = RESOURCE_ROOT

# 用户数据目录
USER_DATA_DIR = USER_DATA_ROOT / "userdata"
IMAGES_DIR = USER_DATA_DIR / "images"
HISTORY_DIR = USER_DATA_DIR / "history"
TEMP_DIR = USER_DATA_DIR / "temp"

# 配置文件路径
CONFIG_DIR = USER_DATA_DIR / "config"
CONFIG_FILE_NAME = "config.json"

# 资源目录(只读)
ASSETS_DIR = RESOURCE_ROOT / "assets"
ICONS_DIR = ASSETS_DIR / "icons"

# 确保目录存在
for d in [IMAGES_DIR, HISTORY_DIR, TEMP_DIR, CONFIG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "auto_recognize": True,
    "auto_copy": True,
    "continuous_recognition": False,
    "text_recognition": False,
    "continuous_chat": False,
    "language": "",
    "theme": "",
    "image_sort": "time",
    "api_timeout": 30.0,
    "max_history": 100,
    "max_log": 100,
    "shortcuts": {
        "screenshot": "Alt+S",
        "paste": "Ctrl+V",
        "recognize": "Alt+Return"
    },
    "default": {
        "platform": "",
        "model": "",
        "function": ""
    },
    "platforms": {
        "siliconflow": {
            "api_url": "https://api.siliconflow.cn/v1",
            "api_key": "",
            "models": [
                "Qwen/Qwen3-VL-235B-A22B-Instruct",
                "zai-org/GLM-4.6V"
            ]
        },
        "openrouter": {
            "api_url": "https://openrouter.ai/api/v1",
            "api_key": "",
            "models": [
                "qwen/qwen3-vl-32b-instruct",
                "openai/gpt-5-nano"
            ]
        },
        "modelscope": {
            "api_url": "https://api-inference.modelscope.cn/v1",
            "api_key": "",
            "models": [
                "MiniMax/MiniMax-M2.5"
            ]
        }
    },
    "system_prompt": "请记住：你是一个专业的公式排版专家，同时也是“啄玛(PeckTeX)”这款图片转公式软件的AI助手，擅长生成准确规范的LaTeX或MathML等格式的代码。你的输出力求精简，绝不废话，输出内容不要包含Markdown语法。",
    "functions": {
        "公式识别 LaTeX": "精准识别图中的数学公式或符号。仅输出纯LaTeX代码，必须以$$或\\[...\\]包裹，禁止任何解释，禁止使用 Markdown 代码块。若无法识别，返回'无法识别'。",
        "公式识别 MathML": "精准识别图中的数学公式或符号，并将其转换为标准的 MathML 格式。仅输出以 <math> 开头并以 </math> 结尾的纯 XML 代码，禁止任何解释，禁止混入 LaTeX 代码，禁止使用 Markdown 代码块。若无法识别，返回'无法识别'。",
        "手写识别 LaTeX": "精准识别图中的手写数学公式或符号，忽略涂抹。仅输出纯LaTeX代码，必须以$$或\\[...\\]包裹，禁止任何解释，禁止使用 Markdown 代码块。若无法识别，返回'无法识别'。",
        "化学公式 LaTeX": "精准识别图中的化学符号或化学方程式。仅输出纯LaTeX代码，优先使用mhchem的\\ce{}宏包格式，必须用$$包裹，禁止任何解释，禁止使用 Markdown 代码块。若无法识别，返回'无法识别'。",
        "通用识别 LaTeX": "提取图中一切可被LaTeX表达的内容(数学结构、公式、符号、化学式、表格、图形等)。仅输出纯LaTeX代码，独立块用$$包裹，禁止任何解释，禁止使用 Markdown 代码块。若无法识别，返回'无法识别'。"
    }
}


class SettingsManager:
    """
    配置与数据层管理器
    负责读写配置文件，处理损坏文件回退，分离各种硬编码行为
    """
    def __init__(self, settings_file: str = str(CONFIG_DIR / CONFIG_FILE_NAME)):
        self.settings_file = settings_file
        self.settings_data: Dict[str, Any] = self._get_default_settings()
        self.last_error: Optional[str] = None
        self.load()

    def _get_default_settings(self) -> Dict[str, Any]:
        """获取系统出厂默认配置，全部从 DEFAULT_CONFIG 读取"""
        return copy.deepcopy(DEFAULT_CONFIG)

    def load(self) -> None:
        """从 JSON 加载用户配置。文件不存在或损坏时使用完整默认配置；正常加载仅补全必填键"""
        config_dir = os.path.dirname(self.settings_file)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("配置文件格式不正确")
            self.settings_data = data
            self._ensure_required_keys()
            self.last_error = None
        except FileNotFoundError:
            self.settings_data = self._get_default_settings()
            self.last_error = "已自动生成默认配置文件。"
        except Exception:
            self.settings_data = self._get_default_settings()
            self.last_error = "读取配置文件时发生错误。已重置为默认配置。"
        finally:
            self._validate_defaults()
            self.save()

    @staticmethod
    def _coerce_float_in_range(value: Any, default: float, min_val: float, max_val: float) -> float:
        """将输入值收敛为指定区间内的浮点数，失败时回退默认值。"""
        try:
            parsed = float(value) if value not in (None, "") else default
        except (ValueError, TypeError):
            return default
        return parsed if min_val <= parsed <= max_val else default

    @staticmethod
    def _coerce_int_in_range(value: Any, default: int, min_val: int, max_val: int) -> int:
        """将输入值收敛为指定区间内的整数，失败时回退默认值。"""
        try:
            parsed = int(value)
        except (ValueError, TypeError):
            return default
        return parsed if min_val <= parsed <= max_val else default

    def _validate_defaults(self) -> None:
        """校验配置数据(api_timeout, default)，若不合法则自动回退"""
        # --- 校验 api_timeout，若超出数值范围或非法，则回退为默认值---
        default_timeout = DEFAULT_CONFIG["api_timeout"]
        timeout_val = self._coerce_float_in_range(
            self.settings_data.get("api_timeout"),
            default_timeout,
            0.1,
            300.0,
        )
        self.settings_data["api_timeout"] = timeout_val
        # --- 校验 image_sort，仅接受 'time' 和 'name' ---
        if self.settings_data.get("image_sort") not in {"time", "name"}:
            self.settings_data["image_sort"] = DEFAULT_CONFIG["image_sort"]
        # --- 校验 max_history / max_log，并限制在允许范围内 ---
        limits = {
            "max_history": (10, 1000),
            "max_log": (10, 1000),
        }
        for key, (min_val, max_val) in limits.items():
            self.settings_data[key] = self._coerce_int_in_range(
                self.settings_data.get(key, DEFAULT_CONFIG[key]),
                DEFAULT_CONFIG[key],
                min_val,
                max_val,
            )
        # --- 校验 default，若为空或不合法则回退为其可用列表的第一个有效值 ---
        default_cfg = self.settings_data.get("default", {})
        # 校验与生成 default:platform
        platforms = self.get_platforms()
        curr_plat = default_cfg.get("platform")
        if not curr_plat or curr_plat not in platforms:
            curr_plat = platforms[0] if platforms else ""
            default_cfg["platform"] = curr_plat
        # 校验与生成 default:model
        if curr_plat:
            models = self.get_models(curr_plat)
            curr_model = default_cfg.get("model")
            if not curr_model or curr_model not in models:
                default_cfg["model"] = models[0] if models else ""
        else:
            default_cfg["model"] = ""
        # 校验与生成 default:function
        functions = self.get_functions()
        curr_func = default_cfg.get("function")
        if not curr_func or curr_func not in functions:
            default_cfg["function"] = functions[0] if functions else ""
        # 写回清洗后的数据
        self.settings_data["default"] = default_cfg

    # 仅需自动补全的结构性必填键（不含 platforms/functions 等用户自定义内容）
    _REQUIRED_SCALAR_KEYS = frozenset({
        "continuous_recognition", "continuous_chat", "text_recognition",
        "auto_recognize", "auto_copy", "api_timeout", "image_sort",
        "max_history", "max_log", "theme", "language", "system_prompt",
    })

    def _ensure_required_keys(self) -> None:
        """补全用户配置中缺失的必填键与容器键，不注入默认的 platforms/functions 等用户内容"""
        defaults = DEFAULT_CONFIG
        if not isinstance(self.settings_data, dict):
            self.settings_data = {}
        for key in self._REQUIRED_SCALAR_KEYS:
            if key not in self.settings_data:
                self.settings_data[key] = copy.deepcopy(defaults[key])
        # shortcuts: 确保整体存在，并补全缺失的子项
        if not isinstance(self.settings_data.get("shortcuts"), dict):
            self.settings_data["shortcuts"] = copy.deepcopy(defaults["shortcuts"])
        else:
            for sk, sv in defaults["shortcuts"].items():
                self.settings_data["shortcuts"].setdefault(sk, sv)
        # default: 确保整体存在，并补全缺失的子键
        if not isinstance(self.settings_data.get("default"), dict):
            self.settings_data["default"] = {"platform": "", "model": "", "function": ""}
        else:
            self.settings_data["default"].setdefault("platform", "")
            self.settings_data["default"].setdefault("model", "")
            self.settings_data["default"].setdefault("function", "")
        # 确保用户容器键存在（空结构即可，不注入默认内容）
        if not isinstance(self.settings_data.get("platforms"), dict):
            self.settings_data["platforms"] = {}
        if not isinstance(self.settings_data.get("functions"), dict):
            self.settings_data["functions"] = {}

    def save(self) -> bool:
        """将当前配置 settings_data 保存到 JSON 文件"""
        try:
            config_dir = os.path.dirname(self.settings_file)
            if config_dir:
                os.makedirs(config_dir, exist_ok=True)
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings_data, f, ensure_ascii=False, indent=4)
            self.last_error = None
            return True
        except Exception:
            self.last_error = "保存配置失败。"
            return False

    def reset_to_defaults(self) -> bool:
        """重置所有配置为系统出厂默认值并保存"""
        self.settings_data = self._get_default_settings()
        self._validate_defaults()
        return self.save()

    def validate_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """校验并清理外部配置数据，返回可用的深拷贝。不影响当前 settings_data"""
        if not isinstance(data, dict):
            raise ValueError("配置数据必须是字典类型。")
        backup = self.settings_data
        self.settings_data = copy.deepcopy(data)
        try:
            self._ensure_required_keys()
            self._validate_defaults()
            return copy.deepcopy(self.settings_data)
        finally:
            self.settings_data = backup

    # ------ 以下为 settings_data set 写操作相关 ------

    def set_value(self, section: str, key: str, value: Any) -> None:
        """设置 settings_data 某节的子键值"""
        if section not in self.settings_data:
            self.settings_data[section] = {}
        if isinstance(self.settings_data[section], dict):
            self.settings_data[section][key] = value

    def set_default(self, key: str, value: Any) -> None:
        """修改可选类型配置的窗口默认配置，如最后一次保存的平台、模型、功能"""
        self.set_value('default', key, value)

    def set_platform(self, platform_id: str, api_key: Optional[str] = None, models: Optional[List[str]] = None, api_url: Optional[str] = None) -> None:
        """修改或新建指定平台的配置信息，包括 platform_id、api_key、models、api_url"""
        platforms = self.get('platforms', default={})
        if platform_id not in platforms:
            platforms[platform_id] = {"api_key": "", "api_url": "", "models": []}
        if api_key is not None:
            platforms[platform_id]["api_key"] = api_key
        if api_url is not None:
            platforms[platform_id]["api_url"] = api_url
        if models is not None:
            platforms[platform_id]["models"] = models
        self.settings_data['platforms'] = platforms

    def set_function_prompt(self, func: str, prompt: str) -> None:
        """修改指定功能的提示词"""
        self.set_value('functions', func, prompt)

    # ------ 以下为 settings_data get 读操作相关 ------

    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        """获取 settings_data 配置值。传入 section 获取顶层键值；传入 section + key 获取嵌套键值"""
        try:
            if key is None:
                return self.settings_data.get(section, default)
            return self.settings_data.get(section, {}).get(key, default)
        except (KeyError, AttributeError):
            return default

    def get_current_platform(self) -> str:
        """获取当前配置窗口默认选中的平台（Platform）"""
        return self.get('default', 'platform', '')

    def get_current_model(self) -> str:
        """获取当前配置窗口默认选中的模型（Model）"""
        return self.get('default', 'model', '')

    def get_current_function(self) -> str:
        """获取当前配置窗口默认选中的功能（Function）"""
        return self.get('default', 'function', '')

    def get_shortcut(self, key: str) -> str:
        """获取指定快捷键配置"""
        return self.get('shortcuts', key, '')

    def get_platforms(self) -> List[str]:
        """获取所有已配置的平台名称列表"""
        return list(self.get('platforms', default={}).keys())

    def get_api_key(self, platform: str) -> str:
        """获取指定平台的 API Key"""
        return self.get('platforms', platform, {}).get('api_key', '')

    def get_api_url(self, platform: str) -> str:
        """获取指定平台的 API URL"""
        return self.get('platforms', platform, {}).get('api_url', '')

    def get_models(self, platform: str) -> List[str]:
        """获取指定平台下的模型列表"""
        return self.get('platforms', platform, {}).get('models', [])

    def get_functions(self) -> List[str]:
        """获取所有已配置的功能名称列表"""
        return list(self.get('functions', default={}).keys())

    def get_prompt(self, func: str) -> str:
        """获取指定功能的提示词"""
        return self.get('functions', func, '')

    def get_system_prompt(self) -> str:
        """获取全局系统提示词"""
        return self.get('system_prompt', default='')

    def get_api_timeout(self) -> float:
        """获取 API 请求超时时间（秒）"""
        return self.get('api_timeout', default=30.0)


