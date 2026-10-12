# 资源 key 与场景名常量（M3 资源命名空间化）。
# 资源 key 为「命名空间/类型/资源」posix 路径（如 PVZpy/fonts/pvz2.ttf），
# 本体命名空间为 PVZpy（大小写保留），对应资源根 assets/PVZpy/；
# Mod 命名空间为 mods/<modid>/，对应资源根 mods/<modid>/assets/。
# key 不再携带裸 assets/ 前缀，避免 _file_for_key 拼接出 assets/assets/... 而回退默认。
# 文件系统路径统一基于 PROJECT_ROOT 构造，不依赖进程 cwd。
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ASSETS_ROOT = "assets"
# M3：本体资源命名空间（大小写保留）；迁移后本体资源位于 assets/PVZpy/ 下
BUILTIN_NAMESPACE = "PVZpy"
LEVELS_ROOT = "src/Levels"
IMAGES = f"{BUILTIN_NAMESPACE}/images"
AUDIO_SFX = f"{BUILTIN_NAMESPACE}/audio/sfx"
FONTS = f"{BUILTIN_NAMESPACE}/fonts"

# 文件系统目录（基于项目根）
ASSETS_DIR = PROJECT_ROOT / ASSETS_ROOT
# M3：本体命名空间资源根（assets/PVZpy/），由 AssetsManager.load_all 注册
ASSETS_BUILTIN_DIR = ASSETS_DIR / BUILTIN_NAMESPACE
LEVELS_DIR = PROJECT_ROOT / LEVELS_ROOT
SAVES_DIR = PROJECT_ROOT / "saves"

FONT_PVZ = f"{FONTS}/pvz2.ttf"
SFX_BUTTON_CLICK = f"{AUDIO_SFX}/buttonclick.ogg"

SCENE_LOADING = "LoadingScene"
SCENE_MAIN_MENU = "MainMenu"
SCENE_SELECT_PLANT = "SelectPlantScene"
SCENE_ADVENTURE = "AdventureScene"

# 本场最多带入植物数
MAX_PLANTS = 10

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# 阳光
START_SUN = 50
SUN_FALL_INTERVAL = 8.0  # 天空落阳光间隔（秒）

# 胜负：僵尸中心 x 低于此值判负（草坪左缘外）
LOSE_X = 40

# 冒险关卡波次：(出现秒, 数量, 行号或 None=随机)
LEVEL_ADVENTURE_1 = (
    (4.0, 1, 2),
    (12.0, 2, None),
    (22.0, 2, None),
    (35.0, 3, None),
    (50.0, 4, None),
)

# 草坪网格（水平居中）
GRID_ROWS = 5
GRID_COLS = 9
CELL_W = 70
CELL_H = 80
GRID_X = 85   # (800 - 9*70) / 2
GRID_Y = 130

# 地图类型 / 行类型（关卡 JSON 的 type、rows）
MAP_DAY = "Day"
ROW_DISABLED = 0  # 禁用：不叠加内容，不可种植/刷怪
ROW_LAWN = 1      # 草坪
ROW_POOL = 2      # 泳池
# 其他行类型预留

# 顶部植物条
SEED_W = 140
SEED_H = 44
SEED_Y = 64

# 简易 UI 配色
UI_BG = (18, 22, 28)
UI_PANEL = (32, 40, 52)
UI_ACCENT = (76, 160, 90)
UI_TEXT = (230, 230, 230)
UI_TEXT_DIM = (150, 155, 165)
UI_HOVER = (52, 70, 88)
UI_BORDER = (70, 85, 105)
GRID_CELL_A = (48, 72, 48)
GRID_CELL_B = (40, 62, 40)
GRID_LINE = (30, 48, 30)
PLANT_FILL = (86, 170, 70)
ZOMBIE_FILL = (180, 70, 60)
BULLET_FILL = (220, 200, 80)
