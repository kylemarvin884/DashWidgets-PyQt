""" .dw 插件包服务测试：打包/读取/安装/版本感知升级"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from app.services import dw_package_service as dps


def _make_plugin_dir(base: Path, plugin_id: str, version: str = "1.0.0",
                     with_config: bool = False) -> Path:
    pdir = base / plugin_id
    pdir.mkdir(parents=True)
    (pdir / "plugin.json").write_text(
        json.dumps({"id": plugin_id, "name": f"测试插件", "version": version},
                   ensure_ascii=False),
        encoding="utf-8",
    )
    (pdir / "__init__.py").write_text(
        "from app.plugins.base_plugin import BasePlugin, PluginMeta\n\n\n"
        f"class Plugin(BasePlugin):\n"
        f"    meta = PluginMeta(id='{plugin_id}', name='测试插件', version='{version}')\n",
        encoding="utf-8",
    )
    if with_config:
        (pdir / "config.json").write_text('{"key": "value"}', encoding="utf-8")
    return pdir


def _make_dw(tmp_path: Path, plugin_id: str, version: str) -> Path:
    src = _make_plugin_dir(tmp_path / "src", plugin_id, version)
    dw_path = tmp_path / f"{plugin_id}.dw"
    ok, msg = dps.create_dw(src, dw_path)
    assert ok, msg
    return dw_path


@pytest.fixture
def plugins_dir(self=None, ):
    # 由 monkeypatch 使用
    return None


class TestCreateAndRead:
    def test_create_and_read_meta(self, tmp_path: Path):
        dw = _make_dw(tmp_path, "pack_test", "1.2.3")
        assert dw.exists()

        meta = dps.read_dw_meta(dw)
        assert meta is not None
        assert meta["id"] == "pack_test"
        assert meta["version"] == "1.2.3"

    def test_read_invalid_file(self, tmp_path: Path):
        bad = tmp_path / "bad.dw"
        bad.write_bytes(b"not a zip")
        assert dps.read_dw_meta(bad) is None

    def test_create_missing_init(self, tmp_path: Path):
        pdir = tmp_path / "incomplete"
        pdir.mkdir()
        (pdir / "plugin.json").write_text('{"id": "x", "name": "x"}', encoding="utf-8")
        ok, _ = dps.create_dw(pdir)
        assert not ok

    def test_dw_excludes_pycache(self, tmp_path: Path):
        src = _make_plugin_dir(tmp_path / "src", "clean_pack")
        cache_dir = src / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "mod.cpython-313.pyc").write_bytes(b"junk")

        dw = tmp_path / "clean_pack.dw"
        ok, msg = dps.create_dw(src, dw)
        assert ok, msg

        with zipfile.ZipFile(dw) as zf:
            names = zf.namelist()
        assert not any("__pycache__" in n for n in names)
        assert not any(n.endswith(".pyc") for n in names)


class TestInstall:
    @pytest.fixture
    def installed_env(self, tmp_path: Path, monkeypatch):
        base = tmp_path / "plugins_ext"
        base.mkdir()
        monkeypatch.setattr(dps, "PLUGINS_DIR", base)
        return base

    def test_fresh_install(self, installed_env: Path, tmp_path: Path):
        dw = _make_dw(tmp_path, "new_plugin", "1.0.0")
        ok, msg = dps.install_dw(dw)
        assert ok, msg
        assert (installed_env / "new_plugin" / "plugin.json").exists()

    def test_upgrade_same_or_newer_allowed(self, installed_env: Path, tmp_path: Path):
        dw_v1 = _make_dw(tmp_path / "v1", "up_plugin", "1.0.0")
        ok, _ = dps.install_dw(dw_v1)
        assert ok

        dw_v2 = _make_dw(tmp_path / "v2", "up_plugin", "1.1.0")
        ok, msg = dps.install_dw(dw_v2)
        assert ok, msg
        installed = json.loads(
            (installed_env / "up_plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        assert installed["version"] == "1.1.0"

    def test_downgrade_rejected(self, installed_env: Path, tmp_path: Path):
        dw_v2 = _make_dw(tmp_path / "v2", "dg_plugin", "2.0.0")
        ok, _ = dps.install_dw(dw_v2)
        assert ok

        dw_v1 = _make_dw(tmp_path / "v1", "dg_plugin", "1.0.0")
        ok, msg = dps.install_dw(dw_v1)
        assert not ok
        assert "降级" in msg or "更新" in msg

    def test_upgrade_preserves_config(self, installed_env: Path, tmp_path: Path):
        # 先手动安装 v1 并写入插件配置
        src = _make_plugin_dir(tmp_path / "src1", "cfg_plugin", "1.0.0", with_config=True)
        import shutil
        shutil.copytree(src, installed_env / "cfg_plugin")

        # 升级到 v2（包内没有 config.json）
        dw_v2 = _make_dw(tmp_path / "v2", "cfg_plugin", "2.0.0")
        ok, msg = dps.install_dw(dw_v2)
        assert ok, msg

        cfg = (installed_env / "cfg_plugin" / "config.json")
        assert cfg.exists()
        assert json.loads(cfg.read_text(encoding="utf-8")) == {"key": "value"}

    def test_missing_required_files(self, installed_env: Path, tmp_path: Path):
        dw = tmp_path / "broken.dw"
        with zipfile.ZipFile(dw, "w") as zf:
            zf.writestr("plugin.json", '{"id": "broken", "name": "x"}')
            # 缺少 __init__.py
        ok, msg = dps.install_dw(dw)
        assert not ok
        assert "__init__.py" in msg

    def test_path_traversal_rejected(self, installed_env: Path, tmp_path: Path):
        dw = tmp_path / "evil.dw"
        with zipfile.ZipFile(dw, "w") as zf:
            zf.writestr("plugin.json", '{"id": "evil", "name": "x"}')
            zf.writestr("__init__.py", "x = 1")
            zf.writestr("../evil.txt", "boom")
        ok, _msg = dps.install_dw(dw)
        assert not ok

    def test_version_tuple(self):
        assert dps._version_tuple("1.2.3") == (1, 2, 3)
        assert dps._version_tuple("10.0") == (10, 0, 0)
        assert dps._version_tuple("1.2.3-rc.1") == (1, 2, 3)
        assert dps._version_tuple("2") == (2, 0, 0)
        assert dps._version_tuple("") == (0, 0, 0)
