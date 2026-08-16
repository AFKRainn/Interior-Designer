import unittest

from app.agents.spec_author import (
    SpecAuthor,
    SpecAuthorError,
    normalize_spec_dict,
    try_parse_spec,
)
from app.planner.views import plan_views
from app.render.svg_plan import plan_svg
from tests.fake_openrouter import FakeOpenRouter
from tests.spec_factory import l_kitchen_spec


def _dump(spec=None):
    spec = spec or l_kitchen_spec()
    return spec.model_dump(mode="json")


class SpecParseTests(unittest.TestCase):
    def test_normalize_l_shaped_alias(self):
        data = normalize_spec_dict({"layout": {"type": "l-shaped", "walls": []}})
        self.assertEqual(data["layout"]["type"], "L")

    def test_valid_dump_roundtrips(self):
        spec, err = try_parse_spec(_dump())
        self.assertIsNone(err)
        self.assertEqual(spec.layout.type.value, "L")
        self.assertEqual(len(spec.walls), 2)

    def test_bad_bay_sum_fails(self):
        data = _dump()
        data["walls"][0]["bays"][0]["width"] = 10
        spec, err = try_parse_spec(data)
        self.assertIsNone(spec)
        self.assertIn("bay widths", err)


class SpecAuthorTests(unittest.IsolatedAsyncioTestCase):
    async def test_from_brief_validates(self):
        data = _dump()
        data.pop("brief", None)
        client = FakeOpenRouter([data])
        author = SpecAuthor(client=client)
        spec = await author.from_brief("L kitchen sink run 300, fridge run 180")
        self.assertEqual(spec.layout.type.value, "L")
        self.assertEqual(spec.brief, "L kitchen sink run 300, fridge run 180")
        plan = plan_views(spec)
        self.assertEqual(len(plan.elevations), 2)
        svg = plan_svg(spec)
        self.assertIn("wall-a", svg)

    async def test_invalid_then_repair(self):
        bad = _dump()
        bad["walls"][0]["bays"][0]["width"] = 10
        client = FakeOpenRouter([bad, _dump()])
        author = SpecAuthor(client=client)
        spec = await author.from_brief("L kitchen")
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(spec.layout_wall("wall-a").length, 300)

    async def test_still_invalid_after_repair_raises(self):
        bad = _dump()
        bad["walls"][0]["bays"][0]["width"] = 10
        client = FakeOpenRouter([bad, bad])
        author = SpecAuthor(client=client)
        with self.assertRaises(SpecAuthorError):
            await author.from_brief("L kitchen")

    async def test_patch_changes_bay_and_keeps_id(self):
        original = l_kitchen_spec()
        patched = _dump(original)
        patched["version"] = 2
        patched["walls"][0]["bays"][0]["width"] = 70
        patched["walls"][0]["bays"][1]["width"] = 70
        patched["project_id"] = "should-be-overwritten"
        client = FakeOpenRouter([patched])
        author = SpecAuthor(client=client)
        out = await author.patch(original, "Sink bay 70 cm, dishwasher bay 70 cm")
        self.assertEqual(out.project_id, original.project_id)
        self.assertEqual(out.version, 2)
        self.assertEqual(out.design_wall("wall-a").bays[0].width, 70)
        self.assertEqual(out.design_wall("wall-a").bays[1].width, 70)

    async def test_patch_bumps_version_if_model_forgets(self):
        original = l_kitchen_spec()
        patched = _dump(original)
        patched["version"] = 1
        client = FakeOpenRouter([patched])
        author = SpecAuthor(client=client)
        out = await author.patch(original, "keep everything")
        self.assertEqual(out.version, original.version + 1)


if __name__ == "__main__":
    unittest.main()
