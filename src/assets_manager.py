import logging
from pathlib import Path
from typing import Dict, List, Optional

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
    # 本机 SysFont 可能异常，优先用项目字体文件（M3：本体资源位于 assets/PVZpy/）
    candidates = [
        const.ASSETS_BUILTIN_DIR / "fonts/pvz2.ttf",
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
    """资源管理器（M3：按命名空间解析）。

    资源 key 采用「命名空间/类型/资源」posix 路径（如 PVZpy/fonts/pvz2.ttf），
    也支持不带命名空间的相对 key（如 fonts/pvz2.ttf），此时按「默认命名空间
    解析」查找：先查已注册的 Mod 命名空间资源根（mods/<modid>/assets/，按注册
    顺序），再查本体命名空间根（assets/PVZpy/）——即 Mod 资源可覆盖原版资源。
    带命名空间的 key 直接映射到对应资源根，互不干扰。
    """

    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}
    SOUND_EXTS = {".wav", ".mp3", ".ogg"}
    FONT_EXTS = {".ttf", ".otf"}
    # 暂不解析的格式：数据/文本类文件不进资源池
    SKIP_EXTS = {".reanim", ".xml", ".json", ".txt", ".md", ".ini"}

    def __init__(self) -> None:
        DEFAULT_SURFACE = _default_surface()
        DEFAULT_SOUND = pygame.mixer.Sound(buffer=b"\x00" * 44100)
        DEFAULT_FONT = _default_font()

        self.surfaces: dict[str, pygame.Surface] = {"default": DEFAULT_SURFACE}
        self.sounds: dict[str, pygame.mixer.Sound] = {"default": DEFAULT_SOUND}
        self.fonts: dict = {"default": DEFAULT_FONT}
        self._root: Path | None = None
        # M3：命名空间 -> 资源根目录（区分大小写原样保留）
        self._namespaces: Dict[str, Path] = {}

    def load_all(self, path) -> None:
        """注册本体命名空间资源根（assets/PVZpy/）。

        资源改为按需加载，启动不再全量 rglob 预加载。
        """
        root = Path(path)
        if not root.is_dir():
            logging.warning("资源目录不存在: %s", root)
            return
        self._root = root.resolve()
        # M3：本体命名空间 PVZpy 注册到该根；mod 命名空间由 register_namespace 注入
        self._namespaces[const.BUILTIN_NAMESPACE] = self._root
        logging.info(
            "AssetsManager ready (%d default surfaces, %d default sounds, "
            "%d default fonts); on-demand loading from %s",
            len(self.surfaces),
            len(self.sounds),
            len(self.fonts),
            self._root,
        )

    def register_namespace(self, namespace: str, root) -> None:
        """注册命名空间资源根（如 Mod 的 mods/<modid>/assets/）。

        同一命名空间重复注册以后者为准；命名空间区分大小写原样保留。
        """
        path = Path(root).resolve()
        self._namespaces[namespace] = path
        logging.debug("AssetsManager register namespace %s -> %s", namespace, path)

    def _file_for_key(self, key: str) -> Path | None:
        """将 posix key 映射为命名空间资源根下的文件；未命中返回 None。

        - key 携带命名空间（如 PVZpy/fonts/pvz2.ttf）时，按命名空间直接定位；
        - key 不带命名空间（如 fonts/pvz2.ttf）时，按默认命名空间解析：
          查找顺序 = Mod 命名空间根（注册顺序）-> 本体命名空间根（mod 覆盖原版）；
        - 兼容历史 key：若仍携带裸 assets/ 前缀则剥离，避免 assets/assets/ 回归。
        """
        if self._root is None:
            return None
        # 兼容历史 key：剥离裸 assets/ 前缀（回归防护）
        if key.startswith(f"{const.ASSETS_ROOT}/"):
            key = key[len(f"{const.ASSETS_ROOT}/"):]

        # 拆出命名空间段：首段命中已注册命名空间 => 按命名空间定位
        head, sep, tail = key.partition("/")
        if sep and head in self._namespaces:
            return self._resolve_in_root(self._namespaces[head], tail, key)

        # 默认命名空间解析：Mod 根优先（覆盖原版），本体根兜底
        mod_roots: List[Path] = [
            root for ns, root in self._namespaces.items()
            if ns != const.BUILTIN_NAMESPACE
        ]
        roots: List[Path] = [*mod_roots, self._namespaces[const.BUILTIN_NAMESPACE]]
        for root in roots:
            found = self._resolve_in_root(root, key, key)
            if found is not None:
                return found
        return None

    @staticmethod
    def _resolve_in_root(root: Path, rel: str, display_key: str) -> Path | None:
        """在单个命名空间根内解析相对路径；越界/不存在返回 None。"""
        candidate = (root / rel).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            logging.warning("资源 key 越界，拒绝加载: %s", display_key)
            return None
        if not candidate.is_file():
            return None
        return candidate

    def _try_load(self, key: str) -> bool:
        # 按需加载单个资源；跳过 SKIP_EXTS 格式
        file = self._file_for_key(key)
        if file is None:
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
            logging.warning(
                "Surface with key '%s' not found. Returning default surface.",
                key,
            )
            key = "default"
        return self.surfaces[key].copy()

    def get_sound(self, key):
        if key not in self.sounds:
            self._try_load(key)
        if key not in self.sounds:
            logging.warning(
                "Sound with key '%s' not found. Returning default sound.",
                key,
            )
            key = "default"
        return self.sounds[key].copy()

    def get_font(self, key):
        if key not in self.fonts:
            self._try_load(key)
        if key not in self.fonts:
            logging.warning(
                "Font with key '%s' not found. Returning default font.",
                key,
            )
            key = "default"
        return self.fonts[key]
