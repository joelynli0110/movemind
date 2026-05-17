"""
General-purpose machine translation layer.

This intentionally does not use the coach LLM. The default configured provider
is LibreTranslate, an open-source machine translation service. If translation
is not configured or fails, callers should fall back to the original English
payload.
"""
from __future__ import annotations

import asyncio
import copy
import os
import re
from typing import Any

import httpx

_PROVIDER = os.getenv("TRANSLATION_PROVIDER", "none").lower()
_LIBRETRANSLATE_API_URL = os.getenv(
    "LIBRETRANSLATE_API_URL",
    "http://127.0.0.1:5000/translate",
).strip()
_LIBRETRANSLATE_API_KEY = os.getenv("LIBRETRANSLATE_API_KEY", "").strip()
_LIBRETRANSLATE_CONCURRENCY = int(os.getenv("LIBRETRANSLATE_CONCURRENCY", "4"))
_TIMEOUT_S = float(os.getenv("TRANSLATION_TIMEOUT_SECONDS", "30"))

_SAN_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?:O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)"
    r"(?![A-Za-z0-9_])"
)


class TranslationError(RuntimeError):
    pass


async def translate_json_values(payload: Any, target_language: str) -> Any:
    if target_language != "zh" or _PROVIDER in ("", "none", "off", "disabled"):
        return payload
    if _PROVIDER in ("libretranslate", "libretranslator"):
        return await _translate_json_values_libretranslate(payload, target_lang="zh")
    raise TranslationError(f"Unsupported TRANSLATION_PROVIDER={_PROVIDER!r}")


async def _translate_json_values_libretranslate(payload: Any, target_lang: str) -> Any:
    paths: list[tuple[Any, ...]] = []
    texts: list[str] = []
    _collect_strings(payload, (), paths, texts)
    if not texts:
        return payload

    protected_pairs = [_protect_chess_notation(text) for text in texts]
    protected_texts = [text for text, _ in protected_pairs]
    async with httpx.AsyncClient(timeout=httpx.Timeout(_TIMEOUT_S, connect=10.0)) as client:
        translated = await _libretranslate_texts(client, protected_texts, target_lang)

    restored = [
        _restore_chess_notation(text, replacements)
        for text, (_, replacements) in zip(translated, protected_pairs)
    ]
    result = copy.deepcopy(payload)
    for path, value in zip(paths, restored):
        _set_path(result, path, value)
    return result


def _collect_strings(node: Any, path: tuple[Any, ...], paths: list[tuple[Any, ...]], texts: list[str]) -> None:
    if isinstance(node, str):
        paths.append(path)
        texts.append(node)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _collect_strings(item, (*path, index), paths, texts)
    elif isinstance(node, dict):
        for key, value in node.items():
            _collect_strings(value, (*path, key), paths, texts)


async def _libretranslate_texts(
    client: httpx.AsyncClient,
    texts: list[str],
    target_lang: str,
) -> list[str]:
    semaphore = asyncio.Semaphore(max(1, _LIBRETRANSLATE_CONCURRENCY))

    async def translate_one(text: str) -> str:
        payload = {
            "q": text,
            "source": "en",
            "target": target_lang,
            "format": "text",
        }
        if _LIBRETRANSLATE_API_KEY:
            payload["api_key"] = _LIBRETRANSLATE_API_KEY

        async with semaphore:
            resp = await client.post(_LIBRETRANSLATE_API_URL, json=payload)
            resp.raise_for_status()
            body = resp.json()

        translated = body.get("translatedText")
        if not isinstance(translated, str):
            raise TranslationError("LibreTranslate returned an unexpected response")
        return translated

    return await asyncio.gather(*(translate_one(text) for text in texts))


def _protect_chess_notation(text: str) -> tuple[str, list[str]]:
    replacements: list[str] = []

    def replace(match: re.Match[str]) -> str:
        replacements.append(match.group(0))
        return f"__MMCHESS{len(replacements) - 1}__"

    protected = _SAN_RE.sub(replace, text)
    return protected, replacements


def _restore_chess_notation(text: str, replacements: list[str]) -> str:
    for index, original in enumerate(replacements):
        text = text.replace(f"__MMCHESS{index}__", original)
    return text


def _set_path(root: Any, path: tuple[Any, ...], value: str) -> None:
    cursor = root
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = value
