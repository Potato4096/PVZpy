import pygame

from src.Entities.Entity import Entity


class Zombie(Entity):
    # 僵尸的属性
    HEART = 100
    SPEED = 20  # 向左移动
    DAMAGE = 25  # 啃咬伤害
    EAT_INTERVAL = 1.0
    CONTACT_RANGE = 24  # 与植物接触（开始啃咬）的距离
    _take_id = False  # 基类不占编号

    def __init__(self, row=1, x=0.0, y=0.0):
        super().__init__()
        self.row = row
        self.x = x
        self.y = y
        self.speed = self.SPEED
        self.damage = self.DAMAGE
        self.eat_timer = 0.0
        self.target_plant = None  # 正在啃的植物
        self.rect = pygame.Rect(0, 0, 28, 36)
        self.sync_rect()

    def update(self, dt: float) -> None:
        if not self.alive():
            return
        if self.target_plant is not None:
            if self.target_plant.alive():
                if self.eat_timer > 0:
                    self.eat_timer = max(0.0, self.eat_timer - dt)
                self.sync_rect()
                return  # 啃咬时不前进
            self.target_plant = None
        self.x -= self.speed * dt
        self.sync_rect()

    def start_eat(self, plant):
        if not self.alive() or not plant.alive() or plant.row != self.row:
            return False
        self.target_plant = plant
        self.eat_timer = 0.0
        return True

    def try_eat(self):
        # 到间隔则咬一口，返回伤害；否则返回 0
        if (
            not self.alive()
            or self.target_plant is None
            or not self.target_plant.alive()
            or self.eat_timer > 0
        ):
            return 0
        self.eat_timer = self.EAT_INTERVAL
        self.target_plant.take_damage(self.damage)
        return self.damage
