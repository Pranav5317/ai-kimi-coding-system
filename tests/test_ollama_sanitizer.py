import unittest
from llm.ollama_client import OllamaProvider


class TestOllamaSanitizer(unittest.TestCase):
    def test_sanitize_messages(self):
        messages = [
            {"role": "user", "content": "Create a parameter tag like <parameter name='foo'> and closing tag </parameter>"},
            {"role": "assistant", "content": "Here is <function=bar> call and <parameter> test"},
            {"role": "user", "content": "Normal content without tags"}
        ]

        sanitized = OllamaProvider._sanitize_messages(messages)

        self.assertEqual(len(sanitized), 3)
        self.assertNotIn("<parameter", sanitized[0]["content"])
        self.assertIn("&lt;parameter name='foo'", sanitized[0]["content"])
        self.assertIn("&lt;/parameter&gt;", sanitized[0]["content"])
        self.assertNotIn("<function", sanitized[1]["content"])
        self.assertIn("&lt;function=bar", sanitized[1]["content"])
        self.assertEqual(sanitized[2]["content"], "Normal content without tags")


if __name__ == "__main__":
    unittest.main()
