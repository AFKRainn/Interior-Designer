import asyncio
import base64
import unittest

from app.planner.views import plan_views
from app.render.photoreal import build_packets, packet_for_shot, render_packet
from app.render.raster import elevation_png, plan_cone_png, png_bytes
from tests.fake_openrouter import TINY_PNG, FakeOpenRouter
from tests.spec_factory import galley_spec, l_kitchen_spec, l_spec, u_spec


class PhotorealPacketTests(unittest.TestCase):
    def test_l_kitchen_one_corner_packet_both_elevations_only(self):
        spec = l_kitchen_spec()
        packets = build_packets(spec)
        self.assertEqual(len(packets), 1)
        packet = packets[0]
        self.assertEqual(packet.shot_id, "shot-1")
        self.assertEqual(packet.camera, "inside_corner")
        self.assertEqual(packet.walls, ["wall-a", "wall-b"])
        self.assertEqual(packet.exclude, [])
        names = [ref.name for ref in packet.references]
        self.assertEqual(
            names,
            ["elev-wall-a.svg", "elev-wall-b.svg", "plan-cone.svg"],
        )
        self.assertEqual(names, plan_views(spec).cameras[0].references)
        self.assertIn("LEFT of frame: wall-a", packet.prompt)
        self.assertIn("RIGHT of frame: wall-b", packet.prompt)
        for ref in packet.references:
            raw = base64.b64decode(ref.data)
            self.assertTrue(raw.startswith(b"\x89PNG"))

    def test_u_shot_isolates_references(self):
        packets = build_packets(u_spec())
        self.assertEqual(len(packets), 2)
        first = [ref.name for ref in packets[0].references]
        second = [ref.name for ref in packets[1].references]
        self.assertEqual(
            first,
            ["elev-wall-a.svg", "elev-wall-b.svg", "plan-cone.svg"],
        )
        self.assertEqual(
            second,
            ["elev-wall-b.svg", "elev-wall-c.svg", "plan-cone.svg"],
        )
        self.assertNotIn("elev-wall-c.svg", first)
        self.assertNotIn("elev-wall-a.svg", second)
        self.assertIn("Do not show these walls: wall-c", packets[0].prompt)
        self.assertIn("Do not show these walls: wall-a", packets[1].prompt)
        self.assertNotIn("wall-c", packets[0].walls)
        self.assertEqual(packets[0].exclude, ["wall-c"])

    def test_galley_two_frontals_one_wall_each(self):
        packets = build_packets(galley_spec())
        self.assertEqual(len(packets), 2)
        self.assertEqual([p.camera for p in packets], ["frontal", "frontal"])
        self.assertEqual(packets[0].walls, ["wall-a"])
        self.assertEqual(packets[1].walls, ["wall-b"])
        self.assertEqual(
            [ref.name for ref in packets[0].references],
            ["elev-wall-a.svg", "plan-cone.svg"],
        )
        self.assertEqual(
            [ref.name for ref in packets[1].references],
            ["elev-wall-b.svg", "plan-cone.svg"],
        )
        self.assertNotEqual(
            packets[0].references[-1].data,
            packets[1].references[-1].data,
        )
        self.assertIn("LEFT of frame: wall-a", packets[0].prompt)
        self.assertNotIn("RIGHT of frame", packets[0].prompt)

    def test_rebuild_is_the_same_packet(self):
        spec = l_spec()
        first = build_packets(spec)[0]
        again = packet_for_shot(spec, "shot-1")
        self.assertEqual(first.prompt, again.prompt)
        self.assertEqual(
            [ref.name for ref in first.references],
            [ref.name for ref in again.references],
        )

    def test_render_packet_sends_only_packet_refs(self):
        packet = build_packets(u_spec())[0]
        fake = FakeOpenRouter()
        data, mime = asyncio.run(render_packet(fake, packet))
        self.assertEqual(data, TINY_PNG)
        self.assertEqual(mime, "image/png")
        sent = fake.image_calls[0]
        self.assertEqual(sent["prompt"], packet.prompt)
        self.assertEqual(len(sent["reference_images"]), 3)
        self.assertEqual(
            [item["data"] for item in sent["reference_images"]],
            [ref.data for ref in packet.references],
        )

    def test_rasters_are_png(self):
        spec = l_kitchen_spec()
        job = plan_views(spec).cameras[0]
        elev = png_bytes(elevation_png(spec, "wall-a"))
        cone = png_bytes(plan_cone_png(spec, job))
        self.assertTrue(elev.startswith(b"\x89PNG"))
        self.assertTrue(cone.startswith(b"\x89PNG"))
        self.assertNotEqual(
            png_bytes(elevation_png(spec, "wall-a")),
            png_bytes(elevation_png(spec, "wall-b")),
        )


if __name__ == "__main__":
    unittest.main()
