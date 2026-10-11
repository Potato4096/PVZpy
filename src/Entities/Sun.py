import pygame

from src.Entities.Entity import Entity


class Sun(Entity):
    # 阳光：从天空落下或向日葵产出，可被收集
    VALUE = 25
    SPEED = 40  # 下落速度
    RADIUS = 18
    _take_id = False  # 阳光不占实体编号，避免日志膨胀

    def __init__(self, x=0.0, y=0.0, value=None, target_y=0.0):
        super().__init__()
        self.x = x
        self.y = y
        self.value = self.VALUE if value is None else value
        self.target_y = target_y  # 落到此高度后停住
        self.radius = self.RADIUS
        self.rect = pygame.Rect(0, 0, self.radius * 2, self.radius * 2)
        self.sync_rect()

    def update(self, dt: float) -> None:
        if not self.alive():
            return
        if self.y < self.target_y:
            self.y = min(self.target_y, self.y + self.SPEED * dt)
            self.sync_rect()

    def contains(self, px, py):
        # 点击判定
        return self.rect.collidepoint(int(px), int(py))

    def collect(self):
        # 收集后消失，返回阳光值
        if not self.alive():
            return 0
        value = self.value
        self.kill()
        self.heart = 0
        return value
