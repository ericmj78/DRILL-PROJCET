import unittest

from stages import DOOR_GRACE, STEP
from world import Actor, Echo, Motion, World


class FirstGateTests(unittest.TestCase):
    def test_plate_releases_and_gate_closes_after_echo_disappears(self):
        world = World(0)
        world.enemies.clear()
        gate = world.stage.gates[0]
        world.player.x = gate.door.x + 200
        world.echo = Echo(Actor.at(gate.plate), (Motion(),) * 100)
        world._update_doors(STEP)
        state = world.doors[0]
        self.assertTrue(state.pressed)
        self.assertTrue(state.open)
        self.assertFalse(state.latched)
        world._remove_echo()
        world._update_doors(DOOR_GRACE + STEP)
        self.assertFalse(state.pressed)
        self.assertFalse(state.open)
        self.assertFalse(state.latched)

    def test_player_can_return_through_gate_after_it_closes(self):
        world = World(0)
        world.enemies.clear()
        gate = world.stage.gates[0]
        world.player.x = gate.door.x + 60
        world._update_doors(STEP)
        self.assertFalse(world.doors[0].pressed)
        self.assertTrue(world.doors[0].open)
        for _ in range(60):
            world.step(Motion(-1))
        self.assertLess(world.player.x, gate.door.x)


if __name__ == '__main__':
    unittest.main()
