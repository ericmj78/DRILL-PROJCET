import unittest

from world import Actor, Motion, World, JUMP_HEIGHT, BEAST_JUMP_HEIGHT


class BeastEchoJumpTests(unittest.TestCase):
    def test_short_press_produces_normal_jump(self):
        world = World(0)
        actor = Actor(100, 0)
        world._move(actor, Motion(jump=True, jump_held=True), 'beast')
        for _ in range(15):
            world._move(actor, Motion(jump_held=True), 'beast')
        self.assertEqual(actor.jump_time, 0)
        self.assertTrue(actor.beast_charge_active)
        world._move(actor, Motion(), 'beast')
        self.assertGreater(actor.jump_time, 0)
        self.assertEqual(actor.jump_peak, JUMP_HEIGHT)
        self.assertFalse(actor.beast_super_jump)

    def test_long_press_super_jump_and_recorded_replay(self):
        world = World(0)
        world.enemies.clear()
        world.player.x = 100
        world.start_recording('beast')
        positions = []
        for frame in range(125):
            world.step(Motion(horizontal=1, jump=frame == 0, jump_held=frame < 60))
            actor = world.recording.preview
            positions.append((actor.x, actor.jump_height, actor.beast_charge_active, actor.beast_super_jump))
        self.assertTrue(positions[58][2])
        self.assertTrue(positions[59][3])
        self.assertGreater(max(p[1] for p in positions), JUMP_HEIGHT * 2)
        self.assertLessEqual(max(p[1] for p in positions), BEAST_JUMP_HEIGHT)
        world.toggle_recording()
        for x, height, charging, jumping in positions[:-1]:
            world.step()
            actor = world.echo.actor
            self.assertAlmostEqual(actor.x, x)
            self.assertAlmostEqual(actor.jump_height, height)
            self.assertEqual(actor.beast_charge_active, charging)
            self.assertEqual(actor.beast_super_jump, jumping)


if __name__ == '__main__':
    unittest.main()
