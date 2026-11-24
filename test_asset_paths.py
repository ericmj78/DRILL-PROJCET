import json
import unittest

from asset_paths import ASSET_ROOT, NAME_MAP, asset_path


class KoreanAssetPathTests(unittest.TestCase):
    def test_all_renamed_images_resolve(self):
        self.assertTrue(NAME_MAP)
        for old, new in NAME_MAP.items():
            with self.subTest(image=old):
                self.assertEqual(asset_path(old), ASSET_ROOT / new)
                self.assertTrue(asset_path(old).is_file())

    def test_effect_metadata_resolves_to_the_renamed_image(self):
        for metadata in (ASSET_ROOT / 'attack_fx').glob('*.json'):
            with self.subTest(effect=metadata.name):
                image = metadata.with_suffix('.png').relative_to(ASSET_ROOT)
                self.assertTrue(asset_path(image).is_file())
                self.assertIn('pixelfx', json.loads(metadata.read_text(encoding='utf-8'))['meta'])

    def test_unrenamed_assets_still_resolve(self):
        self.assertTrue(asset_path('dungeon.png').is_file())


if __name__ == '__main__':
    unittest.main()
