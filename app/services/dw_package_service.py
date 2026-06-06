"""
.dw 插件包格式服务

.dw 文件本质是一个 zip 压缩包，内部结构为：

    plugin.json        # 必须在根目录，包含插件元数据
    __init__.py        # 必须在根目录，插件入口
    *.py / assets/ / ... # 插件的其他文件和资源

文件格式规范：
    - 文件扩展名 .dw
    - 魔数 (Magic Bytes): 无特殊要求，使用标准 zip 格式
    - plugin.json 中必须包含 id 和 name 字段
"""
from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from loguru import logger

from app.constants import PLUGINS_DIR

# .dw 文件包内必须包含的文件
_REQUIRED_FILES = {"plugin.json", "__init__.py"}


def _read_plugin_meta_from_json(json_data: dict[str, Any]) -> dict[str, str]:
    """从 plugin.json 中提取关键元数据字段"""
    return {
        "id": json_data.get("id", ""),
        "name": json_data.get("name", ""),
        "version": json_data.get("version", "1.0.0"),
        "author": json_data.get("author", ""),
        "description": json_data.get("description", ""),
        "permissions": json_data.get("permissions", []),
        "dependencies": json_data.get("dependencies", []),
        "tags": json_data.get("tags", []),
    }


def read_dw_meta(dw_path: str | Path) -> dict[str, Any] | None:
    """
    读取 .dw 文件中的 plugin.json 元数据，不解压。

    Parameters
    ----------
    dw_path : str | Path
        .dw 文件路径

    Returns
    -------
    dict | None
        plugin.json 的内容字典，读取失败返回 None
    """
    dw_path = Path(dw_path)
    if not dw_path.exists() or dw_path.suffix.lower() != ".dw":
        return None

    try:
        with zipfile.ZipFile(dw_path, "r") as zf:
            # 检查 plugin.json 是否存在
            if "plugin.json" not in zf.namelist():
                logger.warning(".dw 包中缺少 plugin.json: {}", dw_path.name)
                return None

            with zf.open("plugin.json") as f:
                data = json.loads(f.read().decode("utf-8"))
                meta = _read_plugin_meta_from_json(data)

                # 验证必填字段
                if not meta["id"] or not meta["name"]:
                    logger.warning(".dw 包 plugin.json 缺少 id 或 name: {}", dw_path.name)
                    return None

                return data
    except zipfile.BadZipFile:
        logger.warning(".dw 文件格式无效（不是有效的 zip 包）: {}", dw_path.name)
        return None
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning(".dw 包 plugin.json 解析失败: {}, 错误: {}", dw_path.name, e)
        return None
    except Exception as e:
        logger.exception("读取 .dw 元数据失败: {}", dw_path.name)
        return None


def install_dw(dw_path: str | Path) -> tuple[bool, str]:
    """
    将 .dw 文件安装到插件目录。

    Parameters
    ----------
    dw_path : str | Path
        .dw 文件路径

    Returns
    -------
    tuple[bool, str]
        (成功与否, 消息)
    """
    dw_path = Path(dw_path)
    if not dw_path.exists() or dw_path.suffix.lower() != ".dw":
        return False, "无效的 .dw 文件"

    # 读取元数据以获取插件 ID
    meta_data = read_dw_meta(dw_path)
    if meta_data is None:
        return False, "无法读取插件元数据，请检查 .dw 文件"

    plugin_id = meta_data.get("id", "")
    plugin_name = meta_data.get("name", "unknown")

    if not plugin_id:
        return False, "plugin.json 中缺少 id 字段"

    # 目标目录
    target_dir = PLUGINS_DIR / plugin_id

    # 检查是否已存在同名插件
    if target_dir.exists():
        # 先删除旧版本
        try:
            shutil.rmtree(target_dir)
        except Exception as e:
            logger.warning("删除旧插件目录失败: {}", e)
            return False, f"删除旧版本失败: {e}"

    # 解压到临时目录再移动，避免解压失败导致残留
    try:
        with zipfile.ZipFile(dw_path, "r") as zf:
            # 验证必须文件
            namelist = set(zf.namelist())
            missing = _REQUIRED_FILES - namelist
            if missing:
                return False, f".dw 包中缺少必要文件: {', '.join(missing)}"

            # 安全检查：确保没有路径穿越
            for name in zf.namelist():
                if name.startswith("/") or ".." in name:
                    return False, f".dw 包中包含不安全的路径: {name}"

            # 解压
            target_dir.mkdir(parents=True, exist_ok=True)
            zf.extractall(target_dir)

            logger.info("插件 '{}' 已安装到 {}", plugin_name, target_dir)
            return True, f"插件「{plugin_name}」安装成功"

    except zipfile.BadZipFile:
        return False, ".dw 文件格式无效"
    except Exception as e:
        logger.exception("安装 .dw 文件失败: {}", dw_path.name)
        # 清理残留
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        return False, f"安装失败: {e}"


def create_dw(plugin_dir: str | Path, output_path: str | Path | None = None) -> tuple[bool, str]:
    """
    将插件目录打包为 .dw 文件。

    Parameters
    ----------
    plugin_dir : str | Path
        插件目录路径（包含 __init__.py 和 plugin.json）
    output_path : str | Path | None
        输出 .dw 文件路径，默认为插件目录同级

    Returns
    -------
    tuple[bool, str]
        (成功与否, 消息)
    """
    plugin_dir = Path(plugin_dir)
    if not plugin_dir.is_dir():
        return False, "插件目录不存在"

    # 检查必要文件
    if not (plugin_dir / "__init__.py").exists():
        return False, "缺少 __init__.py"
    if not (plugin_dir / "plugin.json").exists():
        return False, "缺少 plugin.json"

    # 读取插件 ID
    try:
        with open(plugin_dir / "plugin.json", "r", encoding="utf-8") as f:
            meta = json.load(f)
        plugin_id = meta.get("id", plugin_dir.name)
        plugin_name = meta.get("name", plugin_id)
    except Exception:
        plugin_id = plugin_dir.name
        plugin_name = plugin_id

    # 确定输出路径
    if output_path is None:
        output_path = plugin_dir.parent / f"{plugin_id}.dw"
    else:
        output_path = Path(output_path)

    try:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in plugin_dir.rglob("*"):
                if file_path.is_file():
                    # 跳过 __pycache__、.pyc、运行时数据等
                    rel = file_path.relative_to(plugin_dir)
                    skip = any(
                        p in rel.parts
                        for p in ("__pycache__", ".git", ".gitkeep", "config.json")
                    )
                    if skip or file_path.suffix == ".pyc":
                        continue
                    zf.write(file_path, arcname=str(rel))

        logger.info("插件 '{}' 已打包为 {}", plugin_name, output_path)
        return True, f"已打包: {output_path}"

    except Exception as e:
        logger.exception("打包 .dw 失败: {}", plugin_name)
        return False, f"打包失败: {e}"
