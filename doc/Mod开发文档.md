# PVZpy 模组开发文档

> 适用分支：`mod`。本文档基于当前 `src/mod/`、`src/assets_manager.py`、`src/game.py`、`src/Entities/loader.py`、`src/levels_manager.py` 与 `mods/example_mod/` 的真实实现撰写，所有 API 均以源码为准。

---

## 1. 概述与定位

PVZpy 内置一套轻量级 Mod 系统（M1~M5 分阶段落地），允许第三方在不改动本体源码的前提下：

- **订阅游戏生命周期事件**（预初始化 / 开始 / 每帧 / 停止）；
- **向全局注册表注册自定义内容**（自定义植物、僵尸、子弹、关卡）；
- **提供命名空间资源**（图片 / 声音 / 字体），并**覆盖原版资源**。

系统核心组成：

| 模块 | 职责 |
|---|---|
| `src/mod/mod_info.py` | `ModInfo` 元数据模型、`ModState` 状态枚举、`EntryPoints` |
| `src/mod/loader.py` | 扫描 `mods/`、解析 `mod.json`、导入入口类 |
| `src/mod/event_bus.py` | 轻量同步事件总线（订阅 / 发布 / 退订 / 优先级） |
| `src/mod/registry.py` | 泛型字符串键注册表（register / get / contains / all / disable） |
| `src/mod/mod_manager.py` | `ModManager`：统一编排 Mod 加载与生命周期回调 |
| `src/mod/events.py` | 内置生命周期事件名常量与事件 Payload |
| `src/mod/keys.py` | 本体可扩展内容在注册表中的键前缀约定与拼接函数 |

内置 `pvzpy` Mod 作为**第一个**被加载的 Mod（元数据外置于 `src/Vanilla.json`，见 2.1；代码不移动），外部 Mod 通常声明 `depends: ["pvzpy"]` 表示依赖本体。**启动顺序**：本体（pvzpy）最先初始化 → 外部 Mod 按 `mods/` 目录名字典序初始化 → 游戏随后启动（`run`）；每次启动加载顺序一致。

---

## 2. mods 目录约定与结构

Mod 系统从项目根目录下的 `mods/` 目录扫描外部 Mod（`ModManager(mods_dir)`，默认 `Path("mods")`；`Game._create_default_mod_manager` 使用 `const.PROJECT_ROOT / "mods"` 并自动创建目录）。

**发现规则**（`find_mod_dirs`）：`mods/` 下**每个直接子目录**，只要内含 `mod.json` 即视为一个 Mod；按目录名排序加载。目录名与 Mod `id`、命名空间均**区分大小写原样保留**。

标准目录结构：

```
mods/
└── <mod_id>/
    ├── mod.json              # 必填：Mod 元数据
    ├── <入口模块>.py         # 入口模块（entry_points.main 指向）
    ├── assets/               # 可选：命名空间资源根（图片/声音/字体）
    │   ├── images/...        # 通过「<mod_id>/images/...」访问（mod 命名空间）
    │   └── PVZpy/...         # 可选：放在 PVZpy/ 下可覆盖原版同名资源
    └── ...                   # 其他 Python 模块/子包
```

> 参考 `mods/example_mod/`：
> ```
> example_mod/
> ├── mod.json
> ├── example_mod.py
> └── assets/
>     ├── images/example_plant_card.png          # mod 命名空间资源
>     └── PVZpy/images/mod.png                   # 覆盖原版 PVZpy/images/mod.png
> ```

### 2.1 本体配置：`src/Vanilla.json`

游戏本体同样以"模组"形式登记，其元数据**外置**在项目根 `src/Vanilla.json`（`ModManager.VANILLA_JSON_PATH`）。`ModManager.boot` 启动时读取该文件构建内置条目（`id = "pvzpy"`、资源命名空间 `PVZpy`），不再依赖代码内硬编码元数据（代码中的内置常量仅作读取失败时的回退）。该文件**不含 `entry_points.main`**——本体代码不经 mod 入口实例化，ModManager 对本体走内置适配，仅读取元数据与资源声明。

```json
{
  "schema_version": 1,
  "id": "pvzpy",
  "friendly_name": "PVZpy",
  "version": "1.0.0",
  "version_code": 1,
  "authors": ["PVZpy Developers"],
  "description": "PVZpy 游戏本体（内置模组）",
  "website": "",
  "resources": {
    "assets": "assets/PVZpy",
    "levels": "src/Levels",
    "entities": "src/Entities"
  }
}
```

