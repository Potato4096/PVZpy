# PVZpy_Debugger

PVZpy 游戏调试器模组（按桌面旧版 PVZpy-Debugger-main 重写，界面保持一致，
内部实现迁移到当前 mod 系统接口）。

## 显示内容（左上角）

| 信息 | 说明 |
|------|------|
| PVZpy vX.X.X | 游戏版本（内置 pvzpy Mod 元数据） |
| FPS | 实时帧率 |
| Tick | 帧计数（旧版 game.tick_count 的等价替代） |
| Scene | 当前场景名（场景类常量 NAME） |
| Mouse | 鼠标实时坐标 (x, y) |
| Click | 左键/右键按住状态 L/R |
| Mods | 已加载模组数量 |
| User | 当前用户名 |

右下角：FPS 折线图（最近 120 帧，绿色折线、半透明黑底）。

## 快捷键

| 按键 | 功能 |
|------|------|
| F3 | 切换调试信息 显示/隐藏（默认显示） |

## 实现（当前 mod 系统接口）

- 生命周期：`on_pre_init` / `on_init` / `on_shutdown`（ModManager 驱动）；
- 事件订阅：`GAME_PRE_INIT` / `GAME_START` / `GAME_FRAME` /
  `GAME_EVENT_LOOP` / `GAME_PRE_FLIP` / `GAME_STOP`；
- 渲染时机：`GAME_PRE_FLIP`（本体 draw 后、flip 前），由本体统一 flip；
- F3 检测：`GAME_FRAME` 中 `pygame.key.get_pressed()` 按下沿，不消费事件队列；
- 事件探测：`GAME_EVENT_LOOP` 中 `pygame.event.peek()` 非破坏探测；
- 命名空间资源：`assets/images/icon.png`（mod id 命名空间）。

## 旧接口 -> 新接口映射

| 旧版（PVZpy-Debugger-main/mod.py） | 当前实现 |
|------------------------------------|----------|
| `@mod_manager.register` + `class Debugger(Mod)` | `mod.json` entry_points + `DebuggerMod` |
| `on_load()` | `on_pre_init` / `on_init` |
| `hook("game_init")` | 订阅 `GAME_START` / `GAME_PRE_INIT` |
| `hook("before_event")` | 订阅 `GAME_EVENT_LOOP`（peek 探测）+ `GAME_FRAME`（F3） |
| `hook("after_draw")` | 订阅 `GAME_PRE_FLIP`（flip 前渲染，不自行 flip） |
| `icon = "assets/PVZpy-Debugger/images/icon.png"` | `mods/PVZpy_Debugger/assets/images/icon.png`（命名空间） |
| `game.tick_count` | 帧计数 `_frame_count` |
| `game.mouse_pos` | `pygame.mouse.get_pos()` |
| `game.mouse_click` | `pygame.mouse.get_pressed(3)` |
| `game.username` | `game.context.saves.current_user` |
| `scene.name` | `game.current_scene.NAME` |
| `mod_manager.active_mods` | `manager.loaded` |

## 文件结构

```
mods/PVZpy_Debugger/
  mod.json            # mod 元数据
  debugger_mod.py     # 模组主文件（DebuggerMod）
  assets/images/icon.png  # 命名空间资源（图标）
```
