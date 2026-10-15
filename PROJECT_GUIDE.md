# PVZpy 项目交接文档（PROJECT_GUIDE）

> 本文档面向任何新对话 / 新维护者，读完即可无缝接手本项目。内容基于仓库真实现状与历史开发沉淀撰写，所有 commit hash、测试数字、目录路径均与当前仓库（`ui` 分支，HEAD=`ff3fc1d`）核对一致。
>
> 最后更新：2026-10-15（`docs: 新增PROJECT_GUIDE项目交接文档`）

---

## 1. 项目概览

| 项 | 值 |
|---|---|
| 项目名称 | PVZpy |
| 项目定位 | 基于 pygame-ce 的《植物大战僵尸》复刻版（Python 实现） |
| GitHub 仓库 | `Potato4096/PVZpy`（远程分支：origin/dev 等，近期改动未 push，见 §6） |
| 本地路径 | `C:\Users\Potato\Desktop\PVZpy` |
| 操作系统 | Windows 11（Build 26100），PowerShell 5.1 |
| 开发环境 | Python 3.11.8（系统）/ `.venv` 虚拟环境 Python 3.14.7 + pygame-ce 2.5.8（SDL 2.32.10） |
| 用户 | Potato / Potato4096 |
| 入口 | `main.py`（项目根，任意 cwd 可启动，依赖路径已根化） |

### 根目录结构

```
assets/PVZpy/        本体资源（已命名空间化，见 §4.7）
doc/Mod开发文档.md     Mod 系统开发文档（653be7a 提交）
mods/example_mod/     M5 参考示例 mod（勿删，测试依赖）
mods/PVZpy_Debugger/  调试器 mod
saves/                存档目录（git 忽略）
src/                  源码
tools/                测试与冒烟脚本
main.py / requirements.txt / setup.cfg
```

### `src/` 模块清单

| 文件 | 职责 |
|---|---|
| `main.py` | 入口：`ModManager.boot()` 后构造并运行 `Game` |
| `src/context.py` | `GameContext` 依赖注入容器（详见 §3.1） |
| `src/game.py` | 游戏主循环、事件发布、资源装配分发 |
| `src/assets_manager.py` | 资源按需加载、命名空间解析（详见 §3.4 / §4.7） |
| `src/entities_manager.py` | 实体管理（生成、碰撞、更新） |
| `src/levels_manager.py` | 关卡加载（`load_roots` / `register_builtin_levels`） |
| `src/saves_manager.py` | 存档原子写、版本迁移框架 |
| `src/scene_manager.py` | 场景管理基类与流转 |
| `src/gui.py` | 轻量 UI 组件（Button 等，91 行，部分代码不合规，见 §6 待办） |
| `src/const.py` | 常量（含 `BUILTIN_NAMESPACE = "PVZpy"`） |
| `src/Vanilla.json` | 本体作为内置 mod 的元数据（id=`pvzpy`，见 §4.6） |
| `src/scenes/` | 场景：`mainmenu` / `select_plant` / `adventure` / `loading` |
| `src/Entities/` | 实体基类与子类（Plants / Zombies / Bullets）+ `loader.py` 统一入口 |
| `src/Levels/` | 关卡 JSON（当前仅 `1-1.json`） |
| `src/mod/` | Mod 系统（event_bus / registry / mod_manager / loader / mod_info / events / keys） |

---

## 2. 开发规则与约定

### 2.1 代码规范

- 遵循 PEP8 与 Pygame 惯例；`setup.cfg` 配置 flake8 `max-line-length = 120`。
- 沿途遇到不合规代码可顺手修正（保持逻辑不变），修正随本次 commit 一并提交。
- 已知遗留：`src/gui.py` 部分代码不合规，尚未修正（见 §6 待办）。

### 2.2 提交规则

- **每次逻辑完整更改后 git commit 一次**，commit message 含更改类型 + 内容，例如：
  - `fix: 路径根化：资源/关卡/存档/日志路径基于项目根，解耦 cwd 依赖`
  - `feat: mod系统M3资源命名空间化`
  - `refactor: 以 GameContext 显式依赖注入替代 GLOBAL_REFERENCE 全局引用`
  - `style: PVZpy_Debugger调试面板样式调整`
  - `docs: 新增模组开发文档`
  - `chore: 移除无用代码与残留`
- 任务/轮完成应 push 远程；**当前本地 20 个提交未 push**（清单见 §6）。

