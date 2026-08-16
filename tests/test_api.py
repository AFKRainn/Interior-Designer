import shutil
import unittest

from fastapi.testclient import TestClient

from app.agents.brief import Brief
from app.agents.spec_author import SpecAuthor
from app.api.main import app, get_author, get_brief, get_image_client
from app.editor.session import SESSIONS, sessions_dir
from app.services.openrouter import CostTracker, OpenRouterError
from tests.fake_openrouter import TINY_PNG, FakeOpenRouter
from tests.spec_factory import l_kitchen_spec


class ApiTests(unittest.TestCase):
    def setUp(self):
        SESSIONS.clear()
        app.dependency_overrides.clear()
        CostTracker().reset()
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        root = sessions_dir()
        for sid in list(SESSIONS):
            json_path = root / f"{sid}.json"
            if json_path.exists():
                json_path.unlink()
            shot_dir = root / sid
            if shot_dir.is_dir():
                shutil.rmtree(shot_dir)
        SESSIONS.clear()

    def test_health_and_demo(self):
        self.assertTrue(self.client.get("/api/health").json()["ok"])
        data = self.client.post("/api/session/demo").json()
        self.assertEqual(data["phase"], "edit")
        self.assertEqual(len(data["drawings"]["elevations"]), 2)
        self.assertIn("svg", data["drawings"]["plan_svg"])
        self.assertTrue(data["drawings"]["elevations"][0]["dividers"])
        self.assertEqual(data["spec"]["version"], 1)
        self.assertEqual([item["version"] for item in data["spec_versions"]], [1])
        self.assertEqual(data["cost"]["total_cost"], 0)
        self.assertEqual(data["cost"]["total_calls"], 0)

    def test_bay_width_and_lock(self):
        sid = self.client.post("/api/session/demo").json()["id"]
        out = self.client.post(
            f"/api/session/{sid}/spec/bay-width",
            json={"wall_id": "wall-a", "bay_id": "bay-1", "width": 90},
        ).json()
        bays = out["spec"]["walls"][0]["bays"]
        self.assertEqual(bays[0]["width"], 90)
        self.assertEqual(bays[1]["width"], 50)
        self.assertEqual(out["spec"]["version"], 2)
        self.assertEqual([item["version"] for item in out["spec_versions"]], [1, 2])
        version_file = sessions_dir() / out["id"] / "versions" / "v2.json"
        self.assertTrue(version_file.exists())
        locked = self.client.post(f"/api/session/{sid}/lock").json()
        self.assertTrue(locked["locked"])
        blocked = self.client.post(
            f"/api/session/{sid}/spec/bay-width",
            json={"wall_id": "wall-a", "bay_id": "bay-1", "width": 80},
        )
        self.assertEqual(blocked.status_code, 409)

    def test_divider(self):
        sid = self.client.post("/api/session/demo").json()["id"]
        out = self.client.post(
            f"/api/session/{sid}/spec/divider",
            json={"wall_id": "wall-a", "left_bay_id": "bay-1", "delta_cm": 5},
        ).json()
        self.assertEqual(out["spec"]["walls"][0]["bays"][0]["width"], 85)

    def test_brief_then_build(self):
        dump = l_kitchen_spec().model_dump(mode="json")
        dump.pop("brief", None)
        brief_client = FakeOpenRouter([
            {
                "response": "Locked in.",
                "status": "confirmed",
                "brief": "L kitchen sink 300 fridge 180",
            }
        ])
        author_client = FakeOpenRouter([dump])
        app.dependency_overrides[get_brief] = lambda: Brief(client=brief_client)
        app.dependency_overrides[get_author] = lambda: SpecAuthor(client=author_client)
        sid = self.client.post("/api/session").json()["id"]
        started = self.client.post(
            f"/api/session/{sid}/brief/start",
            json={"text": "L kitchen"},
        ).json()
        self.assertEqual(started["phase"], "brief_ready")
        built = self.client.post(f"/api/session/{sid}/spec/build").json()
        self.assertEqual(built["phase"], "edit")
        self.assertEqual(len(built["drawings"]["elevations"]), 2)

    def test_render_requires_lock(self):
        fake = FakeOpenRouter()
        app.dependency_overrides[get_image_client] = lambda: fake
        sid = self.client.post("/api/session/demo").json()["id"]
        blocked = self.client.post(f"/api/session/{sid}/render")
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(fake.image_calls, [])

    def test_render_and_regenerate_same_packet(self):
        fake = FakeOpenRouter()
        app.dependency_overrides[get_image_client] = lambda: fake
        sid = self.client.post("/api/session/demo").json()["id"]
        self.client.post(f"/api/session/{sid}/lock")
        out = self.client.post(f"/api/session/{sid}/render").json()
        self.assertEqual(len(out["renders"]), 1)
        shot = out["renders"][0]
        self.assertEqual(shot["shot_id"], "shot-1")
        self.assertEqual(shot["camera"], "inside_corner")
        self.assertEqual(shot["walls"], ["wall-a", "wall-b"])
        self.assertEqual(
            shot["references"],
            ["elev-wall-a.svg", "elev-wall-b.svg", "plan-cone.svg"],
        )
        self.assertEqual(shot["data"], TINY_PNG)
        self.assertEqual(len(fake.image_calls), 1)
        self.assertEqual(len(fake.image_calls[0]["reference_images"]), 3)

        skipped = self.client.post(f"/api/session/{sid}/render").json()
        self.assertEqual(len(skipped["renders"]), 1)
        self.assertEqual(len(fake.image_calls), 1)

        again = self.client.post(f"/api/session/{sid}/render/shot-1").json()
        self.assertEqual(len(again["renders"]), 1)
        self.assertEqual(len(fake.image_calls), 2)
        self.assertEqual(fake.image_calls[0]["prompt"], fake.image_calls[1]["prompt"])
        self.assertEqual(
            len(fake.image_calls[0]["reference_images"]),
            len(fake.image_calls[1]["reference_images"]),
        )
        missing = self.client.post(f"/api/session/{sid}/render/shot-99")
        self.assertEqual(missing.status_code, 404)

    def test_openrouter_error_is_json_detail(self):
        class Boom(FakeOpenRouter):
            async def chat_completion(self, **kwargs):
                raise OpenRouterError(
                    402,
                    '{"error":{"message":"need credits"}}',
                )

        app.dependency_overrides[get_brief] = lambda: Brief(client=Boom())
        sid = self.client.post("/api/session").json()["id"]
        out = self.client.post(
            f"/api/session/{sid}/brief/start",
            json={"text": "yes"},
        )
        self.assertEqual(out.status_code, 402)
        self.assertEqual(out.json()["detail"], "need credits")


if __name__ == "__main__":
    unittest.main()