> 本体资源已命名空间化为 `assets/PVZpy`，故 `assets` 显式声明为 `assets/PVZpy`；`levels` / `entities` 指向本体实际目录。`resources` 字段说明见第 3.2 节与 7.0 节。

---

## 3. mod.json 字段说明

`mod.json` 为 UTF-8 JSON 对象。解析逻辑见 `loader.parse_mod_json`。

### 3.1 必填字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | Mod 唯一标识，**非空字符串**，区分大小写。缺失或为空 → `ModLoadError`，该 Mod 被跳过。重复 id 时后加载者被跳过（`ModManager.boot` 打 warning）。 |
| `entry_points.main` | string | 入口类全限定名，形如 `module.ClassName`（模块路径.类名）。类名取最后一段，前面的部分作为相对 Mod 目录的模块导入路径。缺失或不是该形式 → `ModLoadError`。 |

### 3.2 可选字段

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `schema_version` | int | `1` | 元数据 schema 版本。 |
| `friendly_name` | string | 同 `id` | 人类可读名称。 |
| `version` | string | `"1.0.0"` | 展示用版本号。 |
| `version_code` | int | `1` | 程序比较用版本号。 |
| `authors` | string[] | `[]` | 作者列表；非数组会报 `ModLoadError`。 |
| `description` | string | `""` | 描述。 |
| `website` | string | `""` | 主页。 |
| `depends` | string[] | `[]` | 依赖的 Mod id 列表（当前仅记录，不强制解析依赖图）。 |
| `resources` | object | `{}` | **可选**。各类型资源相对路径声明，键限定为 `assets` / `levels` / `entities`，值为相对该 Mod 目录（本体相对项目根）的 posix 路径。键取值非法或值非字符串 → `ModLoadError`。未声明的类型走默认约定（见 7.0 节）。 |

> 注：当前实现**不做依赖解析/冲突检测**，`depends` 作为元数据记录；推荐至少声明 `["pvzpy"]`。

### 3.3 完整示例（取自 `mods/example_mod/mod.json`）

```json
{
  "schema_version": 1,
  "id": "example_mod",
  "friendly_name": "Example Mod",
  "version": "1.0.0",
  "version_code": 1,
  "authors": ["PVZpy Developers"],
  "description": "M5 示例 Mod：演示事件订阅、注册表注册自定义植物与关卡、资源覆盖原版的全链路。",
  "website": "",
  "entry_points": {"main": "example_mod.ExampleMod"},
  "depends": ["pvzpy"]
}
```

> 该示例**未声明** `resources`，`assets` / `levels` / `entities` 分别自动走默认约定 `assets/`、`src/Levels/`、`src/Entities/`（相对 mod 目录）。

---

## 4. 入口类与生命周期回调

### 4.1 入口类约定

入口类为普通 Python 类，`loader.load_entry_point` 导入模块后**无参实例化**（`cls()`）。入口类**建议实现**三个回调（未实现时视为空操作，状态照常推进）：

| 回调 | 时机 | 典型用途 |
|---|---|---|
| `on_pre_init(manager)` | boot 时按加载顺序调用 | 订阅事件总线、保存 manager 引用 |
| `on_init(manager)` | `on_pre_init` 全部完成后按加载顺序调用 | 注册实体 / 关卡 / 服务到注册表 |
| `on_shutdown(manager)` | shutdown 时**按加载逆序**调用 | 退订事件、清理资源 |

`manager` 为 `ModManager` 实例，提供：

- `manager.event_bus`：`EventBus`
- `manager.registry`：`Registry`
- `manager.mods`：`Dict[str, ModEntry]`（id → 条目）
- `manager.loaded`：按加载顺序的 `List[ModEntry]`
- `manager.get(mod_id)` / `manager.builtin` / `manager.booted`

### 4.2 boot 时序（`ModManager.boot`）

```
boot()
├─ 1. 读取 src/Vanilla.json 构建内置 pvzpy Mod（本体最先加载；读取失败回退内置默认元数据）
├─ 2. 扫描 mods/ 按目录名排序加载外部 Mod（load_mod_from_dir）
│     ├─ ModLoadError → 跳过并打 warning（不中断其它 Mod）
│     └─ id 重复 → 跳过并打 warning
├─ 3. 计算各 Mod 三类资源目录（assets/levels/entities，声明或默认）并收集分发列表，
│     由游戏装配阶段交给 AssetsManager / LevelsManager / EntitiesManager（见 7.0）
├─ 4. 按加载顺序逐个调用 on_pre_init(manager)     → 状态 PRE_INIT
├─ 5. 按加载顺序逐个调用 on_init(manager)          → 状态 ACTIVE
└─ booted = True
```

