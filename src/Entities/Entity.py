import pygame


class Entity(pygame.sprite.Sprite):
    # 所有实体共同的属性
    HEART = 100

    # 唯一编号自增计数，从 0 开始
    _next_id = 0
    # 基类不占编号；具体单位子类默认占编号
    _take_id = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # 子类若未写 _take_id，则默认需要编号
        if "_take_id" not in cls.__dict__:
            cls._take_id = True

    def __init__(self):
        pygame.sprite.Sprite.__init__(self)
        self.heart = self.HEART  # 将类属性 HEART 赋值给实例属性 heart
        self.max_heart = self.HEART
        self.row = 1
        self.col = 0
        self.x = 0.0
        self.y = 0.0
        # 精灵矩形，Group 碰撞用
        self.rect = pygame.Rect(0, 0, 32, 32)
        self.sync_rect()
        # 只有具体单位（如 PeaShooter）才分配编号
        if type(self)._take_id:
            self.entity_id = Entity._next_id
            Entity._next_id += 1
        else:
            self.entity_id = None

    def sync_rect(self):
        # 坐标变化后同步 rect
        self.rect.centerx = int(self.x)
        self.rect.centery = int(self.y)

    def take_damage(self, amount):
        # 扣血，血量归零则 kill()（移出 Group，alive() 变 False）
        if not self.alive() or amount <= 0:
            return
        self.heart -= amount
        if self.heart <= 0:
            self.heart = 0
            self.kill()

    def heal(self, amount):
        if not self.alive() or amount <= 0:
            return
        self.heart = min(self.max_heart, self.heart + amount)

    def update(self, dt: float) -> None:
        # 每帧逻辑，子类自己写
        pass

    def __repr__(self):
        # 日志/调试里能看出是哪一只
        if self.entity_id is None:
            return f"{type(self).__name__}(base, row={self.row}, col={self.col})"
        return (
            f"{type(self).__name__}#{self.entity_id}"
            f"(row={self.row}, col={self.col}, heart={self.heart}/{self.max_heart})"
        )
