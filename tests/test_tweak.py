import unittest

from app.editor.sample import l_kitchen_spec
from app.editor.tweak import TweakError, move_divider, set_bay_width


class TweakTests(unittest.TestCase):
    def test_set_bay_width_steals_from_next_bay(self):
        spec = l_kitchen_spec()
        out = set_bay_width(spec, "wall-a", "bay-1", 90)
        bays = out.design_wall("wall-a").bays
        self.assertEqual(bays[0].width, 90)
        self.assertEqual(bays[1].width, 50)
        self.assertEqual(sum(b.width for b in bays), 300)
        self.assertEqual(out.version, spec.version + 1)

    def test_last_bay_steals_from_previous(self):
        spec = l_kitchen_spec()
        out = set_bay_width(spec, "wall-a", "bay-4", 90)
        bays = out.design_wall("wall-a").bays
        self.assertEqual(bays[3].width, 90)
        self.assertEqual(bays[2].width, 70)

    def test_rejects_too_narrow(self):
        spec = l_kitchen_spec()
        with self.assertRaises(TweakError):
            set_bay_width(spec, "wall-a", "bay-1", 5)

    def test_move_divider(self):
        spec = l_kitchen_spec()
        out = move_divider(spec, "wall-a", "bay-1", 10)
        bays = out.design_wall("wall-a").bays
        self.assertEqual(bays[0].width, 90)
        self.assertEqual(bays[1].width, 50)

    def test_move_divider_blocked_at_min(self):
        spec = l_kitchen_spec()
        with self.assertRaises(TweakError):
            move_divider(spec, "wall-a", "bay-1", 55)


if __name__ == "__main__":
    unittest.main()