### 2.3 commit 前后双重验证法（既定流程，必须遵守）

1. 改码后验证：`python -m py_compile`（语法）→ 单测（`tools/test_mod_system.py` + `tools/test_entities.py`）→ 冒烟（`tools/smoke_mod_system.py`，且**冒烟需包含本次行为的断言**）。
2. `git add` 精确文件（逐个列出，不 `git add .`）。
3. `git status` 确认无夹带文件。
4. `git commit -m "..."`。
5. commit 后：`git status` 干净 + `git log` 确认落库 + 重跑验证（可选复跑冒烟）。

### 2.4 历史踩坑（务必避免复发）

| 坑 | 现象 | 规避 |
|---|---|---|
| commit 成功 ≠ 行为生效 | 代码已提交但运行行为未变 | 提交后必须重跑验证（冒烟/单测）确认真实生效 |
| 资源 key 前缀重复 | key 出现 `assets/assets/...` 导致按需加载回退默认资源 | 资源 key 一律相对 `ASSETS_DIR` 的 posix 路径，禁带裸 `assets/` 前缀（54ee2be 修复） |
| M5 命名空间注册时机 | 示例 mod 自定义实体/关卡未在正确时机注册 | 在 mod 入口 `game_pre_init`/启动阶段完成 Registry 注册，命名空间注册先于资源访问 |
| 自动化 git push 失败 | wincredman 凭据问题导致自动 push 失败 | **改为人工推送**，本地任务一律不自动 push |
| 同文件并发 edit 丢改 | 对同一文件并行 edit_file，后写覆盖先写，diff 显示成功但实际未落地 | 同一文件的多处修改必须串行执行；改完用 grep/import 校验符号确实存在 |
| 存量测试依赖 example_mod | `mods/example_mod` 被删后 `test_mod_system.py` 出现 failure/errors | 勿删 example_mod；若被外部删除用 `git restore mods/example_mod` 恢复基线 |

---

## 3. 架构设计思路

### 3.1 GameContext 依赖注入（替代 GLOBAL_REFERENCE）

重构后 `src/context.py` 用 `GameContext` dataclass 显式聚合全部管理器，替代模块级裸全局可变单例 `GLOBAL_REFERENCE`：

- 六个必填字段：`game` / `assets` / `entities` / `levels` / `saves` / `scene_manager`
- 三个可选字段（M2 新增，默认 `None`）：`mod_manager` / `event_bus` / `registry`
- 依赖方向：`Game` 负责构造 context 并向下注入；场景等只从 context 取用所需管理器
- `context.py` 仅用 `TYPE_CHECKING` 做类型引用，运行期零导入，切断 manager / 场景之间的循环依赖（commit：`fed15c2`）

### 3.2 场景状态机枚举化

- `src/scenes/adventure.py` 对局内部状态机使用 `GameState(Enum)` 枚举化（`from enum import Enum, auto`），替代魔法数字/字符串分支（commit：`ab74657`）。
- 场景基类在 `src/scene_manager.py`，四个场景：`mainmenu` / `select_plant` / `adventure` / `loading`。

### 3.3 实体加载统一入口

- `src/Entities/loader.py`：`_ENTITY_PACKAGES = (Plants, Zombies, Bullets)` 三个实体包。
- `_load_all_entity_modules()` 导入包下全部模块触发子类注册；`_entity_classes()` 用 `lru_cache` 缓存各基类（Plant / Zombie / Bullet）的子类清单，`register_builtin_entities` 统一注册（commit：`2004865`）。

### 3.4 资源按需加载与路径根化

- **路径根化**：资源/关卡/存档/日志路径全部基于 `Path(__file__).resolve()` 推导项目根，解除 cwd 绑定（commit：`b748c43`）；任意 cwd 运行 `main.py` 均正常。
- **按需加载**：`AssetsManager` 全量预加载改为首次访问 `get_surface` / `get_sound` 惰性加载 + 缓存；目录级排除 reanim 动画帧（commit：`cd78127`）。
- **资源 key**：为相对 `ASSETS_DIR` 的 posix 路径（如 `PVZpy/fonts/pvz2.ttf`），经 `_file_for_key` 解析定位（详见 §4.7 命名空间规则）。

### 3.5 持久化架构

- 存档原子写：临时文件写入 + `os.replace` 原子替换，损坏时保留 `.bak`（commit：`87796ae`）。
- 胜负判定后立即落盘（非仅退出时保存）；版本迁移框架（v0 → v1 补齐模板字段）。