- 加载顺序**每次启动一致**：本体优先 → 外部 Mod 按 `mods/` 目录名字典序；`manager.loaded` 与资源分发表均按此顺序。

- 回调**未实现**：视为空操作，直接置为成功状态。
- 回调**抛异常**：该 Mod 状态置为 `FAILED`、记录 `error`，`log.exception` 记录，**不中断其它 Mod**（见 `ModManager._call_callback`）。

### 4.3 shutdown 时序（`ModManager.shutdown`）

```
shutdown()
└─ 按加载逆序（reversed(loaded)）逐个调用 on_shutdown(manager) → 状态 SHUTDOWN
```

游戏侧（`Game.run`）退出顺序为：发布 `GAME_STOP` → `saves.save()` → `mod_manager.shutdown()` → `pygame.quit()`。

### 4.4 Mod 状态（`ModState`）

`DISCOVERED` → `LOADED` → `PRE_INIT` → `ACTIVE`；回调异常 → `FAILED`；shutdown 后 → `SHUTDOWN`。

---

## 5. 事件总线

### 5.1 API（`EventBus`）

| 方法 | 签名 | 说明 |
|---|---|---|
| 订阅 | `subscribe(event, handler, priority=0) -> Token` | 返回 token 用于退订。`priority` 数字越小越先执行（默认 0）；同优先级按订阅先后执行。 |
| 发布 | `publish(event, *args, **kwargs)` | 按优先级升序同步调用全部处理器。 |
| 退订 | `unsubscribe(token_or_handler) -> bool` | 按 token（int）或处理器引用退订；成功返回 True。 |
| 清空 | `unsubscribe_all(event=None) -> int` | 清空某事件（或全部）处理器，返回退订条数。 |
| 统计 | `handler_count`（属性） | 当前注册处理器总数。 |

事件总线为**单线程同步**模型：publish 期间处理器内异常**会向上抛出**；游戏侧在发布时用 `Game._publish_safe` 包裹，使 Mod 处理器异常不会拖垮本体逻辑。

### 5.2 内置生命周期事件（`src/mod/events.py`）

| 事件常量 | 触发时机 | Payload |
|---|---|---|
| `GAME_PRE_INIT = "game_pre_init"` | `Game.__init__`：Mod 系统已 boot、GameContext 已构造、资源加载前 | `GamePreInitPayload(context)` |
| `GAME_START = "game_start"` | `Game.run` 主循环开始、第一帧渲染前 | `GameStartPayload(context)` |
| `GAME_FRAME = "game_frame"` | 主循环每帧更新/渲染完成后 | `GameFramePayload(dt, game)` |
| `GAME_STOP = "game_stop"` | 主循环退出后、存档与 Mod 卸载前 | `GameStopPayload(context)` |

Payload 字段：

- `GamePreInitPayload.context` / `GameStartPayload.context` / `GameStopPayload.context`：`GameContext`（含 `game`、`assets`、`entities`、`levels`、`saves`、`scene_manager`、`mod_manager`、`event_bus`、`registry`）。
- `GameFramePayload.dt`：帧间隔（秒，`clock.tick(FPS)/1000.0`）；`GameFramePayload.game`：`Game` 实例。

### 5.3 示例：订阅与退订（取自 `example_mod`）

```python
def on_pre_init(self, manager) -> None:
    self.manager = manager
    bus = manager.event_bus
    self._tokens.append(bus.subscribe(events.GAME_PRE_INIT, self._on_pre_init))
    self._tokens.append(bus.subscribe(events.GAME_START, self._on_game_start))
    self._tokens.append(bus.subscribe(events.GAME_FRAME, self._on_frame, priority=10))
    self._tokens.append(bus.subscribe(events.GAME_STOP, self._on_stop))

def on_shutdown(self, manager) -> None:
    for token in self._tokens:
        manager.event_bus.unsubscribe(token)
    self._tokens.clear()
```

---

## 6. 注册表

### 6.1 API（`Registry`）

