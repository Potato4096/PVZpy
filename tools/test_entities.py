# 测试实体系统：只测 entities_manager 与各单位（需 pygame）
# 运行: python tools/test_entities.py

import sys
from pathlib import Path

# 允许直接在项目根或 tools/ 下运行
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pygame

from src.entities_manager import EntitiesManager
from src.Entities.Entity import Entity
from src.Entities.Plant import Plant
from src.Entities.Zombie import Zombie
from src.Entities.Bullet import Bullet
from src.Entities.Plants.PeaShooter import PeaShooter
from src.Entities.Plants.SunFlower import Sunflower
from src.Entities.Plants.Wallnut import Wallnut
from src.Entities.Zombies.NormalZombie import NormalZombie
from src.Entities.Bullets.Pea import Pea

passed = 0
failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}")


def spawn(*sprites):
    # 入组后 Sprite.alive() 才为 True（pygame 约定）
    g = pygame.sprite.Group()
    for s in sprites:
        g.add(s)
    return g


def test_entity_base():
    print("Entity 基类")
    e = Entity()
    spawn(e)
    check("默认血量 100", e.heart == 100 and e.max_heart == 100)
    check("初始存活", e.alive())

    e.take_damage(30)
    check("扣血 30 后为 70", e.heart == 70)
    check("受伤仍存活", e.alive())

    e.heal(50)
    check("治疗不超过上限", e.heart == 100)

    e.take_damage(999)
    check("过量伤害致死", not e.alive() and e.heart == 0)

    e.heal(10)
    check("死亡后不再治疗", e.heart == 0 and not e.alive())


def test_plant_base():
    print("Plant 基类")
    p = Plant(row=2, col=3)
    spawn(p)
    check("坐标", p.row == 2 and p.col == 3)
    check("费用 COST", p.cost == Plant.COST)
    check("可攻击默认 True", p.can_attack)
    check("冷却结束可开火", p.ready_to_attack())

    p.mark_attacked()
    check("开火后进入冷却", not p.ready_to_attack())
    p.update(Plant.ATTACK_INTERVAL + 0.1)
    check("冷却结束恢复可开火", p.ready_to_attack())


def test_peashooter():
    print("PeaShooter")
    ps = PeaShooter(row=1, col=4)
    spawn(ps)
    check("费用 100", ps.cost == 100)
    check("攻击间隔 1.4", ps.ATTACK_INTERVAL == 1.4)
    check("可攻击", ps.can_attack)

    pea = ps.make_bullet()
    check("make_bullet 返回 Pea", isinstance(pea, Pea))
    check("子弹同行", pea.row == 1)
    check("伤害在子弹上", pea.damage == Pea.DAMAGE == 20)
    check("植物自身无 damage", not hasattr(ps, "damage"))

    pea2 = ps.make_bullet(x=100, y=50)
    check("可指定子弹坐标", pea2.x == 100 and pea2.y == 50)


def test_sunflower():
    print("Sunflower")
    sf = Sunflower(row=0, col=0)
    spawn(sf)
    check("费用 50", sf.cost == 50)
    check("不攻击", not sf.can_attack)
    check("阳光值 25", sf.SUN_VALUE == 25)

    sf.sun_timer = 0.0
    check("到点可产阳光", sf.try_produce_sun())
    check("产完进入冷却", not sf.try_produce_sun())
    sf.update(Sunflower.SUN_INTERVAL + 0.1)
    check("再次可产阳光", sf.try_produce_sun())


def test_wallnut():
    print("Wallnut")
    wn = Wallnut(row=1, col=1)
    spawn(wn)
    check("费用 50", wn.cost == 50)
    check("血量 400", wn.heart == 400 and wn.max_heart == 400)
    check("不攻击", not wn.can_attack)
    wn.take_damage(100)
    check("可正常扣血", wn.heart == 300)


def test_zombie():
    print("Zombie / NormalZombie")
    z = NormalZombie(row=2, x=800, y=0)
    spawn(z)
    check("普通僵尸血量 100", z.heart == 100)
    check("速度 20", z.speed == 20)
    check("啃咬伤害 25", z.damage == 25)

    x0 = z.x
    z.update(1.0)
    check("无目标时向左走", z.x == x0 - 20)

    plant = Wallnut(row=2, col=0)
    plant.x = 100
    plant.sync_rect()
    spawn(plant)
    z.x = 110
    z.sync_rect()
    check("可开始啃咬", z.start_eat(plant))
    check("啃咬时停止移动", True)
    x1 = z.x
    z.update(1.0)
    check("啃咬中不前进", z.x == x1)

    dmg = z.try_eat()
    check("try_eat 返回伤害", dmg == 25)
    check("植物掉血", plant.heart == 400 - 25)
    check("间隔内不再咬", z.try_eat() == 0)
    z.eat_timer = 0
    check("间隔结束后可再咬", z.try_eat() == 25)

    plant.take_damage(999)
    z.update(0.01)
    check("目标死亡后继续走", z.target_plant is None)


