import logging
from pathlib import Path

import pygame
import pygame.freetype

from src import const


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
        const.PROJECT_ROOT / "assets/fonts/pvz2.ttf",
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


class AssetsManager:
    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}
    SOUND_EXTS = {".wav", ".mp3", ".ogg"}
    FONT_EXTS = {".ttf", ".otf"}
    # 暂不解析的格式：reanim 等大体量数据，避免启动刷屏
    SKIP_EXTS = {".reanim", ".xml", ".json", ".txt", ".md", ".ini"}
    # 目录名命中即跳过：reanim 动画数据（大量 png 帧）不进资源池
    SKIP_DIRS = {"reanim"}

    def __init__(self) -> None:
        DEFAULT_SURFACE = _default_surface()
        DEFAULT_SOUND = pygame.mixer.Sound(buffer=b"\x00" * 44100)
        DEFAULT_FONT = _default_font()

        self.surfaces: dict[str, pygame.Surface] = {"default": DEFAULT_SURFACE}
        self.sounds: dict[str, pygame.mixer.Sound] = {"default": DEFAULT_SOUND}
        self.fonts: dict = {"default": DEFAULT_FONT}
        self._root: Path | None = None

    def load_all(self, path) -> None:
        # 记录资源根目录；资源改为按需加载，启动不再全量 rglob 预加载
        root = Path(path)
        if not root.is_dir():
            logging.warning("资源目录不存在: %s", root)
            return
        self._root = root.resolve()
        logging.info(
            "AssetsManager ready (%d default surfaces, %d default sounds, %d default fonts); on-demand loading from %s",
            len(self.surfaces),
            len(self.sounds),
            len(self.fonts),
            self._root,
        )

    def _file_for_key(self, key: str) -> Path | None:
        # 将 posix key 映射为资源根目录下的文件；root 未就绪/越界/不存在返回 None
        if self._root is None:
            return None
        candidate = (self._root / key).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError:
            logging.warning("资源 key 越界，拒绝加载: %s", key)
            return None
        if not candidate.is_file():
            return None
        return candidate

    def _try_load(self, key: str) -> bool:
        # 按需加载单个资源；跳过目录（如 reanim 动画帧）与 SKIP_EXTS 格式
        file = self._file_for_key(key)
        if file is None:
            return False
        parts = file.relative_to(self._root).parts
        if any(part in self.SKIP_DIRS for part in parts[:-1]):
            logging.debug("跳过资源目录: %s", file)
            return False
        ext = file.suffix.lower()
        if ext in self.SKIP_EXTS:
            logging.debug("跳过资源扩展名: %s", file)
            return False
        try:
            if ext in self.IMAGE_EXTS:
                self.surfaces[key] = pygame.image.load(file).convert_alpha()
            elif ext in self.SOUND_EXTS:
                self.sounds[key] = pygame.mixer.Sound(file)
            elif ext in self.FONT_EXTS:
                self.fonts[key] = pygame.freetype.Font(file)
            else:
                return False
        except Exception as e:
            logging.warning("资源加载失败 %s: %s", file, e)
            return False
        logging.debug("按需加载资源 %s", file)
        return True

    def get_surface(self, key):
        if key not in self.surfaces:
            self._try_load(key)
        if key not in self.surfaces:
            logging.warning("Surface with key '%s' not found. Returning default surface.", key)
            key = "default"
        return self.surfaces[key].copy()

    def get_sound(self, key):
        if key not in self.sounds:
            self._try_load(key)
        if key not in self.sounds:
            logging.warning("Sound with key '%s' not found. Returning default sound.", key)
            key = "default"
        return self.sounds[key].copy()

    def get_font(self, key):
        if key not in self.fonts:
            self._try_load(key)
        if key not in self.fonts:
            logging.warning("Font with key '%s' not found. Returning default font.", key)
            key = "default"
        return self.fonts[key]
