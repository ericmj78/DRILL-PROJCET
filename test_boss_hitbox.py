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
        for frame in range(120):   # 섬 높이(120)는 점프(96)로 못 닿아 2단 점프한다
            w.step(Motion(1 if w.player.x < x else 0, jump=frame == 24))
        self.assertEqual(w.player.base, height)
        w.player.x = x + 200   # 섬 끝 밖으로 걸어 나가면 떨어진다
        for _ in range(60):
            w.step(Motion())
        self.assertEqual(w.player.base, 0)


class WitchBroomTests(unittest.TestCase):
    """대마녀는 체력이 절반 이하가 되면 빗자루에 올라타(그동안 무적) 공중으로 떠오른다."""

    def test_mounts_at_half_health_then_flies(self):
        from stages import STEP
        from world import BROOM_HEIGHT, BROOM_MOUNT, Motion
        w = World(5)
        witch = w.enemies[0]
        w.player.x = witch.actor.x + 600   # 기본 공격이 닿지 않는 거리
        witch.health = witch.max_health // 2
        w.step(Motion())
        self.assertIsNotNone(witch.broom)
        self.assertEqual(witch.actor.base, 0)
        health = witch.health   # 타는 동안은 베어도 줄지 않는다
        w.player.x, w.player.facing = witch.actor.x - 40, 1
        w._attack()
        w._apply_attack()
        self.assertEqual(witch.health, health)
        w.player.x = witch.actor.x + 600
        for _ in range(round((BROOM_MOUNT + 1.5) / STEP)):
            w.step(Motion())
        self.assertAlmostEqual(witch.actor.base, BROOM_HEIGHT, delta=1)
        self.assertGreater(w.health, 0)


class KnightPhaseTests(unittest.TestCase):
    """잔향 기사는 체력 2/3·1/3에서 단계가 오르고(빛의 기둥 → 부활), 오르는 동안은 베어도 체력이 줄지 않는다."""

    def test_three_phases(self):
        import boss_skills
        w = World(8)
        knight = next(e for e in w.enemies if e.spawn.kind == 'echo_knight')
        self.assertTrue(all(s.phase == 1 for s in boss_skills.SKILLS['echo_knight'] if s.name in ('charge', 'skulls', 'hands')))
        self.assertEqual(next(s for s in boss_skills.SKILLS['echo_knight'] if s.name == 'pillar').phase, 2)
        for health, phase, sheet in ((knight.max_health * 2 // 3, 2, 'holy-pillar'), (knight.max_health // 3, 3, 'resurrection')):
            knight.health = health
            self.assertTrue(boss_skills.update_phase(w, knight))
            self.assertEqual(knight.phase, phase)
            self.assertIn(sheet, [effect.sheet for effect in w.boss_effects])
            w.player.floor, w.player.x, w.player.facing = knight.actor.floor, knight.actor.x - 40, 1
            w._attack()
            w._apply_attack()
            self.assertEqual(knight.health, health)   # 단계가 오르는 연출 중에는 무적
            while boss_skills.update_phase(w, knight):
                pass
            self.assertLessEqual(knight.phase_time, 0)


if __name__ == '__main__':
    unittest.main()