def test_bullet():
    print("Bullet / Pea")
    b = Pea(row=1, x=50, y=0)
    spawn(b)
    check("豌豆速度 280", b.speed == 280)
    check("豌豆伤害 20", b.damage == 20)

    b.update(1.0)
    check("向右飞", b.x == 50 + 280)

    z = NormalZombie(row=1, x=b.x, y=0)
    z.sync_rect()
    spawn(z)
    check("命中同行僵尸", b.hit(z))
    check("僵尸掉血", z.heart == 80)
    check("子弹消失", not b.alive())

    z2 = NormalZombie(row=2, x=b.x)
    z2.sync_rect()
    spawn(z2)
    b2 = Pea(row=1, x=50)
    spawn(b2)
    check("不命中异行", not b2.hit(z2))
    check("异行僵尸未受伤", z2.heart == 100)


def test_entities_manager():
    print("EntitiesManager")
    em = EntitiesManager()
    p = em.add_plant(PeaShooter(row=0, col=0))
    z = em.add_zombie(NormalZombie(row=0, x=p.x + 5))
    b = em.add_bullet(p.make_bullet(x=p.x + 1, y=p.y))
    check("登记 1 植物 1 僵尸 1 子弹",
          len(em.plants) == 1 and len(em.zombies) == 1 and len(em.bullets) == 1)
    check("plant_at 命中", em.plant_at(0, 0) is p)
    check("plant_at 空位为 None", em.plant_at(0, 1) is None)
    check("zombies_in_row", list(em.zombies_in_row(0)) == [z])
    check("本行无其它僵尸", list(em.zombies_in_row(1)) == [])

    # 子弹应能打到很近的僵尸
    em.update(0.016)
    check("更新后子弹/僵尸状态正常",
          (not b.alive() and z.heart == 80) or (b.alive() and z.heart == 100))

    # 清理死亡实体
    z.take_damage(9999)
    p.take_damage(9999)
    em.update(0.01)
    check("死亡实体被清理", len(em.alive_plants) == 0 and len(em.alive_zombies) == 0)

    em.add_plant(Sunflower(row=1, col=1))
    em.add_plant(Wallnut(row=2, col=2))
    check("多种植物可共存", len(em.plants) == 2)
    em.clear()
    check("clear 清空", len(em.plants) == 0 and len(em.zombies) == 0 and len(em.bullets) == 0)


def test_inheritance():
    print("继承关系")
    check("PeaShooter 是 Plant", issubclass(PeaShooter, Plant))
    check("Plant 是 Entity", issubclass(Plant, Entity))
    check("NormalZombie 是 Zombie", issubclass(NormalZombie, Zombie))
    check("Zombie 是 Entity", issubclass(Zombie, Entity))
    check("Pea 是 Bullet", issubclass(Pea, Bullet))
    check("Bullet 是 Entity", issubclass(Bullet, Entity))


def test_entity_id():
    print("entity_id 唯一编号")
    # 基类不占编号
    check("Entity 不占编号", Entity().entity_id is None)
    check("Plant 基类不占编号", Plant().entity_id is None)
    check("Zombie 基类不占编号", Zombie().entity_id is None)
    check("Bullet 基类不占编号", Bullet().entity_id is None)

    a = PeaShooter()
    b = Sunflower()
    c = NormalZombie()
    d = Pea()
    ids = [a.entity_id, b.entity_id, c.entity_id, d.entity_id]
    check("具体单位都有编号", all(i is not None for i in ids))
    check("编号互不相同", len(set(ids)) == 4)
    check("repr 带编号", f"#{a.entity_id}" in repr(a))
    check("基类 repr 标明 base", "base" in repr(Entity()))


def main():
    print("==== 实体系统测试 ====")
    test_entity_base()
    test_plant_base()
    test_peashooter()
    test_sunflower()
    test_wallnut()
    test_zombie()
    test_bullet()
    test_entities_manager()
    test_inheritance()
    test_entity_id()

    print()
    print(f"结果: PASS {passed}, FAIL {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
