from src.Entities.Plant import Plant


class Sunflower(Plant):
    # 向日葵：产阳光，不攻击
    COST = 50
    SUN_INTERVAL = 24.0
    SUN_VALUE = 25

    def __init__(self, row=0, col=0):
        super().__init__(row, col)
        self.can_attack = False
        self.sun_timer = self.SUN_INTERVAL * 0.5  # 首次快一些

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.sun_timer > 0:
            self.sun_timer = max(0.0, self.sun_timer - dt)

    def try_produce_sun(self):
        if self.alive() and self.sun_timer <= 0:
            self.sun_timer = self.SUN_INTERVAL
            return True
        return False
