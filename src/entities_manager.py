import logging
from pathlib import Path
from collections.abc import Iterator

import pygame

from src.Entities.Bullet import Bullet
from src.Entities.Plant import Plant
from src.Entities.Sun import Sun
from src.Entities.Zombie import Zombie


def _eat_collide(zombie: Zombie, plant: Plant) -> bool:
    # 僵尸与植物接触（用 rect + 同行判定）
    return (
        plant.row == zombie.row
        and pygame.sprite.collide_rect(zombie, plant)
    )


class EntitiesManager:
    # 用 Sprite.Group 管理实体，碰撞用 pygame.sprite.*

    def __init__(self, resource_dirs=None) -> None:
        # B：接收 ModManager 分发的实体资源目录列表（本体优先 + 外部目录序）。
        # 当前实体类由 src/Entities/loader.py 导入收集，目录列表先持有供后续扩展。
        self.resource_dirs: list[Path] = [Path(p) for p in (resource_dirs or [])]
        self.plants: pygame.sprite.Group = pygame.sprite.Group()
        self.zombies: pygame.sprite.Group = pygame.sprite.Group()
        self.bullets: pygame.sprite.Group = pygame.sprite.Group()
        self.suns: pygame.sprite.Group = pygame.sprite.Group()

    def clear(self) -> None:
        self.plants.empty()
        self.zombies.empty()
        self.bullets.empty()
        self.suns.empty()

    def add_plant(self, plant: Plant) -> Plant:
        self.plants.add(plant)
        return plant

    def add_zombie(self, zombie: Zombie) -> Zombie:
        self.zombies.add(zombie)
        return zombie

    def add_bullet(self, bullet: Bullet) -> Bullet:
        self.bullets.add(bullet)
        return bullet

    def add_sun(self, sun: Sun) -> Sun:
        self.suns.add(sun)
        return sun

    def plant_at(self, row: int, col: int) -> Plant | None:
        # row 1-5，col 0-8
        for p in self.plants:
            if p.row == row and p.col == col:
                return p
        return None

    def zombies_in_row(self, row: int) -> Iterator[Zombie]:
        # row 1-5
        for z in self.zombies:
            if z.row == row:
                yield z

    def update(self, dt: float) -> None:
        self.plants.update(dt)
        self.zombies.update(dt)
        self.bullets.update(dt)
        self.suns.update(dt)
        self._resolve_eat()
        self._resolve_hits()

    def _resolve_eat(self) -> None:
        # 僵尸接触到同行植物时开始啃咬
        for z in list(self.zombies):
            if z.target_plant is not None:
                if z.target_plant.alive():
                    z.try_eat()
                    continue
                z.target_plant = None

            hits = pygame.sprite.spritecollide(z, self.plants, False, _eat_collide)
            if not hits:
                continue
            p = hits[0]
            if z.start_eat(p):
                logging.debug("僵尸开始啃咬: %s -> %s", z, p)
                z.try_eat()

    def _resolve_hits(self) -> None:
        # 子弹命中僵尸
        for b in list(self.bullets):
            hits = pygame.sprite.spritecollide(b, self.zombies, False)
            if not hits:
                continue
            # 只打同行
            for z in hits:
                if z.row == b.row:
                    b.hit(z)
                    break

    @property
    def alive_plants(self) -> list[Plant]:
        return list(self.plants)

    @property
    def alive_zombies(self) -> list[Zombie]:
        return list(self.zombies)
