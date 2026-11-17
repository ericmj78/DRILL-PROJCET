import unittest

from stages import ACTOR_RADIUS, GATE_HALF_WIDTH, LEFT
from world import Actor, Motion, World


class SpiderEchoTests(unittest.TestCase):
    def setUp(self):
        self.world = World(0)
        self.world.enemies.clear()

    def test_spider_climbs_boundary_but_normal_echo_cannot(self):
        spider = Actor(LEFT, 0)
        normal = Actor(LEFT, 0)
        self.world._move(spider, Motion(stairs=1), 'crawler')
        self.world._move(normal, Motion(stairs=1))
        self.assertEqual(spider.elevator_target, 1)
        self.assertIsNone(normal.elevator_target)
        for _ in range(60):
            self.world._move(spider, Motion(), 'crawler')
        self.assertEqual(spider.floor, 1)
        self.assertIsNone(spider.elevator_target)

    def test_spider_can_climb_wall_background_but_not_above_top_floor(self):
        spider = Actor(1100, 0)
        self.world._move(spider, Motion(stairs=1), 'crawler')
        self.assertEqual(spider.elevator_target, 1)
        spider.elevator_target = None
        spider.x, spider.floor = LEFT, self.world.stage.floors - 1
        self.world._move(spider, Motion(stairs=1), 'crawler')
        self.assertIsNone(spider.elevator_target)

    def test_web_movement_is_recorded_and_replayed(self):
        w = self.world
        w.player.x = 100
        w.start_recording('crawler')
        recorded = []
        for frame in range(60):
            w.step(Motion(web=frame == 0))
            recorded.append((w.recording.preview.x, w.recording.preview.jump_height))
        self.assertGreater(recorded[25][1], 80)
        self.assertGreater(recorded[-1][0], 300)
        w.toggle_recording()
        for x, height in recorded[:-1]:
            w.step()
            self.assertAlmostEqual(w.echo.actor.x, x)
            self.assertAlmostEqual(w.echo.actor.jump_height, height)

    def test_holding_up_climbs_and_replays_from_dungeon_wall(self):
        w = self.world
        w.player.x = 500
        w.start_recording('crawler')
        recorded = []
        for _ in range(120):
            w.step(Motion(stairs=1))
            actor = w.recording.preview
            recorded.append((actor.floor, actor.elevator_target, actor.elevator_offset))
        self.assertEqual(w.recording.preview.floor, 2)
        w.toggle_recording()
        for floor, target, offset in recorded[:-1]:
            w.step()
            self.assertEqual(w.echo.actor.floor, floor)
            self.assertEqual(w.echo.actor.elevator_target, target)
            self.assertAlmostEqual(w.echo.actor.elevator_offset, offset)

    def test_climbs_over_closed_door_from_both_sides_and_replays(self):
        for side in (-1, 1):
            with self.subTest(side=side):
                w = World(0)
                w.enemies.clear()
                door_x = w.stage.gates[0].door.x
                w.player.x = door_x + side * (GATE_HALF_WIDTH + ACTOR_RADIUS)
                w.start_recording('crawler')
                w.player.x = 100
                w._update_doors(0)
                self.assertFalse(w.doors[0].open)
                recorded = []
                for _ in range(85):
                    w.step(Motion(stairs=1))
                    recorded.append((w.recording.preview.x, w.recording.preview.jump_height))
                self.assertEqual(w.recording.preview.floor, 0)
                self.assertLess((w.recording.preview.x - door_x) * side, 0)
                self.assertGreater(max(height for _, height in recorded), 110)
                self.assertFalse(w.doors[0].open)
                self.assertFalse(w.doors[0].pressed)
                w.toggle_recording()
                for expected_x, expected_height in recorded[:-1]:
                    w.step()
                    self.assertAlmostEqual(w.echo.actor.x, expected_x)
                    self.assertAlmostEqual(w.echo.actor.jump_height, expected_height)
                self.assertEqual(w.echo.actor.floor, 0)
                self.assertLess((w.echo.actor.x - door_x) * side, 0)
                self.assertFalse(w.doors[0].pressed)

    def test_web_does_not_cross_a_closed_gate(self):
        w = self.world
        spider = Actor(650, 0)
        for frame in range(70):
            w._move(spider, Motion(web=frame == 0), 'crawler')
        self.assertLess(spider.x, w.stage.gates[0].door.x)
        self.assertEqual(spider.web_time, 0)

    def test_web_cannot_be_used_by_normal_echo(self):
        actor = Actor(100, 0)
        self.world._move(actor, Motion(web=True))
        self.assertEqual(actor.web_time, 0)
        self.assertEqual(actor.x, 100)


if __name__ == '__main__':
    unittest.main()
