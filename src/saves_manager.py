import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

DEFAULT_USERNAME = "default"

# 当前支持的存档版本；读取到更低版本时按 MIGRATIONS 逐级迁移
LATEST_VERSION = 1

SAVE_TEMPLATE: dict[str, Any] = {
    "username": DEFAULT_USERNAME,
    "version": 1,
    "unlocked_levels": [],
    "unlocked_plants": ["PeaShooter", "Sunflower", "Wallnut"],
    "options": {
        "music_volume": 0.8,
        "sfx_volume": 1.0,
    },
}


def _migrate_v0_to_v1(data: dict[str, Any]) -> None:
    # v0：无 version 字段或缺失模板字段的早期存档 -> v1 补齐默认结构
    template = json.loads(json.dumps(SAVE_TEMPLATE, ensure_ascii=False))
    for key, value in template.items():
        if key not in data:
            data[key] = value
            continue
        # 嵌套字典（如 options）按子字段补齐,不覆盖已有值
        if isinstance(value, dict) and isinstance(data[key], dict):
            for sub_key, sub_value in value.items():
                data[key].setdefault(sub_key, sub_value)
    data["version"] = 1


# 版本迁移注册表：source_version -> 迁移函数（就地修改 data 并推进 version）
MIGRATIONS: dict[int, Callable[[dict[str, Any]], None]] = {
    0: _migrate_v0_to_v1,
}


class SavesManager:
    def __init__(self) -> None:
        self.saves: dict[str, dict[str, Any]] = {}
        self.save_dir: Path | None = None
        self.current_user: str = DEFAULT_USERNAME
        self.current_save: dict[str, Any] = self._template(DEFAULT_USERNAME)

    @staticmethod
    def _template(username: str) -> dict[str, Any]:
        data = json.loads(json.dumps(SAVE_TEMPLATE, ensure_ascii=False))
        data["username"] = username
        return data

    def load_all(self, path: Path) -> None:
        self.save_dir = Path(path)
        self.saves.clear()
        if not self.save_dir.is_dir():
            logging.info("存档目录不存在: %s", self.save_dir)
            self.set_user(self.current_user)
            return
        for save in sorted(self.save_dir.glob("*.json")):
            try:
                with open(save, "r", encoding="utf-8") as raw:
                    data = json.load(raw)
            except (OSError, json.JSONDecodeError) as e:
                logging.warning("存档 %s 无法读取,跳过: %s", save, e)
                continue
            username = data.get("username")
            if not username:
                logging.warning("存档 %s 缺少 username,跳过", save)
                continue
            if self._migrate(data):
                self._save_atomic(save, data)
                logging.info("存档 %s 已从旧版本迁移并写回", save)
            self.saves[username] = data
            logging.debug("成功加载了用户 %s 的存档", username)
        self.set_user(self.current_user)

    def create_user(self, username: str) -> dict[str, Any]:
        if username in self.saves:
            self.set_user(username)
            return self.current_save
        self.saves[username] = self._template(username)
        self.set_user(username)
        return self.current_save

    def set_user(self, username: str) -> None:
        if username not in self.saves:
            logging.info("用户 %s 无存档,创建默认模板", username)
            self.saves[username] = self._template(username)
        self.current_user = username
        self.current_save = self.saves[username]

    def get(self, key: str, default: Any = None) -> Any:
        return self.current_save.get(key, default)

    def set(self, key: str, value: Any) -> None:
        # 数据变更即时落盘（原子写），避免仅退出时才保存造成丢失
        self.current_save[key] = value
        self.saves[self.current_user] = self.current_save
        self.save()

    def _migrate(self, data: dict[str, Any]) -> bool:
        # 将旧版本存档逐级迁移到 LATEST_VERSION；返回是否发生迁移
        version = data.get("version")
        if not isinstance(version, int) or version < 0:
            version = 0
        if version == LATEST_VERSION:
            return False
        if version > LATEST_VERSION:
            logging.warning("存档版本 %d 高于当前支持 %d,跳过迁移", version, LATEST_VERSION)
            return False
        while version < LATEST_VERSION:
            migrator = MIGRATIONS.get(version)
            if migrator is None:
                logging.error("缺少 %d -> %d 的迁移函数,放弃迁移", version, version + 1)
                return False
            migrator(data)
            version = data.get("version", version + 1)
            data["version"] = version
        return version == LATEST_VERSION

    def _save_atomic(self, path: Path, data: dict[str, Any]) -> bool:
        # 先写同目录临时文件并 fsync,再原子替换目标文件,避免中途崩溃留下半截存档
        tmp = path.with_name(path.name + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
            logging.debug("已保存存档 %s", path)
            return True
        except OSError as e:
            logging.error("写入存档失败 %s: %s", path, e)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            return False

    def save(self, username: str | None = None) -> None:
        name = username or self.current_user
        data = self.saves.get(name)
        if data is None:
            data = self._template(name)
            self.saves[name] = data
        if self.save_dir is None:
            logging.warning("未设置存档目录,无法写入用户 %s", name)
            return
        self.save_dir.mkdir(parents=True, exist_ok=True)
        path = self.save_dir / f"{name}.json"
        self._save_atomic(path, data)