---

## 4. Mod 系统设计

### 4.1 概览

Mod 系统采用 **Fabric 风格事件总线 + 泛型注册表 + 生命周期钩子** 的设计，分阶段实现：M1 基础设施 → M2 启动接入 → M3 资源命名空间化 → M4 注册表对接 → M5 示例 mod（提交见 §5 时间线）。详细规范见 `doc/Mod开发文档.md`。

### 4.2 事件总线（`src/mod/event_bus.py`）

- API：`subscribe(event, callback, priority)` / `publish(event, *args, **kwargs)` / `unsubscribe(...)`。
- **同步发布**，按优先级顺序调用回调；单个回调异常被隔离，不影响其它回调与主流程。
- Fabric 风格：解耦 mod 与本体，mod 通过订阅事件挂接生命周期。

### 4.3 注册表（`src/mod/registry.py`）

- 泛型 `Registry`：`register(key, value, replace=False)`（默认拒绝重复注册；`replace=True` 显式授权覆盖）、`get` / `contains` / `all` / `len` / `disable`，键区分大小写。
- 键约定（`src/mod/keys.py`）：`entity.plant.<ClassName>` / `entity.zombie.<ClassName>` / `entity.bullet.<ClassName>` / `level.<part>-<level>`。

### 4.4 mod 管理器（`src/mod/mod_manager.py`）

- `boot()`：**先初始化本体（Vanilla.json，id=pvzpy）→ 再按目录名字典序初始化外部 mod → 之后游戏启动（run）**。
- `shutdown()`：游戏退出时卸载。
- `ModManager.resource_dirs(kind)` / `resource_dirs_by_mod`：按类型收集各 mod 声明的资源路径列表（见 §4.7）。

### 4.5 生命周期事件（`src/mod/events.py`）

| 事件 | 触发时机 | Payload 关键字段 |
|---|---|---|
| `game_pre_init` | Mod 系统已 boot、GameContext 已构造、资源加载前 | `context` |
| `game_start` | 游戏主循环开始（第一帧渲染前） | `context` |
| `game_frame` | 每帧更新/渲染完成后 | `dt` / `game` |
| `game_pre_flip` | 每帧绘制完成后、`display.flip` 之前（供调试 UI 覆盖层） | `dt` / `game` |
| `game_event_loop` | 每帧事件循环消费 pygame 事件队列之前（可用 `pygame.event.peek()` 非破坏性查看） | `game` |
| `game_stop` | 游戏主循环退出后、存档与 Mod 卸载前 | `context` |

Payload 均为 frozen dataclass，字段默认值见 `events.py`。

### 4.6 mod.json 字段（`src/mod/loader.py` 解析）

| 字段 | 说明 |
|---|---|
| `schema_version` | 配置版本（当前 1） |
| `id` | 唯一标识，区分大小写原样保留 |
| `friendly_name` | 显示名 |
| `version` / `version_code` | 版本号 / 版本码 |
| `authors` / `description` / `website` | 元信息 |
| `entry_points.main` | mod 入口类路径（`<模块>.<类>`），本体无此字段 |
| `depends` | 依赖 mod id 列表（通常 `["pvzpy"]`） |
| `resources` | 可选；声明各类型资源相对路径（见 §4.7），未声明走默认约定 |

参考模板：`mods/example_mod/mod.json`（**存量测试依赖，勿删**）。

### 4.7 本体外置与资源声明分发（`ff3fc1d` 提交）

- **本体外置**：`src/Vanilla.json` 声明本体为内置 mod——`id="pvzpy"`、**无 entry_points.main**（本体代码不走 mod 入口实例化，ModManager 对本体走内置适配，仅读元数据与资源声明）。
- **资源类型**：`RESOURCE_TYPES = {assets, levels, entities}`；默认约定 `DEFAULT_RESOURCE_DIRS`：未声明类型走 `assets/` / `src/Levels/` / `src/Entities/`（本体 `Vanilla.json` 显式声明 `assets=assets/PVZpy`、`levels=src/Levels`、`entities=src/Entities`）。
- **分发**：boot 时收集所有已加载 mod 的分类型资源路径列表，装配分发——`register_namespace`（AssetsManager）、`load_roots`（LevelsManager）、`EntitiesManager(resource_dirs=...)` 构造入参。
- **启动顺序**：本体最先 → 外部 mod 目录序 → 游戏 run；加载顺序与初始化顺序一致。

