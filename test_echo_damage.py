import unittest

import boss_skills
from stages import STEP
from world import Echo, Motion, World, Actor


class EchoDamageTests(unittest.TestCase):
    def setUp(self):
        self.world = World(0)
        self.world.player.x = 100
        self.enemy = self.world.enemies[0]
        self.enemy.actor.x = 800

    def test_recording_keeps_world_running_and_preview_takes_damage(self):
        w = self.world
        w.start_recording()
        echo = w.recording.preview
        echo.x = 720
        old_time, old_player_x, old_enemy_x = w.time, w.player.x, self.enemy.actor.x
        w.step(Motion(1))
        self.assertGreater(w.time, old_time)
        self.assertEqual(w.player.x, old_player_x)
        self.assertNotEqual(self.enemy.actor.x, old_enemy_x)
        echo.x = self.enemy.actor.x - 20
        self.enemy.target = echo
        damage = w.enemy_damage(self.enemy)
        old_health = w.health
        w._enemy_attack(self.enemy, 100)
        self.assertEqual(w.health, old_health - max(1, round(damage * .30)))
        self.assertIs(w.recording.preview, echo)
        w._enemy_attack(self.enemy, 100)
        self.assertEqual(w.health, old_health - max(1, round(damage * .30)))

    def test_replay_survives_and_immunity_expires(self):
        w = self.world
        actor = Actor.at(self.enemy.spawn.point)
        w.echo = Echo(actor, (Motion(),) * 100)
        self.enemy.target = actor
        old = w.health
        self.assertTrue(w.hurt_echo(actor, 10))
        self.assertEqual(w.health, old - 3)
        self.assertFalse(w.hurt_echo(actor, 10))
        self.assertIs(w.echo.actor, actor)
        w.enemies.clear()
        for _ in range(round(1.0 / STEP)):
            w.step()
        self.assertTrue(w.hurt_echo(actor, 10))
        self.assertEqual(w.health, old - 6)

    def test_boss_effect_damages_echo_without_destroying_it(self):
        w = self.world
        actor = Actor.at(self.enemy.spawn.point)
        w.echo = Echo(actor, (Motion(),) * 100)
        w.boss_effects.append(boss_skills.Effect('test', actor.x, actor.floor,
                                                 hit_at=0, hit_for=.5, radius=30, damage=10))
        old = w.health
        boss_skills.update_effects(w)
        self.assertEqual(w.health, old - 3)
        self.assertIs(w.echo.actor, actor)

    def test_ending_recording_clears_enemy_target(self):
        w = self.world
        w.start_recording()
        self.enemy.target = w.recording.preview
        w.recording.inputs.append(Motion())
        w.toggle_recording()
        self.assertIsNone(self.enemy.target)
        self.assertIsNotNone(w.echo)


if __name__ == '__main__':
    unittest.main()
