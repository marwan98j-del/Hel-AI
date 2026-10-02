import re
import unittest
from pathlib import Path


CONFIG = (Path(__file__).resolve().parent / ".streamlit" / "config.toml").read_text(encoding="utf-8")


def section(name):
    match = re.search(rf"^\[{re.escape(name)}\]\n(.*?)(?=^\[|\Z)", CONFIG, re.M | re.S)
    return match.group(1) if match else ""


class ServerConfigTests(unittest.TestCase):
    def test_server_listens_on_localhost_only(self):
        # The tunnel connects to localhost; nothing else on the network may.
        self.assertRegex(section("server"), re.compile(r'^address = "localhost"$', re.M))

    def test_static_file_serving_stays_off(self):
        self.assertNotRegex(section("server"), re.compile(r"^enableStaticServing\s*=\s*true", re.M))


if __name__ == "__main__":
    unittest.main()
