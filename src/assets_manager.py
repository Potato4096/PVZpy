import logging
from pathlib import Path

import pygame
import pygame.freetype


def _default_surface():
    # 占位图：紫黑棋盘格
    surface = pygame.Surface((64, 64), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 255))
    pygame.draw.rect(surface, (255, 0, 255, 255), (0, 0, 32, 32))
    pygame.draw.rect(surface, (255, 0, 255, 255), (32, 32, 32, 32))
    return surface


def _default_font():
    # 本机 SysFont 可能异常，优先用项目字体文件
    candidates = [
        Path("assets/fonts/pvz2.ttf"),
        Path(__file__).resolve().parents[1] / "assets/fonts/pvz2.ttf",
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            try:
                return pygame.freetype.Font(str(path), 24)
            except Exception:
                continue
    try:
        return pygame.freetype.Font(None, 24)
    except Exception as e:
        logging.error("No usable default font: %s", e)
        raise


def _asset_key(asset: Path) -> str:
    # 资源 key：相对 cwd 的 posix 路径
    resolved = asset.resolve()
    try:
        return resolved.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return resolved.as_posix()


class AssetsManager:
    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}
    SOUND_EXTS = {".wav", ".mp3", ".ogg"}
    FONT_EXTS = {".ttf", ".otf"}
    # 暂不解析的格式：reanim 等大体量数据，避免启动刷屏
    SKIP_EXTS = {".reanim", ".xml", ".json", ".txt", ".md", ".ini"}

    def __init__(self) -> None:
        DEFAULT_SURFACE = _default_surface()
        DEFAULT_SOUND = pygame.mixer.Sound(buffer=b"\x00" * 44100)
        DEFAULT_FONT = _default_font()

        self.surfaces: dict[str, pygame.Surface] = {"default": DEFAULT_SURFACE}
        self.sounds: dict[str, pygame.mixer.Sound] = {"default": DEFAULT_SOUND}
        self.fonts: dict = {"default": DEFAULT_FONT}

    def load_all(self, path) -> None:
        root = Path(path)
        if not root.is_dir():
            logging.warning("资源目录不存在: %s", root)
            return
        for asset in root.rglob("*"):
            if not asset.is_file():
                continue
            ext = asset.suffix.lower()
            if ext in self.SKIP_EXTS:
                continue
            key = _asset_key(asset)
            try:
                if ext in self.IMAGE_EXTS:
                    self.surfaces[key] = pygame.image.load(asset).convert_alpha()
                elif ext in self.SOUND_EXTS:
                    self.sounds[key] = pygame.mixer.Sound(asset)
                elif ext in self.FONT_EXTS:
                    self.fonts[key] = pygame.freetype.Font(asset)
                else:
                    continue
            except Exception as e:
                logging.warning("资源加载失败 %s: %s", asset, e)
                continue
            logging.debug("Successfully loaded asset %s", asset)
        logging.info(
            "Loaded %d surfaces, %d sounds, %d fonts from %s",
            len(self.surfaces),
            len(self.sounds),
            len(self.fonts),
            path,
        )
    def get_surface(self, key):
        if key not in self.surfaces:
            logging.warning("Surface with key '%s' not found. Returning default surface.", key)
            key = "default"
        return self.surfaces[key].copy()

    def get_sound(self, key):
        if key not in self.sounds:
            logging.warning("Sound with key '%s' not found. Returning default sound.", key)
            key = "default"
        return self.sounds[key].copy()

    def get_font(self, key):
        if key not in self.fonts:
            logging.warning("Font with key '%s' not found. Returning default font.", key)
            key = "default"
        return self.fonts[key]
