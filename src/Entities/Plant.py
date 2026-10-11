import pygame

from src.Entities.Entity import Entity


class Plant(Entity):
    # 植物的属性
    COST = 100
    ATTACK_INTERVAL = 1.5  # 开火/技能间隔（秒）
    RANGE_ROW_ONLY = True  # 默认只打本行
    _take_id = False  # 基类不占编号

    def __init__(self, row=1, col=0):
        super().__init__()
        self.row = row
        self.col = col
        self.cost = self.COST
        self.attack_timer = 0.0
        self.can_attack = True  # 豌豆射手等为 True，向日葵等为 False
        self.rect = pygame.Rect(0, 0, 48, 48)
        self.sync_rect()

    def ready_to_attack(self):
        return self.alive() and self.can_attack and self.attack_timer <= 0.0

    def mark_attacked(self):
        self.attack_timer = self.ATTACK_INTERVAL

    def update(self, dt: float) -> None:
        if not self.alive():
            return
        if self.attack_timer > 0:
            self.attack_timer = max(0.0, self.attack_timer - dt)
