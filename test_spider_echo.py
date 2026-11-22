import unittest
from unittest.mock import patch

from stages import ACTOR_RADIUS, GATE_HALF_WIDTH, LEFT, RIGHT
from world import Actor, Motion, World


class SpiderEchoTests(unittest.TestCase):
    def setUp(self):
        self.world = World(0)
        self.world.enemies.clear()

    def test_statue_within_range_can_cross_a_and_press_b_on_replay(self):
        w = self.world
        w.player.x = 780
        w.start_recording('crawler')
        w.player.x = 100
        moves = ([Motion(stairs=1, web_aiming=True), Motion(web=True)]
                 + [Motion(horizontal=-1)] * 15
                 + [Motion(horizontal=-1, jump=True)]
                 + [Motion(horizontal=-1)] * 100 + [Motion()] * 30)
        for move in moves:
            w.step(move)
        self.assertLess(abs(w.recording.preview.x - w.stage.gates[1].plate.x), 27)
        self.assertFalse(w.doors[0].open)
        w.toggle_recording()
        b_pressed = False
        for _ in moves[:-1]:
            w.step()
            b_pressed |= w.doors[1].pressed
        self.assertTrue(b_pressed)

    def test_web_range_reaches_the_raised_statue(self):
        w = self.world
        beam = w.stage.web_beams[0]
        gate_x = w.stage.gates[0].door.x
        # 조각상 바로 아래에서는 위로, 조금 떨어진 곳에서는 대각선으로 닿는다.
        self.assertEqual(w.spider_web_target(Actor(beam.left + 40, 0), 0), (beam.left + 40, beam.underside))
        hit = w.spider_web_target(Actor(beam.left - 120, 0), 1)
        self.assertIsNotNone(hit)
        self.assertEqual(hit[1], beam.underside)
        # 닫힌 A 문 옆면에도 가까이에서는 붙는다.
        self.assertEqual(w.spider_web_target(Actor(gate_x - 60, 0), 1)[0], gate_x)
        # 너무 멀거나 위에 아무것도 없으면 붙지 않는다.
        self.assertIsNone(w.spider_web_target(Actor(gate_x - 300, 0), 1))
        self.assertIsNone(w.spider_web_target(Actor(1000, 0), 0))

    def test_aiming_is_left_out_of_the_replay(self):
        w = self.world
        w.player.x = 600
        w.start_recording('crawler')
        for frame in range(40):     # 땅에서 오래 조준해도
            w.step(Motion(horizontal=1 if frame > 20 else 0, web_aiming=True))
        self.assertEqual(w.recording.inputs, [])   # 녹화에는 남지 않는다
        w.step(Motion(web=True))
        anchor = w.recording.preview.web_anchor_x
        for _ in range(20):
            w.step(Motion())
        w.toggle_recording()
        aiming_seen = False
        for _ in range(20):
            w.step()
            aiming_seen |= w.echo.actor.web_aiming
        self.assertFalse(aiming_seen)               # 재현에서 조준 장면이 나오지 않고
        self.assertAlmostEqual(w.echo.actor.web_anchor_x, anchor)   # 같은 곳에 바로 쏜다

    @patch('world.SPIDER_AIM_REACH', 480)
    def test_aim_shows_real_surface_and_fire_replaces_old_rope(self):
        w = self.world
        actor = Actor(1000, 0)
        w._move(actor, Motion(stairs=1, web_aiming=True), 'crawler')
        target = w.spider_web_target(actor, actor.web_aim_x)
        self.assertEqual(target, (1000, 365))
        w._move(actor, Motion(web=True), 'crawler')
        self.assertEqual(actor.web_anchor_x, 1000)
        self.assertGreater(actor.web_time, 0)
        w._move(actor, Motion(horizontal=1, web_aiming=True), 'crawler')
        target = w.spider_web_target(actor, actor.web_aim_x)
        self.assertIsNotNone(target)
        w._move(actor, Motion(web=True), 'crawler')
        self.assertAlmostEqual(actor.web_anchor_x, target[0])
        self.assertNotEqual(actor.web_anchor_x, 1000)
        self.assertFalse(actor.web_flying)

    def test_no_surface_in_range_does_not_attach(self):
        w = self.world
        actor = Actor(1100, w.stage.floors - 1)
        w._move(actor, Motion(stairs=1, web_aiming=True), 'crawler')
        self.assertIsNone(w.spider_web_target(actor, actor.web_aim_x))
        w._move(actor, Motion(web=True), 'crawler')
        self.assertEqual(actor.web_time, 0)

    @patch('world.SPIDER_AIM_REACH', 480)
    def test_f_reconnects_while_airborne_and_replays(self):
        w = self.world
        w.player.x = 100
        w.start_recording('crawler')
        states = []
        for frame in range(80):
            kept = len(w.recording.inputs)
            w.step(Motion(horizontal=1, jump=frame == 51, web=frame in (1, 54),
                          web_aiming=frame in (0, 52, 53)))
            actor = w.recording.preview
            if len(w.recording.inputs) > kept:   # 땅에서 조준한 0번 프레임만 빠지고, 공중 조준은 몸 움직임이 남는다
                states.append((actor.x, actor.jump_height, actor.web_flying, actor.web_anchor_x))
        self.assertEqual(len(states), 79)
        self.assertTrue(states[52][2])
        self.assertFalse(states[53][2])
        self.assertNotEqual(states[52][3], states[53][3])
        self.assertAlmostEqual(states[52][0], states[53][0])
        self.assertAlmostEqual(states[52][1], states[53][1])
        w.toggle_recording()
        for expected in states[:-1]:
            w.step()
            actor = w.echo.actor
            self.assertAlmostEqual(actor.x, expected[0])
            self.assertAlmostEqual(actor.jump_height, expected[1])
            self.assertEqual(actor.web_flying, expected[2])
            self.assertAlmostEqual(actor.web_anchor_x, expected[3])

    def test_spider_climbs_map_boundaries_but_normal_echo_cannot(self):
        for x in (LEFT, RIGHT):
            with self.subTest(x=x):
                spider = Actor(x, 0)
                normal = Actor(x, 0)
                self.world._move(spider, Motion(stairs=1), 'crawler')
                self.world._move(normal, Motion(stairs=1))
                self.assertEqual(spider.elevator_target, 1)
                self.assertIsNone(normal.elevator_target)
                for _ in range(60):
                    self.world._move(spider, Motion(), 'crawler')
                self.assertEqual(spider.floor, 1)

    def test_spider_cannot_climb_wall_background(self):
        spider = Actor(1100, 0)
        self.world._move(spider, Motion(stairs=1), 'crawler')
        self.assertIsNone(spider.elevator_target)
        spider.elevator_target = None
        spider.x, spider.floor = LEFT, self.world.stage.floors - 1
        self.world._move(spider, Motion(stairs=1), 'crawler')
        self.assertIsNone(spider.elevator_target)

    def swing(self, world, spider, frames, horizontal=0, stairs=0):
        for frame in range(frames):
            # 반동은 흔들리는 방향으로 줄 때 커진다.
            push = horizontal if horizontal != 'pump' else (1 if spider.web_speed >= 0 else -1)
            world._move(spider, Motion(push, stairs), 'crawler')

    def land(self, world, spider):
        world._move(spider, Motion(jump=True), 'crawler')
        for _ in range(300):
            if spider.web_time == 0:
                return
            world._move(spider, Motion(), 'crawler')
        self.fail('거미가 착지하지 않았습니다')

    @patch('world.SPIDER_AIM_REACH', 480)
    def test_pumping_swings_further_than_hanging(self):
        distances = {}
        for name, push in (('hang', 0), ('pump', 'pump')):
            w = World(1)
            w.enemies.clear()
            spider = Actor(1300, 0)
            w._move(spider, Motion(web=True), 'crawler')
            self.assertGreater(spider.web_time, 0)
            self.swing(w, spider, 150, push)
            best = 0.0
            # 오른쪽으로 가장 빠르게 흔들릴 때 놓는다.
            for _ in range(120):
                w._move(spider, Motion(push if push != 'pump' else (1 if spider.web_speed >= 0 else -1)), 'crawler')
                if spider.web_speed > 0 and spider.web_angle > 0.45:   # 오른쪽으로 올라가는 중
                    break
            self.land(w, spider)
            distances[name] = spider.x - 1300
        self.assertGreater(distances['pump'], distances['hang'] + 80)

    def test_web_swing_is_recorded_and_replayed(self):
        w = self.world
        w.player.x = 1000
        w.start_recording('crawler')
        recorded = []
        for frame in range(150):
            push = 1 if (frame // 25) % 2 == 0 else -1
            kept = len(w.recording.inputs)
            w.step(Motion(push, 1 if 60 < frame < 80 else 0, jump=frame == 130,
                          web=frame == 1, web_aiming=frame == 0))
            if len(w.recording.inputs) > kept:   # 땅에서 조준한 프레임은 재현에 없다
                recorded.append((w.recording.preview.x, w.recording.preview.jump_height))
        self.assertGreater(max(h for _, h in recorded), 30)
        w.toggle_recording()
        for x, height in recorded[:-1]:
            w.step()
            self.assertAlmostEqual(w.echo.actor.x, x)
            self.assertAlmostEqual(w.echo.actor.jump_height, height)

    @patch('world.SPIDER_AIM_REACH', 480)
    def test_reeling_in_lifts_the_spider_over_a_wall(self):
        w = World(1)
        w.enemies.clear()
        wall = w.stage.walls[0]
        spider = Actor(wall.x - 60, wall.floor)
        w._move(spider, Motion(stairs=1, web_aiming=True), 'crawler')
        w._move(spider, Motion(web=True), 'crawler')
        self.swing(w, spider, 40)
        self.assertLess(spider.x, wall.x)          # 낮을 때는 벽에 막힌다
        for _ in range(120):                       # 벽보다 높아질 때까지만 줄을 감는다
            w._move(spider, Motion(stairs=1), 'crawler')
            if spider.jump_height > 125:
                break
        self.assertGreater(spider.jump_height, 125)
        for _ in range(120):
            w._move(spider, Motion(horizontal=1), 'crawler')
            if spider.web_speed > 0 and spider.x > wall.x:
                break
        self.assertGreater(spider.x, wall.x)
        self.land(w, spider)
        self.assertGreater(spider.x, wall.x)
        self.assertEqual(spider.floor, wall.floor)

    def test_holding_up_at_background_stays_on_same_floor_in_replay(self):
        w = self.world
        w.player.x = 500
        w.start_recording('crawler')
        recorded = []
        for _ in range(120):
            w.step(Motion(stairs=1))
            actor = w.recording.preview
            recorded.append((actor.floor, actor.elevator_target, actor.elevator_offset))
        self.assertEqual(w.recording.preview.floor, 0)
        self.assertIsNone(w.recording.preview.elevator_target)
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

    def test_climbs_actual_wall_obstacle(self):
        w = World(1)
        wall = w.stage.walls[0]
        spider = Actor(wall.x - GATE_HALF_WIDTH - ACTOR_RADIUS, wall.floor)
        w._move(spider, Motion(stairs=1), 'crawler')
        self.assertGreater(spider.door_climb_time, 0)
        for _ in range(80):
            w._move(spider, Motion(), 'crawler')
        self.assertGreater(spider.x, wall.x)
    def test_low_swing_does_not_cross_a_closed_gate(self):
        w = self.world
        spider = Actor(650, 0)
        w._move(spider, Motion(web=True), 'crawler')
        self.swing(w, spider, 120, 'pump')
        self.assertLess(spider.x, w.stage.gates[0].door.x)
        self.land(w, spider)
        self.assertLess(spider.x, w.stage.gates[0].door.x)
        self.assertEqual(spider.web_time, 0)

    def test_web_cannot_be_used_by_normal_echo(self):
        actor = Actor(100, 0)
        self.world._move(actor, Motion(web=True))
        self.assertEqual(actor.web_time, 0)
        self.assertEqual(actor.x, 100)


if __name__ == '__main__':
    unittest.main()
