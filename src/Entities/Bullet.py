import pygame

from src.Entities.Entity import Entity


class Bullet(Entity):
    # 子弹的属性，伤害在子弹上
    HEART = 1
    SPEED = 200  # 向右
    DAMAGE = 20
    _take_id = False  # 基类不占编号

    def __init__(self, row=1, x=0.0, y=0.0, damage=None):
        super().__init__()
        self.row = row
        self.x = x
        self.y = y
        self.speed = self.SPEED
        self.damage = self.DAMAGE if damage is None else damage
        self.rect = pygame.Rect(0, 0, 12, 12)
        self.sync_rect()

    def update(self, dt: float) -> None:
        if not self.alive():
            return
        self.x += self.speed * dt
        self.sync_rect()

    def hit(self, zombie):
        # 打中同行僵尸则扣血，子弹消失
        if not self.alive() or not zombie.alive() or zombie.row != self.row:
            return False
        if not pygame.sprite.collide_rect(self, zombie):
            return False
        zombie.take_damage(self.damage)
        self.kill()
        self.heart = 0
        return True
