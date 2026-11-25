import unittest

from stages import STEP
from world import Motion, World


class JumpFallTests(unittest.TestCase):
    """발판에서 뛰어 아래로 떨어질 때 포물선이 끝나는 순간 멈칫하지 않는다."""

    def test_falls_on_without_stopping_after_jumping_off_a_platform(self):
        w = World(2)   # 간수의 방: 높이 45 발판
        w.enemies = []
        w.player.x, w.player.base = 1060, 45   # 가운데 발판(871~1067) 오른쪽 끝
        w.step(Motion())
        heights = [w.player.jump_height]
        w.step(Motion(1, jump=True))
        while w.player.jump_height > 0 and len(heights) < 200:
            w.step(Motion(1))
            heights.append(w.player.jump_height)
        drops = [a - b for a, b in zip(heights, heights[1:])]
        after = drops[heights.index(max(heights)):-1]   # 꼭대기부터 바닥에 닿기 직전까지 한 스텝에 내려간 거리
        # 멈칫하면 낙하가 0부터 다시 시작해 직전 스텝보다 수십 배 느려진다 (고치기 전: 4.8 → 0.23)
        self.assertTrue(all(b >= a * 0.5 for a, b in zip(after, after[1:])), after)
        self.assertEqual(w.player.base, 0)

    def test_normal_jump_on_the_ground_still_lands_cleanly(self):
        w = World(2)
        w.enemies = []
        w.player.x = 700
        w.step(Motion(jump=True))
        for _ in range(round(1 / STEP)):
            w.step(Motion())
        self.assertEqual((w.player.base, w.player.fall_speed, w.player.jump_time), (0, 0.0, 0.0))


if __name__ == '__main__':
    unittest.main()
