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



class WitchIslandTests(unittest.TestCase):
    """대마녀의 방: 하늘 섬 7개가 저마다 범위 안에서 떠다니고, 올라탄 본체를 실어 나른다."""

    def test_islands_stay_in_their_lanes_and_carry_the_player(self):
        from stages import STEP
        from world import Motion
        w = World(5)
        w.enemies = []
        sky = w.stage.sky
        self.assertEqual(len(w.sky_blocks), 7)
        w.player.x, w.player.base = w.sky_blocks[0][0], w.sky_blocks[0][1]
        start = w.sky_blocks[0][0]
        for _ in range(round(20 / STEP)):
            w.step(Motion())
            for (x, _), (left, right) in zip(w.sky_blocks, sky.lanes):
                self.assertTrue(left - 1 <= x <= right + 1, (x, left, right))
        self.assertNotEqual(w.sky_blocks[0][0], start)
        self.assertEqual(w.player.base, w.sky_blocks[0][1])
        self.assertAlmostEqual(w.player.x, w.sky_blocks[0][0], delta=1)


    def test_jumping_from_below_lands_on_an_island(self):
        from world import Motion
        w = World(5)   # 정적 발판이 없고 하늘 섬만 있는 방
        w.enemies = []
        w.step(Motion())
        w.sky_pin = [999.0] * len(w.sky_blocks)   # 섬을 멈춰 두고 확인
        x, height = w.sky_blocks[0]
        w.player.x = x - 60
        w.step(Motion(1, jump=True))
        for frame in range(60):   # 섬 높이(80)는 보통 점프(48)로 못 닿아 꼭대기에서 2단 점프한다
            w.step(Motion(1 if w.player.x < x else 0, jump=frame == 17))
        self.assertEqual(w.player.base, height)
        w.player.x = x + 200   # 섬 끝 밖으로 걸어 나가면 떨어진다
        for _ in range(60):
            w.step(Motion())
        self.assertEqual(w.player.base, 0)


if __name__ == '__main__':
    unittest.main()
