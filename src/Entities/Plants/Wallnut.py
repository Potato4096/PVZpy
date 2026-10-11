from src.Entities.Plant import Plant


class Wallnut(Plant):
    # 坚果墙：高血量，不攻击
    COST = 50
    HEART = 400

    def __init__(self, row=0, col=0):
        super().__init__(row, col)
        self.can_attack = False
        self.heart = self.HEART
        self.max_heart = self.HEART
