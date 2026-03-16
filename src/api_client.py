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
大语言模型通信模块
负责提供与兼容 OpenAI 格式的 API 接口进行交互的核心客户端，
处理底层的网络请求和错误封装，同时管理 HTTP keep-alive 短会话状态。
"""

import base64
import mimetypes
import threading
from typing import List, Dict, Any, Optional, Generator, NoReturn

import httpx
from openai import OpenAI
from openai import APITimeoutError, APIConnectionError, APIStatusError


class APIError(Exception):
    """自定义 API 异常类，用于同 UI 层隔离网络错误"""
    pass


class FormulaAPIClient:
    """
    大语言模型通信客户端。
    负责请求的封装、历史上下文的管理。
    """
    # GLM 等模型经常携带的特殊标记，在流式输出中平滑滤除
    _BLOCK_LIST = ["\n<|begin_of_box|>", "<|end_of_box|>", "<|box_start|>", "<|box_end|>"]

    def __init__(self):
        self._api_key: str = ""
        self._api_url: str = ""
        self._timeout_val: float = 30.0
        self.conversation_history: List[Dict[str, Any]] = []
        self._cached_client: Optional[OpenAI] = None
        self._cached_client_key: str = ""
        self._client_lock = threading.RLock()

    def set_credentials(self, api_key: str, api_url: str, timeout_val: float) -> None:
        """更新底层的鉴权信息与请求地址。"""
        self._api_key = api_key
        self._api_url = api_url
        self._timeout_val = timeout_val

    @staticmethod
    def encode_image(image_path: str) -> str:
        """读取图片并可靠地转换为 Base64。若无图片则抛出有意义的异常"""
        if not image_path:
            raise ValueError("图片路径不能为空。")
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except FileNotFoundError:
            raise ValueError(f"找不到图片文件：{image_path}")
        except OSError as e:
            raise ValueError(f"读取图片失败: {str(e)}")

    def _get_client(self) -> OpenAI:
        """实例化并返回标准的 OpenAI SDK client，带默认超时管控。复用实例以利用底层连接池加速"""
        if not self._api_key:
            raise APIError("未提供 API Key，请先在配置中填写。")

        with self._client_lock:
            cache_key = f"{self._api_key}:{self._api_url}:{self._timeout_val}"
            if self._cached_client and self._cached_client_key == cache_key:
                return self._cached_client

            # 连接超时短，读取超时长（等待视觉模型处理图片后的首个 token）
            structured_timeout = httpx.Timeout(self._timeout_val, connect=5.0)
            self._cached_client = OpenAI(
                api_key=self._api_key,
                base_url=self._api_url if self._api_url else None,
                timeout=structured_timeout,
                max_retries=0
            )
            self._cached_client_key = cache_key
            return self._cached_client

    def _raise_api_error(self, e: Exception) -> NoReturn:
        """将底层异常统一转换为 APIError，供 UI 层展示"""
        if isinstance(e, APIError):
            raise
        if isinstance(e, APITimeoutError):
            raise APIError(
                f"请求超时（已等待 {self._timeout_val:.0f} 秒）：模型处理时间过长，"
                f"可尝试：1. 检查网络连接；2. 更换模型或平台；3. 稍后重试。"
            )
        if isinstance(e, APIConnectionError):
            raise APIError(f"连接服务器失败：请检查 API URL 是否正确以及网络是否可用。（{e.__class__.__name__}）")
        if isinstance(e, APIStatusError):
            raise APIError(f"服务器返回错误 HTTP {e.status_code}：{e.message}")
        raise APIError(str(e) or repr(e))

    _ALLOWED_MIMES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})

    def _build_messages(
        self, system_prompt: str, user_content: Any
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """构建完整消息列表和用于发送的用户消息体"""
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]
        if self.conversation_history:
            messages.extend(self.conversation_history)
        user_message: Dict[str, Any] = {"role": "user", "content": user_content}
        messages.append(user_message)
        return messages, user_message

    def chat_with_image(
        self,
        image_path: str,
        prompt: str,
        model: str,
        system_prompt: str
    ) -> Generator[str, None, None]:
        base64_image = self.encode_image(image_path)
        detected_mime, _ = mimetypes.guess_type(image_path)
        mime_type = detected_mime if detected_mime in self._ALLOWED_MIMES else "image/png"

        user_content: List[Dict[str, Any]] = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
        ]
        messages, _ = self._build_messages(system_prompt, user_content)
        # 历史记录中剥离 Base64，仅保留文本占位
        history_message: Dict[str, Any] = {
            "role": "user",
            "content": f"{prompt}\n[图片已上传]"
        }
        return self._send_request(messages, model, history_message)

    def chat_text(
        self,
        prompt: str,
        model: str,
        system_prompt: str
    ) -> Generator[str, None, None]:
        messages, user_message = self._build_messages(system_prompt, prompt)
        return self._send_request(messages, model, user_message)

    def _send_request(self, messages: List[Dict[str, Any]], model: str, user_message_to_save: Dict[str, Any]) -> Generator[str, None, None]:
        if not model:
            raise APIError("未选择模型，请先选择要使用的识别大模型。")
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
                stream=True
            )
            
            full_content_parts: List[str] = []
            buffer = ""
            
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    delta_content = chunk.choices[0].delta.content
                    buffer += delta_content
                    
                    for b in self._BLOCK_LIST:
                        buffer = buffer.replace(b, "")
                        
                    # 防止由于截断恰好把形如 "<|beg" 留在 buffer 末尾而导致被输出
                    safe_index = len(buffer)
                    for b in self._BLOCK_LIST:
                        for i in range(1, len(b)):
                            prefix = b[:i]
                            if buffer.endswith(prefix):
                                safe_index = min(safe_index, len(buffer) - i)
                                
                    safe_chunk = buffer[:safe_index]
                    buffer = buffer[safe_index:]
                    
                    if safe_chunk:
                        full_content_parts.append(safe_chunk)
                        yield safe_chunk
            
            if buffer:
                full_content_parts.append(buffer)
                yield buffer
            
            full_content = "".join(full_content_parts)
            if not full_content:
                raise APIError("模型未返回任何内容，连接可能被服务端断开或异常超时。")
                
            self.conversation_history.append(user_message_to_save)
            self.conversation_history.append({
                "role": "assistant", 
                "content": full_content
            })
        except Exception as e:
            self._raise_api_error(e)

    def test_connection(self, model: str) -> str:
        """
        发送一条最小化测试消息，验证 API 配置的连通性与基础响应能力。
        使用非流式同步调用，结果不写入对话历史记录。
        """
        if not model:
            raise APIError("未选择模型，请先选择要使用的识别大模型。")
        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": "Reply with exactly the word: OK"}
        ]
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=10,
                stream=False
            )
            content = response.choices[0].message.content.strip() if response.choices else ""
            return content or "（空响应）"
        except Exception as e:
            self._raise_api_error(e)

    def interrupt(self) -> None:
        """关闭当前的 HTTP 客户端以强行打断可能阻塞的网络请求，并清除缓存以便下一次请求重建"""
        with self._client_lock:
            if self._cached_client:
                try:
                    self._cached_client.close()
                except Exception:
                    pass
                self._cached_client = None
                self._cached_client_key = ""

    def clear_history(self) -> None:
        """清除对话历史记录，重置上下文"""
        self.conversation_history.clear()
