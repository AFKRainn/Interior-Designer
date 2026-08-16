import json
import unittest

from app.agents.brief import Brief
from app.json_parse import parse_json_from_text
from config import BRIEF_MODEL
from tests.fake_openrouter import FakeOpenRouter


class BriefTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_returns_chat(self):
        client = FakeOpenRouter([
            {"response": "What is the layout — straight, L, or U?", "status": "chat"}
        ])
        brief = Brief(client=client)
        out = await brief.start("I want a kitchen")
        self.assertEqual(out["status"], "chat")
        self.assertIsNone(out["brief"])
        self.assertIn("layout", out["response"].lower())
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["model"], BRIEF_MODEL["id"])

    async def test_confirmed_includes_brief(self):
        client = FakeOpenRouter([
            {
                "response": "Locked in.",
                "status": "confirmed",
                "brief": "Straight run wardrobe, 200 cm wide, 60 deep, 220 high.",
            }
        ])
        brief = Brief(client=client)
        out = await brief.start("wardrobe 200cm")
        self.assertEqual(out["status"], "confirmed")
        self.assertIn("200 cm", out["brief"])

    async def test_confirmed_without_brief_stays_chat(self):
        client = FakeOpenRouter([{"response": "Done", "status": "confirmed"}])
        brief = Brief(client=client)
        out = await brief.start("hello")
        self.assertEqual(out["status"], "chat")
        self.assertIsNone(out["brief"])

    async def test_thats_enough_triggers_synthesis(self):
        client = FakeOpenRouter([
            {"response": "One more thing?", "status": "chat"},
            {
                "response": "Thanks.",
                "status": "confirmed",
                "brief": "Straight cabinet 120 cm, default cornice straight 8 cm.",
            },
        ])
        brief = Brief(client=client)
        first = await brief.start("a cabinet")
        out = await brief.reply(first["messages"], "that's enough")
        self.assertEqual(out["status"], "confirmed")
        self.assertTrue(out["brief"])
        self.assertEqual(len(client.calls), 2)

    async def test_notice_is_kept_in_history(self):
        client = FakeOpenRouter([
            {
                "notice": [
                    {
                        "q": "What is this piece?",
                        "a": "Tall laundry cabinet",
                    }
                ],
                "response": "Washer size — 60 cm standard, or do you have a model?",
                "status": "chat",
            }
        ])
        brief = Brief(client=client)
        out = await brief.start("tall utility with washer and dryer")
        last = json.loads(out["messages"][-1]["content"])
        self.assertEqual(last["notice"][0]["a"], "Tall laundry cabinet")
        self.assertNotIn("Tall laundry cabinet", out["response"])

    async def test_sketch_sends_image_part(self):
        client = FakeOpenRouter([
            {"response": "I see a run of cabinets. Cornice — straight, stepped, or ogee?", "status": "chat"}
        ])
        brief = Brief(client=client)
        await brief.start(
            "this sketch",
            images=[{"data": "aaa", "mime_type": "image/png"}],
        )
        content = client.calls[0]["messages"][1]["content"]
        self.assertIsInstance(content, list)
        types = [part["type"] for part in content]
        self.assertIn("text", types)
        self.assertIn("image_url", types)
        self.assertTrue(
            content[1]["image_url"]["url"].startswith("data:image/png;base64,")
        )

    async def test_reply_can_attach_more_photos(self):
        client = FakeOpenRouter([
            {"response": "Got the first crop.", "status": "chat"},
            {"response": "That fills the top that was out of frame.", "status": "chat"},
        ])
        brief = Brief(client=client)
        first = await brief.start("this sketch", images=[{"data": "aaa", "mime_type": "image/png"}])
        out = await brief.reply(
            first["messages"],
            "top of the same unit",
            images=[{"data": "bbb", "mime_type": "image/jpeg"}],
        )
        self.assertEqual(out["status"], "chat")
        content = client.calls[1]["messages"][-1]["content"]
        self.assertIsInstance(content, list)
        self.assertEqual(content[0]["text"], "top of the same unit")
        self.assertTrue(
            content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        )

    async def test_start_sends_several_crops(self):
        client = FakeOpenRouter([
            {"response": "Two crops of one tall unit.", "status": "chat"}
        ])
        brief = Brief(client=client)
        await brief.start(
            "same cabinet",
            images=[
                {"data": "aaa", "mime_type": "image/png"},
                {"data": "bbb", "mime_type": "image/png"},
            ],
        )
        content = client.calls[0]["messages"][1]["content"]
        types = [part["type"] for part in content]
        self.assertEqual(types.count("image_url"), 2)


class JsonParseSmoke(unittest.TestCase):
    def test_fenced_json(self):
        parsed = parse_json_from_text('```json\n{"status": "chat"}\n```')
        self.assertEqual(parsed["status"], "chat")


if __name__ == "__main__":
    unittest.main()
