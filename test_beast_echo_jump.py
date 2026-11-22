import unittest
from dataclasses import replace

from stages import JumpBlock
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


    def jump_map(self):
        """점프 블록 하나를 둔 1스테이지 1층."""
        world = World(0)
        world.enemies.clear()
        world.stage = replace(world.stage, jump_blocks=(JumpBlock(0, 1200),))
        return world, world.stage.jump_blocks[0]

    def test_jump_block_stops_walking_and_normal_jumps(self):
        world, block = self.jump_map()
        for kind in (None, 'beast'):
            with self.subTest(kind=kind):
                actor = Actor(block.x - 120, 0)
                world._move(actor, Motion(horizontal=1, jump=True), kind)   # 짧게 누른 보통 점프
                for _ in range(90):
                    world._move(actor, Motion(horizontal=1), kind)
                self.assertLess(actor.x, block.x)
        self.assertLess(JUMP_HEIGHT, block.height)

    def test_super_jump_clears_the_block_and_replays(self):
        world, block = self.jump_map()
        world.player.x = block.x - 120
        world.start_recording('beast')
        positions = []
        for frame in range(140):
            world.step(Motion(horizontal=1, jump=frame == 0, jump_held=frame < 60))
            positions.append(world.recording.preview.x)
        self.assertGreater(positions[-1], block.x + block.width)
        self.assertGreater(BEAST_JUMP_HEIGHT, block.height)
        world.toggle_recording()
        for x in positions[:-1]:
            world.step()
            self.assertAlmostEqual(world.echo.actor.x, x)


if __name__ == '__main__':
    unittest.main()
