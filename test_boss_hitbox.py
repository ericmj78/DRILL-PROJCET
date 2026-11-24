import unittest

from stages import ENEMY_KINDS, WEAPONS
from world import World


class BossHitboxTests(unittest.TestCase):
    """보스는 그림 크기 상자(몸 폭 × 키)로 맞는다: 몸 가장자리나 발판 위에서 때려도 맞는다."""

    def setUp(self):
        self.w = World(2)   # 간수의 방
        self.boss = next(e for e in self.w.enemies if e.spawn.kind == 'jailer_boss')
        self.half = ENEMY_KINDS['jailer_boss'].width / 2
        self.reach = WEAPONS[self.w.weapon_index].reach * 0.8   # 베기
        self.me = self.w.player
        self.me.floor, self.me.facing = self.boss.actor.floor, 1

    def test_hits_body_edge_even_when_center_is_out_of_reach(self):
        self.me.x = self.boss.actor.x - self.half - self.reach / 2
        self.assertGreater(self.boss.actor.x - self.me.x, self.reach)   # 예전 판정(중심까지 거리)으로는 안 닿는다
        self.assertTrue(self.w._in_reach(self.boss, self.reach))

    def test_hits_from_a_platform_or_mid_jump(self):
        self.me.x = self.boss.actor.x - self.half
        for height in (38, 76, 150):
            self.me.base = height   # 발판 높이 (jump_height는 여기서 계산된다)
            self.assertTrue(self.w._in_reach(self.boss, self.reach), height)

    def test_misses_when_facing_away_or_above_the_head(self):
        self.me.x = self.boss.actor.x - self.half - self.reach / 2
        self.me.facing = -1
        self.assertFalse(self.w._in_reach(self.boss, self.reach))
        self.me.facing = 1
        self.me.base = ENEMY_KINDS['jailer_boss'].size + 40
        self.assertFalse(self.w._in_reach(self.boss, self.reach))

    def test_small_monsters_still_use_a_point(self):
        w = World(0)
        spider = next(e for e in w.enemies if e.spawn.kind == 'crawler')
        w.player.floor, w.player.facing = spider.actor.floor, 1
        w.player.x = spider.actor.x - self.reach - 5
        self.assertFalse(w._in_reach(spider, self.reach))
        w.player.x = spider.actor.x - self.reach + 5
        self.assertTrue(w._in_reach(spider, self.reach))


if __name__ == '__main__':
    unittest.main()
