import unittest
from types import SimpleNamespace

from translation_service import build_translation_prompt, translate_opportunity


class _FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text="کورتەی کوردی")


class KurdishTerminologyPromptTests(unittest.TestCase):
    def test_prompt_states_the_three_terms(self):
        prompt = build_translation_prompt("Title: Example Scholarship 2027")
        self.assertIn('For "opportunity" always write هەل', prompt)
        self.assertIn("Never write دەرفەت", prompt)
        self.assertIn('For "scholarship" always write سکۆڵەرشیپ', prompt)
        self.assertIn("Never write بورسیە or بۆرسیە", prompt)
        self.assertIn('For "fellowship" always write فێلۆشیپ', prompt)
        self.assertIn("Title: Example Scholarship 2027", prompt)

    def test_translation_sends_the_prompt_with_terminology(self):
        # Fake client: no OpenAI call, no Supabase write.
        responses = _FakeResponses()
        client = SimpleNamespace(responses=responses)
        opportunity = {"title": "Example Scholarship 2027", "organization": "Example Foundation"}

        self.assertEqual(translate_opportunity(client, opportunity), "کورتەی کوردی")
        sent = responses.calls[0]["input"]
        self.assertIn("سکۆڵەرشیپ", sent)
        self.assertIn("هەل", sent)
        self.assertIn("فێلۆشیپ", sent)


if __name__ == "__main__":
    unittest.main()
