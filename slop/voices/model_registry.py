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
    def _join_url(base_url: str, relative_path: str) -> str:
        base_url = base_url.rstrip("/")
        relative_path = relative_path.lstrip("/")
        return f"{base_url}/{relative_path}"

    @staticmethod
    def _url_json(url: str) -> dict:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Unexpected JSON format from {url}")
        return data

    def _catalog_sources(self) -> list[dict]:
        return [
            {
                "name": "official",
                "label": "Official",
                "kind": "official",
                "catalog_url": HF_VOICES_JSON,
                "base_url": HF_MODEL_BASE,
            },
            {
                "name": "vi_voice",
                "label": "Unofficial - Vietnamese",
                "kind": "index",
                "catalog_url": "https://huggingface.co/sannht/vi_voice/raw/main/index.json",
                "base_url": "https://huggingface.co/sannht/vi_voice/resolve/main",
            },
            {
                "name": "agentvibes",
                "label": "Unofficial - AgentVibes",
                "kind": "static",
                "base_url": "https://huggingface.co/agentvibes/piper-custom-voices/resolve/main",
                "items": [
                    {
                        "id": "kristin",
                        "name": "Kristin",
                        "language": "en",
                        "quality": "medium",
                        "num_speakers": 1,
                        "onnx_rel": "kristin.onnx",
                        "onnx_json_rel": "kristin.onnx.json",
                    },
                    {
                        "id": "jenny",
                        "name": "Jenny",
                        "language": "en-gb",
                        "quality": "high",
                        "num_speakers": 1,
                        "onnx_rel": "jenny.onnx",
                        "onnx_json_rel": "jenny.onnx.json",
                    },
                    {
                        "id": "tracy",
                        "name": "Tracy (ManyVoice)",
                        "language": "en",
                        "quality": "medium",
                        "num_speakers": 16,
                        "onnx_rel": "tracy.onnx",
                        "onnx_json_rel": "tracy.onnx.json",
                    },
                ],
            },
        ]

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

        if "onnx" in files and "json" in files:
            onnx_rel = files.get("onnx")
            cfg_rel = files.get("json")
            if isinstance(onnx_rel, str) and isinstance(cfg_rel, str):
                return onnx_rel, cfg_rel

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
            cached = self._read_json(self._catalog_cache)
            if isinstance(cached, dict) and cached:
                first_item = next(iter(cached.values()))
                if isinstance(first_item, dict) and "source" in first_item:
                    self._catalog = cached
                    return self._catalog

        merged: dict[str, dict] = {}
        fetch_errors: list[str] = []

        for source in self._catalog_sources():
            try:
                if source["kind"] == "official":
                    catalog = self._url_json(source["catalog_url"])
                    for key, meta in catalog.items():
                        if not isinstance(meta, dict):
                            continue
                        onnx_rel, cfg_rel = self._extract_file_paths(meta)
                        if not onnx_rel or not cfg_rel:
                            continue

                        unique_key = f"{source['name']}::{key}"
                        merged[unique_key] = {
                            "key": unique_key,
                            "source": source["label"],
                            "base_url": source["base_url"],
                            "name": str(meta.get("name") or key),
                            "language": self._language_code(meta),
                            "quality": str(meta.get("quality", "")),
                            "num_speakers": int(meta.get("num_speakers", 1) or 1),
                            "speaker_id_map": meta.get("speaker_id_map", {}) or {},
                            "size_mb": self._onnx_size_mb(meta),
                            "onnx_rel": onnx_rel,
                            "onnx_json_rel": cfg_rel,
                            "installed": False,
                        }
                elif source["kind"] == "index":
                    catalog = self._url_json(source["catalog_url"])
                    for voice in catalog.get("voices", []):
                        if not isinstance(voice, dict):
                            continue
                        files = voice.get("files", {})
                        if not isinstance(files, dict):
                            continue
                        onnx_rel = files.get("onnx")
                        cfg_rel = files.get("json")
                        if not isinstance(onnx_rel, str) or not isinstance(cfg_rel, str):
                            continue

                        unique_key = f"{source['name']}::{voice.get('id', onnx_rel)}"
                        size_bytes = voice.get("size_bytes", {})
                        onnx_size = 0
                        if isinstance(size_bytes, dict):
                            onnx_size = int(size_bytes.get("onnx", 0) or 0)

                        merged[unique_key] = {
                            "key": unique_key,
                            "source": source["label"],
                            "base_url": source["base_url"],
                            "name": str(voice.get("name") or voice.get("id") or onnx_rel),
                            "language": str(voice.get("language", "")),
                            "quality": str(voice.get("quality") or voice.get("piper_version") or ""),
                            "num_speakers": int(voice.get("num_speakers", 1) or 1),
                            "speaker_id_map": voice.get("speaker_id_map", {}) or {},
                            "size_mb": float(onnx_size) / (1024 * 1024) if onnx_size else 0.0,
                            "onnx_rel": onnx_rel,
                            "onnx_json_rel": cfg_rel,
                            "installed": False,
                        }
                elif source["kind"] == "static":
                    for voice in source.get("items", []):
                        if not isinstance(voice, dict):
                            continue
                        unique_key = f"{source['name']}::{voice['id']}"
                        merged[unique_key] = {
                            "key": unique_key,
                            "source": source["label"],
                            "base_url": source["base_url"],
                            "name": str(voice.get("name") or voice["id"]),
                            "language": str(voice.get("language", "")),
                            "quality": str(voice.get("quality", "")),
                            "num_speakers": int(voice.get("num_speakers", 1) or 1),
                            "speaker_id_map": voice.get("speaker_id_map", {}) or {},
                            "size_mb": float(voice.get("size_mb", 0.0) or 0.0),
                            "onnx_rel": str(voice["onnx_rel"]),
                            "onnx_json_rel": str(voice["onnx_json_rel"]),
                            "installed": False,
                        }
            except Exception as e:
                fetch_errors.append(f"{source['name']}: {e}")

        if merged:
            installed_stems = {Path(m["path"]).stem for m in self.list_installed()}
            for item in merged.values():
                model_stem = Path(item["onnx_rel"]).stem
                item["installed"] = model_stem in installed_stems or Path(item["key"]).stem in installed_stems

            self._catalog = merged
            self._write_json(self._catalog_cache, merged)
            return self._catalog

        if self._catalog_cache.exists():
            self._catalog = self._read_json(self._catalog_cache)
            return self._catalog

        if fetch_errors:
            raise RuntimeError("Failed to load any voice catalogs: " + "; ".join(fetch_errors))
        raise RuntimeError("No voice catalogs available")

    def _catalog_items(self) -> list[dict]:
        catalog = self.fetch_catalog(force=False)

        items = []
        for key, meta in catalog.items():
            if not isinstance(meta, dict):
                continue
            items.append(meta)

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

        onnx_rel = meta.get("onnx_rel")
        cfg_rel = meta.get("onnx_json_rel")
        base_url = str(meta.get("base_url", HF_MODEL_BASE))
        if not isinstance(onnx_rel, str) or not isinstance(cfg_rel, str):
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

        onnx_url = self._join_url(base_url, onnx_rel)
        cfg_url = self._join_url(base_url, cfg_rel)

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