| 方法 | 签名 | 说明 |
|---|---|---|
| 注册 | `register(key, value, *, replace=False) -> bool` | key 已存在且 `replace=False` 时返回 False（不覆盖）。成功后自动解除禁用。 |
| 查询 | `get(key) -> Optional[T]` | 未注册**或已禁用**返回 None。 |
| 包含 | `contains(key) -> bool` | 是否已注册（**含禁用项**）。 |
| 全量 | `all() -> Dict[str, T]` | 全部注册项（含禁用项）的拷贝。 |
| 禁用 | `disable(key) -> bool` | 禁用某项（保留注册关系，`get` 不再返回）；未注册返回 False。 |
| 可用键 | `enabled_keys`（属性） | 当前未禁用的 key 列表。 |

key **区分大小写原样保留**。

### 6.2 内置键约定（`src/mod/keys.py`）

| 前缀常量 | 键形 | 用途 |
|---|---|---|
| `KEY_ENTITY_PLANT = "entity.plant."` | `entity.plant.<ClassName>` | 植物类 |
| `KEY_ENTITY_ZOMBIE = "entity.zombie."` | `entity.zombie.<ClassName>` | 僵尸类 |
| `KEY_ENTITY_BULLET = "entity.bullet."` | `entity.bullet.<ClassName>` | 子弹类 |
| `KEY_LEVEL = "level."` | `level.<part>-<level>` | 关卡（如 `level.9-9`） |

推荐使用拼接函数：`entity_plant_key(name)` / `entity_zombie_key(name)` / `entity_bullet_key(name)` / `level_key(level_id)`。

### 6.3 注册表与本体的对接

- **实体**（`src/Entities/loader.py`）：启动时 `register_builtin_entities(registry)` 将本体全部实体类注册到注册表；游戏逻辑经 `all_plant_classes(registry)` / `all_zombie_classes(registry)` / `all_bullet_classes(registry)` 查询（注册表视角：仅含 `type` 值、去重、跳过禁用项），**无注册表或无注册项时回退本体内置清单**。构造键也可用 `entity_key_for("plant", name)`。
- **关卡**（`src/levels_manager.py`）：`LevelsManager(registry=...)`；启动时 `register_builtin_levels(registry)` 注册本体关卡。`list_levels()` 合并注册表与内置关卡（同 id 注册表优先）；`get_level_by_id(id)` **先查注册表、未命中回退内置**。注册表值支持 `Level` 实例或**可解析为 Level 的 dict**（dict 由 `_parse_level` 解析，path 标为 `registry:<key>`）。

### 6.4 示例：注册自定义植物与关卡（取自 `example_mod`）

```python
from src.Entities.Plant import Plant
from src.levels_manager import Level, LevelWave
from src.mod.keys import entity_plant_key, level_key

class ExamplePlant(Plant):
    COST = 25
    def __init__(self, row=1, col=0):
        super().__init__(row, col)
        self.can_attack = False

def on_init(self, manager) -> None:
    reg = manager.registry
    reg.register(entity_plant_key("ExamplePlant"), ExamplePlant)
    reg.register(
        level_key("9-9"),
        Level(
            part=9, level=9, title="Example Mod 关卡",
            rows=[1] * 5,
            default_plants=["PeaShooter", "ExamplePlant"],
            default_sun=150,
            zombie_types=["Zombie"],
            waves=[LevelWave(delay=60, count=2, zombie_type="Zombie")],
            path="registry:level.9-9",
        ),
    )
```

> 覆盖本体内容需显式 `register(key, value, replace=True)`（在明确授权下使用）。

---

## 7. 资源系统

### 7.0 资源目录声明与分发（`resources`）

每个 Mod（含本体）可通过 `mod.json` / `src/Vanilla.json` 的 `resources` 字段声明三类资源的**相对路径**（相对该 Mod 所在目录；本体相对项目根）。未声明的类型走**默认约定**：

| 类型 | 键 | 默认约定（未声明时） |
|---|---|---|
| 通用资源（图片 / 音频 / 字体） | `assets` | `<mod_dir>/assets` |
| 关卡目录 | `levels` | `<mod_dir>/src/Levels` |
| 实体目录 | `entities` | `<mod_dir>/src/Entities` |

`ModManager.boot` 完成加载后按**加载顺序**（本体优先 + 目录序）收集三类路径，可通过以下 API 获取：

- `manager.resource_dirs(kind)`：`kind ∈ {"assets","levels","entities"}`，返回该类型的路径列表 `List[Path]`；
- `manager.resource_dirs_by_mod()`：返回 `Dict[str, Dict[str, Path]]`（`mod_id → {kind: Path}`）。

