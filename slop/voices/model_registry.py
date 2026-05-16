"""Local/remote Piper voice model catalog and download helper."""

from __future__ import annotations

import json
import re
import shutil
import urllib.request
from pathlib import Path

from slop.constants import HF_MODEL_BASE, HF_VOICES_JSON, VOICES_DIR


class VoiceModelRegistry:
    """Manage local Piper models and HuggingFace voice catalog metadata."""

    def __init__(self, voices_dir: Path | None = None):
        self._voices_dir = Path(voices_dir or VOICES_DIR)
        self._voices_dir.mkdir(parents=True, exist_ok=True)
        self._catalog_cache = self._voices_dir / "voices.catalog.json"
        self._catalog: dict[str, dict] = {}

    @staticmethod
    def _safe_name(name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
        return cleaned or "voice"

    @staticmethod
    def _read_json(path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _language_code(meta: dict) -> str:
        lang = meta.get("language")
        if isinstance(lang, dict):
            return str(lang.get("code", ""))
        if isinstance(lang, str):
            return lang
        return ""

    @staticmethod
    def _extract_file_paths(meta: dict) -> tuple[str | None, str | None]:
        files = meta.get("files", {})
        if not isinstance(files, dict):
            return None, None

        onnx_rel = None
        cfg_rel = None
        for rel in files.keys():
            if rel.endswith(".onnx") and onnx_rel is None:
                onnx_rel = rel
            elif rel.endswith(".onnx.json") and cfg_rel is None:
                cfg_rel = rel
        return onnx_rel, cfg_rel

    @staticmethod
    def _onnx_size_mb(meta: dict) -> float:
        files = meta.get("files", {})
        if not isinstance(files, dict):
            return 0.0
        for rel, info in files.items():
            if rel.endswith(".onnx") and isinstance(info, dict):
                size = info.get("size_bytes", 0) or 0
                return float(size) / (1024 * 1024)
        return 0.0

    def fetch_catalog(self, force: bool = False) -> dict[str, dict]:
        """Fetch Piper catalog from HuggingFace and cache it locally."""
        if self._catalog and not force:
            return self._catalog

        if not force and self._catalog_cache.exists():
            self._catalog = self._read_json(self._catalog_cache)
            return self._catalog

        try:
            with urllib.request.urlopen(HF_VOICES_JSON, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Unexpected catalog format")
            self._catalog = data
            self._write_json(self._catalog_cache, data)
            return self._catalog
        except Exception:
            if self._catalog_cache.exists():
                self._catalog = self._read_json(self._catalog_cache)
                return self._catalog
            raise

    def _catalog_items(self) -> list[dict]:
        catalog = self.fetch_catalog(force=False)
        installed = {m["name"] for m in self.list_installed()}

        items = []
        for key, meta in catalog.items():
            if not isinstance(meta, dict):
                continue
            onnx_rel, cfg_rel = self._extract_file_paths(meta)
            if not onnx_rel or not cfg_rel:
                continue

            display_name = str(meta.get("name") or key)
            language = self._language_code(meta)
            quality = str(meta.get("quality", ""))
            num_speakers = int(meta.get("num_speakers", 1) or 1)
            size_mb = self._onnx_size_mb(meta)

            items.append({
                "key": str(key),
                "name": display_name,
                "language": language,
                "quality": quality,
                "num_speakers": num_speakers,
                "speaker_id_map": meta.get("speaker_id_map", {}) or {},
                "size_mb": size_mb,
                "onnx_rel": onnx_rel,
                "onnx_json_rel": cfg_rel,
                "installed": str(key) in installed,
            })

        items.sort(key=lambda x: (x["language"], x["name"], x["quality"]))
        return items

    def list_available(self, language: str = "", quality: str = "", search: str = "") -> list[dict]:
        """List downloadable voices with optional filters."""
        language = language.strip().lower()
        quality = quality.strip().lower()
        search = search.strip().lower()

        result = []
        for item in self._catalog_items():
            lang_code = item["language"].lower()
            if language and not (lang_code == language or lang_code.startswith(f"{language}_")):
                continue
            if quality and item["quality"].lower() != quality:
                continue
            if search:
                hay = " ".join([item["key"], item["name"], item["language"], item["quality"]]).lower()
                if search not in hay:
                    continue
            result.append(item)

        return result

    def list_installed(self) -> list[dict]:
        """List local voice models from VOICES_DIR."""
        out = []
        for onnx_path in sorted(self._voices_dir.glob("*.onnx")):
            name = onnx_path.stem
            cfg_path = self._voices_dir / f"{name}.onnx.json"

            language = ""
            quality = ""
            num_speakers = 1
            speaker_id_map = {}

            if cfg_path.exists():
                try:
                    meta = self._read_json(cfg_path)
                    language = self._language_code(meta)
                    quality = str(meta.get("quality", ""))
                    speaker_id_map = meta.get("speaker_id_map", {}) or {}
                    if isinstance(speaker_id_map, dict) and speaker_id_map:
                        num_speakers = len(speaker_id_map)
                    else:
                        num_speakers = int(meta.get("num_speakers", 1) or 1)
                except Exception:
                    pass

            size_mb = float(onnx_path.stat().st_size) / (1024 * 1024)
            out.append({
                "name": name,
                "path": str(onnx_path),
                "language": language,
                "quality": quality,
                "num_speakers": num_speakers,
                "speaker_id_map": speaker_id_map,
                "size_mb": size_mb,
            })

        return out

    def get_installed_model(self, model_name: str) -> dict | None:
        for m in self.list_installed():
            if m["name"] == model_name:
                return m
        return None

    def rename_model(self, old_name: str, new_name: str) -> tuple[Path, Path]:
        old_name = self._safe_name(old_name)
        new_name = self._safe_name(new_name)
        if old_name == new_name:
            raise ValueError("New name must be different")

        old_onnx = self._voices_dir / f"{old_name}.onnx"
        old_cfg = self._voices_dir / f"{old_name}.onnx.json"
        new_onnx = self._voices_dir / f"{new_name}.onnx"
        new_cfg = self._voices_dir / f"{new_name}.onnx.json"

        if not old_onnx.exists():
            raise FileNotFoundError(f"Model not found: {old_name}")
        if new_onnx.exists() or new_cfg.exists():
            raise FileExistsError(f"Target already exists: {new_name}")

        old_onnx.rename(new_onnx)
        if old_cfg.exists():
            old_cfg.rename(new_cfg)

        return old_onnx, new_onnx

    def delete_model(self, model_name: str) -> None:
        model_name = self._safe_name(model_name)
        onnx = self._voices_dir / f"{model_name}.onnx"
        cfg = self._voices_dir / f"{model_name}.onnx.json"

        if not onnx.exists() and not cfg.exists():
            raise FileNotFoundError(f"Model not found: {model_name}")

        if onnx.exists():
            onnx.unlink()
        if cfg.exists():
            cfg.unlink()

    @staticmethod
    def _download_file(url: str, out_path: Path, progress_callback=None, total_offset=0, total_size=0):
        out_path.parent.mkdir(parents=True, exist_ok=True)

        def reporthook(block_num: int, block_size: int, total: int):
            if not progress_callback:
                return
            downloaded = min(block_num * block_size, total if total > 0 else block_num * block_size)
            if total_size > 0:
                progress_callback(total_offset + downloaded, total_size)
            else:
                progress_callback(downloaded, total if total > 0 else 0)

        urllib.request.urlretrieve(url, str(out_path), reporthook=reporthook)

    def download_model(self, key: str, local_name: str | None = None, progress_callback=None) -> Path:
        """Download one voice model (.onnx + .onnx.json) and return local .onnx path."""
        catalog = self.fetch_catalog(force=False)
        meta = catalog.get(key)
        if not isinstance(meta, dict):
            raise KeyError(f"Voice key not found: {key}")

        onnx_rel, cfg_rel = self._extract_file_paths(meta)
        if not onnx_rel or not cfg_rel:
            raise ValueError(f"Voice entry has no model files: {key}")

        model_name = self._safe_name(local_name or key)
        out_onnx = self._voices_dir / f"{model_name}.onnx"
        out_cfg = self._voices_dir / f"{model_name}.onnx.json"

        if out_onnx.exists() and out_cfg.exists():
            return out_onnx

        files = meta.get("files", {})
        onnx_size = int((files.get(onnx_rel, {}) or {}).get("size_bytes", 0) or 0)
        cfg_size = int((files.get(cfg_rel, {}) or {}).get("size_bytes", 0) or 0)
        total_size = onnx_size + cfg_size

        tmp_onnx = out_onnx.with_suffix(out_onnx.suffix + ".part")
        tmp_cfg = out_cfg.with_suffix(out_cfg.suffix + ".part")

        onnx_url = f"{HF_MODEL_BASE}/{onnx_rel}"
        cfg_url = f"{HF_MODEL_BASE}/{cfg_rel}"

        try:
            self._download_file(onnx_url, tmp_onnx, progress_callback, total_offset=0, total_size=total_size)
            self._download_file(cfg_url, tmp_cfg, progress_callback, total_offset=onnx_size, total_size=total_size)

            shutil.move(str(tmp_onnx), str(out_onnx))
            shutil.move(str(tmp_cfg), str(out_cfg))
        finally:
            if tmp_onnx.exists():
                tmp_onnx.unlink()
            if tmp_cfg.exists():
                tmp_cfg.unlink()

        return out_onnx
