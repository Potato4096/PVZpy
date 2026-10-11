import json
import logging
from pathlib import Path
from typing import Any

DEFAULT_USERNAME = "default"

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
        self.current_save[key] = value
        self.saves[self.current_user] = self.current_save

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
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            logging.debug("已保存存档 %s", path)
        except OSError as e:
            logging.error("写入存档失败 %s: %s", path, e)