游戏侧 `Game.__init__` 装配阶段分发：

- `AssetsManager`：对每个 Mod 的 `assets` 路径调用 `register_namespace(mod_id, assets_dir)`（本体为 `assets/PVZpy`），使 Mod 资源可按命名空间解析并覆盖原版；
- `LevelsManager.load_roots([...])`：依次加载各 Mod 的 `levels` 目录，同名关卡 id 后加载者覆盖；
- `EntitiesManager(resource_dirs=[...])`：接收各 Mod 的 `entities` 目录（当前实体类仍以源码导入包收集为主，目录参数供扩展预留）。

**向后兼容**：未声明 `resources` 的既有 Mod（如 `mods/example_mod`、`mods/PVZpy_Debugger`）自动走默认约定，无需修改其 `mod.json`。

### 7.1 命名空间

`AssetsManager` 以**命名空间**组织资源根。常量 `const.BUILTIN_NAMESPACE = "PVZpy"`，本体资源根为 `const.ASSETS_BUILTIN_DIR`（`assets/PVZpy/`）。

- `load_all(path)`：注册**本体命名空间** `PVZpy` 到资源根，资源**按需加载**（不再全量预加载）。
- `register_namespace(namespace, root)`：注册命名空间资源根；游戏装配阶段按 7.0 分发对各 Mod 调用 `register_namespace(mod_id, <assets 路径>)`。同一命名空间重复注册**以后者为准**；命名空间区分大小写原样保留。

### 7.2 资源 key 与解析规则（`_file_for_key`）

key 为 posix 路径，两种形式：

1. **带命名空间**：`<namespace>/<类型>/<资源>`（如 `PVZpy/fonts/pvz2.ttf`、`example_mod/images/example_plant_card.png`）——首段命中已注册命名空间时直接定位到对应根。
2. **不带命名空间**（如 `images/mod.png`）：按「**默认命名空间解析**」——依次查找各 Mod 命名空间根（按注册顺序），最后回退本体命名空间根，即 **Mod 资源可覆盖原版资源**。

**M5 覆盖规则**：key 首段为**本体命名空间** `PVZpy` 时（如 `PVZpy/images/mod.png`），若存在 `mods/<mod_id>/assets/PVZpy/<tail>` 则**优先返回 Mod 覆盖文件**（按 Mod 注册顺序），未命中再回退本体 `assets/PVZpy/<tail>`。

**历史兼容**：key 若携带裸 `assets/` 前缀会自动剥离，避免 `assets/assets/` 回归。

**路径越界防护**：`_resolve_in_root` 将解析结果 `.resolve()` 后校验是否仍位于命名空间根内，越界则拒绝加载（打 warning）。

### 7.3 资源访问 API

| 方法 | 用途 |
|---|---|
| `get_surface(key)` | 获取图片 Surface（支持 `.png/.jpg/.jpeg/.bmp/.gif`） |
| `get_sound(key)` | 获取声音（支持 `.wav/.mp3/.ogg`） |
| `get_font(key)` | 获取字体（支持 `.ttf/.otf`） |

`SKIP_EXTS = {.reanim, .xml, .json, .txt, .md, .ini}` 不进入资源池。

### 7.4 覆盖示例（取自 `example_mod`）

- `mods/example_mod/assets/images/example_plant_card.png` → 通过 key `example_mod/images/example_plant_card.png` 访问；
- `mods/example_mod/assets/PVZpy/images/mod.png` → 覆盖原版 `PVZpy/images/mod.png`。

---

## 8. 从零开始写一个 Mod（分步教程）

以 `example_mod` 为模板，实现一个注册自定义植物与关卡、订阅事件的 Mod。

**第 1 步：建目录与 mod.json**

在 `mods/<mod_id>/` 下创建 `mod.json`（字段见第 3 节），至少包含非空 `id` 与 `entry_points.main`：

```json
{
  "schema_version": 1,
  "id": "my_mod",
  "friendly_name": "My Mod",
  "version": "1.0.0",
  "version_code": 1,
  "authors": ["Me"],
  "description": "",
  "website": "",
  "entry_points": {"main": "my_mod.MyMod"},
  "depends": ["pvzpy"]
}
```

**第 2 步：编写入口类**

`mods/my_mod/my_mod.py`：