### 4.8 资源命名空间规则（M3，`d8cd6fb`）

- 常量：`BUILTIN_NAMESPACE = "PVZpy"`；本体资源位于 `assets/PVZpy/`，mod 资源位于 `mods/<modid>/assets/`。
- 资源 key 形如 `PVZpy/fonts/pvz2.ttf`：**首段命中已注册命名空间则直接定位；否则在 Mod 资源根优先查找（可覆盖原版）**。
- 解析时剥离裸 `assets/` 前缀（防 `assets/assets/` 回归，`54ee2be` 修复）；路径越界（`../` 逃逸）拒绝。
- mod 自定义资源也可显式声明 `resources.assets` 等字段（示例见 `mods/PVZpy_Debugger` / `example_mod`，二者当前未声明 resources，走默认约定）。

### 4.9 调试器 mod（`mods/PVZpy_Debugger`）

- 入口 `debugger_mod.DebuggerMod`；F3 切换调试面板；`pygame.event.peek` 事件日志；监听 `GAME_EVENT_LOOP` / `GAME_PRE_FLIP`。
- 最近一次为按桌面旧版（PVZpy-Debugger-main）重写（`b4f587b`）：左上角单列黄字调试信息（版本/FPS/Tick/Scene/Mouse/Click/Mods/User）+ 右下角 FPS 折线图。
- **中文界面为待办**（见 §6）。

---

## 5. 历史变化时间线

> 提交顺序自旧到新；本地当前分支 `ui` 完整历史共 20 个提交（含 init）。`main` 分支停留在 init。

| 阶段 | 提交 | 说明 |
|---|---|---|
| 初始 | `8c2d36b` | `init: 项目初始提交`（main 分支亦在此） |
| 重构与清理（批次1 + 去全局化） | `b748c43` | 路径根化：资源/关卡/存档/日志基于项目根，解耦 cwd |
| | `cd78127` | 资源按需加载 + 排除 reanim 动画帧（去 cwd 依赖 key 与全量预加载） |
| | `87796ae` | 存档原子写、set 即时落盘、版本迁移框架（v0→v1） |
| | `fed15c2` | GameContext 显式依赖注入替代 GLOBAL_REFERENCE |
| | `ab74657` | 冒险场景状态机枚举化，移除波次旧元组兼容死代码 |
| | `2004865` | 实体加载器缓存化，统一子类查询入口 |
| | `9b7a52c` | 移除无用代码与残留（孤儿 pyc、GLOBAL_REFERENCE、reanim 资源与 SKIP_DIRS 机制） |
| | `54ee2be` | fix: 资源 key 路径前缀重复导致按需加载回退默认 |
| Mod 系统 M1~M5 | `a608603` | M1 基础设施（mod.json 解析、事件总线、注册表） |
| | `446a204` | M2 启动流程接入（boot/生命周期钩子） |
| | `d8cd6fb` | M3 资源命名空间化 |
| | `caf6654` | M4 注册表对接 |
| | `7326574` | M5 示例 mod（`mods/example_mod`） |
| Mod 开发文档 | `653be7a` | `docs: 新增模组开发文档`（`doc/Mod开发文档.md`） |
| 调试器演进 | `5b546d4` | 制作 PVZpy_Debugger 调试器 mod |
| | `d33938e` | 调试面板样式调整 |
| | `b2822e0` | 全屏分块布局与闪烁优化 |
| | `9904723` | 事件日志与布局样式调整 |
| | `b4f587b` | 按桌面旧版重写 PVZpy_Debugger（左上单列黄字 + FPS 折线） |
| 本体外置与资源分发 | `ff3fc1d` | feat: 本体外置 Vanilla.json 与 mod 资源分发改造（当前 HEAD） |
| 分支整理 | — | dev 快进合并 mod（`54ee2be..ff3fc1d`，12 提交，无 merge commit）→ 删除 mod 分支 → 从 dev 新建 ui 分支。全程未 push、未改代码 |

---

## 6. 当前仓库状态

### 6.1 分支与 HEAD

- 本地分支：`main`（8c2d36b init）/ `dev`（ff3fc1d）/ **`* ui`（ff3fc1d，当前）**。
- HEAD：`ff3fc1de83e0027e6a2e1687a81bf0f8b58caf4b`；`git status` 干净。
- 远程：`origin/dev` 停留在 `8c2d36b`（init）。

### 6.2 未 push 清单（20 个提交，相对 origin/dev）

