import unittest

from main import advance_stage_section
from world import World


class EchoInventoryTests(unittest.TestCase):
    def test_two_monsters_and_duplicate_or_boss_are_ignored(self):
        w = World()
        for kind in ('crawler', 'beast', 'crawler', 'jailer_boss'):
            w.offer_monster_echo(kind)
        self.assertEqual(w.monster_echoes, ['crawler', 'beast'])
        self.assertIsNone(w.pending_monster_echo)

    def test_replace_or_discard_and_queue(self):
        w = World(monster_echoes=['crawler', 'beast'])
        w.offer_monster_echo('warden')
        w.offer_monster_echo('watcher')
        self.assertEqual(w.pending_monster_echo, 'warden')
        before = w.time
        w.step()
        self.assertEqual(w.time, before)
        w.resolve_monster_echo(0)
        self.assertEqual(w.monster_echoes, ['warden', 'beast'])
        self.assertEqual(w.pending_monster_echo, 'watcher')
        w.resolve_monster_echo()
        self.assertEqual(w.monster_echoes, ['warden', 'beast'])
        self.assertIsNone(w.pending_monster_echo)

    def test_base_remains_available_and_inventory_is_copied_to_next_section(self):
        w = World(1, monster_echoes=['crawler', 'beast'])
        w.start_recording()
        self.assertIsNone(w.recording.monster_kind)
        w.cancel_recording()
        w.result = 'cleared'
        following = advance_stage_section(w)
        self.assertEqual(following.monster_echoes, ['crawler', 'beast'])
        following.monster_echoes[0] = 'warden'
        self.assertEqual(w.monster_echoes, ['crawler', 'beast'])

    def test_armor_guard_does_not_duplicate_armor(self):
        w = World()
        w.offer_monster_echo('magic_armor')
        w.offer_monster_echo('magic_armor_guard')
        self.assertEqual(w.monster_echoes, ['magic_armor'])


if __name__ == '__main__':
    unittest.main()
