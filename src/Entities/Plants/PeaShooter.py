from src.Entities.Bullets.Pea import Pea
from src.Entities.Plant import Plant


class PeaShooter(Plant):
    # 豌豆射手
    COST = 100
    ATTACK_INTERVAL = 1.4

    def __init__(self, row=0, col=0):
        super().__init__(row, col)
        self.can_attack = True

    def make_bullet(self, x=None, y=None):
        # 生成一颗豌豆，伤害用 Pea.DAMAGE
        return Pea(
            row=self.row,
            x=self.x if x is None else x,
            y=self.y if y is None else y,
        )
