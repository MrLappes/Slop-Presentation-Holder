from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path
import json
import hashlib

@dataclass
class PresenterConfig:
    name: str
    title: str = ""
    voice_model: str = ""
    speaker_id: Optional[int] = None
    length_scale: float = 1.0
    noise_scale: float = 0.667
    noise_w_scale: float = 0.8
    color: tuple = (100, 100, 100)
    gif_mode: str = "tint"  # "tint", "solid", "none"

@dataclass
class SlideConfig:
    presenter: str = ""
    text: str = ""

@dataclass
class GifConfig:
    path: str = ""
    target_color: tuple = (235, 78, 10)
    tolerance: int = 60
    scale: float = 2.0

@dataclass
class SlopProject:
    version: int = 1
    name: str = "Untitled"
    pdf_path: str = ""
    gif: GifConfig = field(default_factory=GifConfig)
    auto_advance: bool = True
    auto_advance_delay: float = 1.2
    presenters: dict = field(default_factory=dict)  # name -> PresenterConfig
    slides: list = field(default_factory=list)  # list of SlideConfig
    _file_path: Optional[Path] = field(default=None, repr=False)

    @property
    def base_dir(self) -> Path:
        if self._file_path:
            return self._file_path.parent
        return Path.cwd()

    @property
    def resolved_pdf_path(self) -> Path:
        p = Path(self.pdf_path)
        if p.is_absolute():
            return p
        return self.base_dir / p

    @property
    def resolved_gif_path(self) -> Optional[Path]:
        if not self.gif.path:
            return None
        p = Path(self.gif.path)
        if p.is_absolute():
            return p
        return self.base_dir / p

    @property
    def cache_dir(self) -> Path:
        from slop.constants import CACHE_DIR
        h = hashlib.md5(str(self._file_path or self.name).encode()).hexdigest()[:8]
        d = CACHE_DIR / h
        d.mkdir(parents=True, exist_ok=True)
        return d

    def resolve_voice_model(self, presenter_name: str) -> Path:
        p = Path(self.presenters[presenter_name].voice_model)
        if p.is_absolute():
            return p
        return self.base_dir / p

    def save(self, path: Optional[Path] = None) -> None:
        path = path or self._file_path
        if not path:
            raise ValueError("No path specified")
        self._file_path = Path(path)
        data = self._to_dict()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path) -> 'SlopProject':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        project = cls._from_dict(data)
        project._file_path = Path(path)
        return project

    @classmethod
    def new_from_pdf(cls, pdf_path: str, num_slides: int) -> 'SlopProject':
        project = cls(
            name=Path(pdf_path).stem,
            pdf_path=pdf_path,
            slides=[SlideConfig() for _ in range(num_slides)],
        )
        return project

    def _to_dict(self) -> dict:
        # Custom serialization: convert tuples to lists for JSON,
        # skip _file_path, convert dataclass instances
        result = {
            "version": self.version,
            "name": self.name,
            "pdf_path": self.pdf_path,
            "gif": {
                "path": self.gif.path,
                "target_color": list(self.gif.target_color),
                "tolerance": self.gif.tolerance,
                "scale": self.gif.scale,
            },
            "auto_advance": self.auto_advance,
            "auto_advance_delay": self.auto_advance_delay,
            "presenters": {},
            "slides": [],
        }
        for name, p in self.presenters.items():
            result["presenters"][name] = {
                "title": p.title,
                "voice_model": p.voice_model,
                "speaker_id": p.speaker_id,
                "length_scale": p.length_scale,
                "noise_scale": p.noise_scale,
                "noise_w_scale": p.noise_w_scale,
                "color": list(p.color),
                "gif_mode": p.gif_mode,
            }
        for s in self.slides:
            result["slides"].append({
                "presenter": s.presenter,
                "text": s.text,
            })
        return result

    @classmethod
    def _from_dict(cls, data: dict) -> 'SlopProject':
        gif_data = data.get("gif", {})
        gif = GifConfig(
            path=gif_data.get("path", ""),
            target_color=tuple(gif_data.get("target_color", [235, 78, 10])),
            tolerance=gif_data.get("tolerance", 60),
            scale=gif_data.get("scale", 2.0),
        )
        presenters = {}
        for name, pd in data.get("presenters", {}).items():
            presenters[name] = PresenterConfig(
                name=name,
                title=pd.get("title", ""),
                voice_model=pd.get("voice_model", ""),
                speaker_id=pd.get("speaker_id"),
                length_scale=pd.get("length_scale", 1.0),
                noise_scale=pd.get("noise_scale", 0.667),
                noise_w_scale=pd.get("noise_w_scale", 0.8),
                color=tuple(pd.get("color", [100, 100, 100])),
                gif_mode=pd.get("gif_mode", "tint"),
            )
        slides = []
        for sd in data.get("slides", []):
            slides.append(SlideConfig(
                presenter=sd.get("presenter", ""),
                text=sd.get("text", ""),
            ))
        return cls(
            version=data.get("version", 1),
            name=data.get("name", "Untitled"),
            pdf_path=data.get("pdf_path", ""),
            gif=gif,
            auto_advance=data.get("auto_advance", True),
            auto_advance_delay=data.get("auto_advance_delay", 1.2),
            presenters=presenters,
            slides=slides,
        )

    def to_engine_dict(self) -> dict:
        """Convert to the dict format expected by the presentation engine."""
        return {
            "pdf_path": str(self.resolved_pdf_path),
            "slides": [{"presenter": s.presenter, "text": s.text} for s in self.slides],
            "presenters": {
                name: {
                    "color": p.color,
                    "title": p.title,
                    "voice_model": str(self.resolve_voice_model(name)),
                    "speaker_id": p.speaker_id,
                    "length_scale": p.length_scale,
                    "noise_scale": p.noise_scale,
                    "noise_w_scale": p.noise_w_scale,
                    "gif_mode": p.gif_mode,
                }
                for name, p in self.presenters.items()
            },
            "gif": {
                "path": str(self.resolved_gif_path) if self.resolved_gif_path else "",
                "target_color": self.gif.target_color,
                "tolerance": self.gif.tolerance,
                "scale": self.gif.scale,
            },
            "auto_advance": self.auto_advance,
            "auto_advance_delay": self.auto_advance_delay,
            "cache_dir": str(self.cache_dir),
        }