```
ff3fc1d feat: 本体外置Vanilla.json与mod资源分发改造
b4f587b feat: 按桌面旧版重写PVZpy_Debugger模组
9904723 style: PVZpy_Debugger事件日志与布局样式调整
b2822e0 style: PVZpy_Debugger全屏分块布局与闪烁优化
d33938e style: PVZpy_Debugger调试面板样式调整
5b546d4 feat: 新增PVZpy_Debugger调试器mod
653be7a docs: 新增模组开发文档
7326574 feat: mod系统M5示例mod
caf6654 feat: mod系统M4注册表对接
d8cd6fb feat: mod系统M3资源命名空间化
446a204 feat: mod系统M2启动流程接入
a608603 feat: mod系统M1基础设施
54ee2be fix: 资源key路径前缀重复导致按需加载回退默认
9b7a52c chore: 移除无用代码与残留（孤儿pyc、GLOBAL_REFERENCE、reanim资源与SKIP_DIRS机制）
2004865 refactor: 实体加载器缓存化，统一子类查询入口
ab74657 refactor: 冒险场景状态机枚举化并移除波次旧元组兼容死代码
fed15c2 refactor: 以 GameContext 显式依赖注入替代 GLOBAL_REFERENCE 全局引用
87796ae fix: 存档原子写（临时文件+原子替换）、set 即时落盘、版本迁移框架（v0->v1 补齐模板字段）
cd78127 refactor: 资源加载改为按需加载并排除 reanim 动画帧（去掉 cwd 依赖 key 与全量 rglob 预加载）
b748c43 fix: 路径根化：资源/关卡/存档/日志路径基于项目根，解耦 cwd 依赖
```

### 6.3 待办事项

1. **push 远程**：以上 20 个提交未 push（人工推送，禁用自动 push；wincredman 曾失败）。
2. **清理 `__pycache__` 孤儿 pyc**：磁盘上 `src/`、`mods/`、`tools/` 等存在多个 Python 版本（311/314）的孤儿缓存（含无对应源码的历史模块残留）。`.gitignore` 已忽略 `__pycache__/`，不影响 git 状态；清理前先向用户确认，防误删。
3. **调试器界面补强与中文化**：`mods/PVZpy_Debugger` 界面仍为英文，中文化为待办。
4. **旧 TodoList 批次 3~5 未做**：修复计划见会话产物 `output/修复TodoList.md`（非仓库内文件）——批次 3（血量统一接口 / 硬编码收敛 / 编号机制与日志降噪 / 音量配置生效）、批次 4（碰撞行分区索引 / 资源访问去拷贝 / 拆分 adventure.py）、批次 5（贴图渲染 / 关卡存档 schema 校验 / 清理遗留产物 / CI lint 依赖锁定 / 场景栈与事件总线 / 内容扩充）。批次 1 已完成，批次 2 已基本完成（测试基线、GameContext 注入、循环依赖消除）。
5. **顺手修正 `src/gui.py` 不合规代码**（PEP8）。

---

## 7. 验证基线

> 冒烟/单测运行方式：在项目根执行，无头环境先设 `SDL_VIDEODRIVER=dummy` / `SDL_AUDIODRIVER=dummy`（冒烟脚本内部已驱动 dummy SDL）。

| 验证项 | 命令 | 基线（当前 HEAD） |
|---|---|---|
| 语法检查 | `python -m py_compile <文件>` 或全量 `py_compile` | 通过 |
| Mod 系统单测 | `python tools/test_mod_system.py`（或 `python -m unittest tools.test_mod_system`） | **Ran 65 tests, OK** |
| 实体系统单测 | `python tools/test_entities.py` | **PASS 74, FAIL 0** |
| 无头冒烟 | `python tools/smoke_mod_system.py` | **60 帧 + 全部行为断言通过**（含 Vanilla.json 读取、启动顺序、资源分发、命名空间解析等断言，见脚本输出） |

- 冒烟断言示例：`Vanilla.json id=pvzpy`、`assets=assets/PVZpy`、本体最先初始化、example_mod 位于本体之后、未声明 resources 走默认、声明自定义 assets/levels/entities 正确分发。
- `doc/Mod开发文档.md`：Mod 系统权威文档（653be7a 提交），含概述/目录约定/mod.json/生命周期/事件总线/注册表/资源系统/教程/调试，字段与代码一致，写 mod 前先读它。
- 每次逻辑完整更改后按 §2.3 双重验证法执行并 commit（不 push）。