```python
from src.mod import events

class MyMod:
    def __init__(self):
        self._tokens = []

    def on_pre_init(self, manager) -> None:
        self.manager = manager
        self._tokens.append(manager.event_bus.subscribe(events.GAME_START, self._on_start))

    def on_init(self, manager) -> None:
        # 注册自定义内容：manager.registry.register(...)
        pass

    def on_shutdown(self, manager) -> None:
        for token in self._tokens:
            manager.event_bus.unsubscribe(token)
        self._tokens.clear()

    def _on_start(self, payload):
        # 读取 GameContext：payload.context
        pass
```

**第 3 步：注册自定义植物与关卡**

参考 6.4 节：在 `on_init` 中用 `entity_plant_key(...)` / `level_key(...)` 注册 `Plant` 子类与 `Level`（或可解析 dict）。

**第 4 步：添加资源（可选）**

- 在 `mods/my_mod/assets/` 下放资源；
- 通过 `mods/my_mod/assets/images/xxx.png` → key `my_mod/images/xxx.png` 访问；
- 要覆盖原版，放到 `mods/my_mod/assets/PVZpy/<同路径>`（见 7.4）。

**第 5 步：验证**

直接启动游戏（`python main.py`），或运行调试脚本（见第 9 节）。观察日志确认 `Mod my_mod` 状态推进、注册成功。

---

## 9. 调试技巧

### 9.1 测试与冒烟脚本

| 脚本 | 内容 | 运行方式 |
|---|---|---|
| `tools/test_mod_system.py` | 49 项 mod 系统单测（含 M4 注册表对接、M5 示例 Mod） | `python -m unittest tools.test_mod_system` 或直接 `python tools/test_mod_system.py` |
| `tools/test_entities.py` | 74 项实体单测 | 同上方式 |
| `tools/smoke_mod_system.py` | 60 帧无头（dummy SDL）冒烟：验证 mod 加载 / 事件 / 注册表 / 资源覆盖，含 11 项检查点 | `python tools/smoke_mod_system.py` |

> 无头环境需先 `set_mode`（dummy SDL）；冒烟脚本将存档隔离到临时目录。

### 9.2 常见报错与排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 日志 `Mod 加载失败 <dir>: ...` | `mod.json` 解析失败、`id` 缺失/非字符串、`entry_points.main` 缺失/非 `module.ClassName`、入口导入/实例化异常 | 检查 `mod.json` 字段与入口类路径；确认入口类可无参实例化 |
| 日志 `Mod id 重复，跳过` | 两个 Mod 声明相同 `id` | 修改其中一个 `id`（区分大小写） |
| 回调抛异常，Mod 状态 `FAILED` | `on_pre_init`/`on_init`/`on_shutdown` 内异常 | 查看 `log.exception` 堆栈；异常不会拖垮其它 Mod |
| `registry.register(...)` 返回 False | key 已存在且未用 `replace=True` | 换 key 或显式 `replace=True` |
| `assets.get_surface("xxx")` 返回默认占位图 | key 未命中（路径错误 / 文件不存在 / 越界被拒） | 核对命名空间与文件扩展名（见 7.2/7.3）；检查日志中的越界 warning |
| 覆盖原版不生效 | 覆盖文件路径未放对（需 `assets/PVZpy/<tail>`）或 Mod 注册顺序靠后 | 按 7.2 规则放置；多个 Mod 覆盖同一资源时先注册者优先 |
| 自定义关卡找不到 | 注册键不是 `level.<part>-<level>`，或值既非 `Level` 也非可解析 dict | 用 `level_key(...)` 拼接；dict 需包含可解析字段（参考 `_parse_level`） |
| 事件处理器未触发 | 事件名拼写错误 / 未在 `on_pre_init` 订阅（或订阅在发布之后） | 使用 `events` 常量；在 `on_pre_init` 订阅，`GAME_PRE_INIT` 之外的事件均在其后发布 |
| 入口模块导入报错 | 相对路径问题 | 入口模块相对 Mod 目录解析；`inject_sys_path` 已把 Mod 目录加入 `sys.path`（幂等） |

### 9.3 开发建议

- 在 `on_pre_init` 中订阅全部所需事件（此时 `GAME_PRE_INIT` 尚未发布）。
- 保存订阅 token，在 `on_shutdown` 中退订，避免重复订阅。
- 自定义内容用拼接函数生成注册键，避免手写字符串出错。
- 修改后重启游戏验证；无头冒烟脚本可快速回归。
