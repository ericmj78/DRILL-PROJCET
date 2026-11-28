import unittest

import boss_skills
from asset_paths import ASSET_ROOT
from sound import BOSS_MUSIC, JINGLES, SOUNDS, STAGE_MUSIC, files
from stages import STEP
from world import Motion, World


class SoundTests(unittest.TestCase):
    """게임이 쌓는 효과음 이름은 모두 SOUNDS 표에 있고 파일도 있다."""

    def test_files_exist(self):
        for entry, _ in (*SOUNDS.values(), *JINGLES.values(), (BOSS_MUSIC, 0), (STAGE_MUSIC, 0)):
            for file in files(entry):
                self.assertTrue((ASSET_ROOT / 'sound' / file).exists(), file)
        names = set(boss_skills.SKILL_SOUNDS.values()) | {'rock', 'hands', 'pillar', 'phase', 'phase_start'}
        self.assertLessEqual(names, set(SOUNDS))

    def test_jump_and_boss_fight_make_sounds(self):
        w = World(2)   # 간수의 방
        w.step(Motion(jump=True))
        self.assertIn('jump', w.sounds)
        heard = set(w.sounds)
        boss = next(e for e in w.enemies if e.spawn.kind == 'jailer_boss')
        w.player.floor, w.player.x = boss.actor.floor, boss.actor.x + 300
        for _ in range(round(12 / STEP)):
            w.health = w.max_health
            w.step(Motion())
            heard |= set(w.sounds)
            w.sounds.clear()
        self.assertTrue(heard & {'chain', 'rockfall', 'charge'}, heard)
        self.assertIn('boss_appears', heard)
        self.assertLessEqual(heard, set(SOUNDS))

    def test_landing_and_monster_sounds(self):
        w = World(0)
        w.enemies = []
        heard = set()
        for frame in range(60):
            w.step(Motion(jump=frame == 0))
            heard |= set(w.sounds)
            w.sounds.clear()
        self.assertIn('land', heard)
        w = World(0)
        enemy = w.enemies[0]
        enemy.health = 1
        w.player.floor, w.player.x, w.player.facing = enemy.actor.floor, enemy.actor.x - 40, 1
        w._attack()
        w._apply_attack()
        self.assertIn('monster_die', w.sounds)


if __name__ == '__main__':
    unittest.main()
