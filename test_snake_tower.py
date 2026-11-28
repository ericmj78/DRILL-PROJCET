import unittest

import chain_snake
from stages import STAGES, STEP
from world import Actor, Motion, World

TOWER = next(index for index, stage in enumerate(STAGES) if stage.tower)


class SnakeTowerTests(unittest.TestCase):
    """사슬 뱀의 탑: 올라타면 출발하고, 몸은 꼬리부터 사라지며, 세로 몸을 타고 위층으로 넘어간다."""

    def run_for(self, w, seconds, motion=Motion()):
        for _ in range(round(seconds / STEP)):
            w.step(motion)

    def test_snake_waits_until_stepped_on_and_starts_its_partner(self):
        w = World(TOWER)
        self.run_for(w, 1.0)
        self.assertEqual(w.snake_state[0], [chain_snake.start_head(w.stage.tower.snakes[0]), False])
        w.player = Actor(2060, 1, -1)   # 2층 시작 바닥에서 뱀 B 꼬리로 걸어간다
        self.run_for(w, 1.0, Motion(-1))
        self.assertTrue(w.snake_state[1][1] and w.snake_state[2][1])   # B를 타면 C도 함께 출발한다

    def test_standing_still_falls_and_returns_to_floor_start(self):
        w = World(TOWER)
        self.run_for(w, 1.2, Motion(1))           # 꼬리에 올라탄다
        self.assertTrue(w.snake_state[0][1])
        self.run_for(w, 8.0)                      # 가만히 서 있으면 꼬리가 지나가 떨어진다
        self.assertEqual((w.player.floor, w.player.x, w.result), (0, w.stage.tower.starts[0], 'playing'))
        self.assertFalse(w.snake_state[0][1])     # 뱀도 처음 자리로 돌아가 기다린다

    def test_rising_column_carries_the_player_to_the_next_floor(self):
        w = World(TOWER)
        snake = w.stage.tower.snakes[0]
        corner = snake.path[1][0]
        w.snake_state[0] = [chain_snake.length(snake) - 800 - 5, True]   # 머리가 위로 꺾이기 직전
        w.player = Actor(corner - 5, 0, 1)   # 머리 끝에 서 있으면 세로 몸을 타고 함께 오른다
        self.run_for(w, 800 / snake.speed + 1.0)
        self.assertEqual((w.player.floor, w.player.base, w.result), (1, 0.0, 'playing'))


if __name__ == '__main__':
    unittest.main()
