#!/usr/bin/env python3
"""Validate private-pack selection without loading or testing mods."""
import pathlib
import runpy
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
build = runpy.run_path(str(ROOT / 'build.py'))


class SelectionTests(unittest.TestCase):
    def test_removes_exactly_pinned_entity_culling(self):
        entity = {'path': 'mods/culling.jar', 'downloads': ['https://cdn.modrinth.com/data/NNAgCjsB/versions/VhQ51u7a/culling.jar']}
        other = {'path': 'mods/other.jar', 'downloads': ['https://cdn.modrinth.com/data/other/versions/one/other.jar']}
        exclusions = build['LOCK']['exclusions']
        self.assertEqual(build['remove_exclusions']([entity, other], exclusions), [other])
        with self.assertRaises(ValueError):
            build['remove_exclusions']([other], exclusions)
        with self.assertRaises(ValueError):
            build['remove_exclusions']([entity, entity], exclusions)


if __name__ == '__main__':
    unittest.main()
