"""版本字符串比较工具"""
from __future__ import annotations


def version_tuple(version: str) -> tuple[int, ...]:
    """把 '1.2.3-beta.1' 之类的版本字符串解析成可比较的元组。

    预发布/构建后缀被忽略（'1.2.3-rc.1' 等同 '1.2.3'），
    不足三段的补 0（'2.0' → (2, 0, 0)）。
    """
    parts: list[int] = []
    for seg in str(version).strip().split("."):
        if seg.isdigit():
            parts.append(int(seg))
            continue
        # 混合段（如 "3-beta"）：取数字前缀，其后均为预发布部分，忽略
        digits = ""
        for ch in seg:
            if not ch.isdigit():
                break
            digits += ch
        if digits:
            parts.append(int(digits))
        break
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)
