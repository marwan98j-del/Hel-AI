import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helai_env


HERE = Path(__file__).resolve().parent

FAKE_ENV = {
    "SUPABASE_URL": "https://fake-project.supabase.co",
    "SUPABASE_KEY": "sb_publishable_fake",
    "OPENAI_API_KEY": "sk-fake-openai",
    "SUPABASE_SECRET_KEY": "sb_secret_fake",
    "RESEND_API_KEY": "re_fake",
    "TELEGRAM_BOT_TOKEN": "123:fake-telegram",
    "TELEGRAM_TEST_CHAT_ID": "42",
    "TELEGRAM_TEST_MODE": "true",
    "EMAIL_TEST_RECIPIENT": "tester@example.com",
    "HELAI_MATCH_THRESHOLD": "50",
}
APP_VISIBLE = {"SUPABASE_URL", "SUPABASE_KEY", "OPENAI_API_KEY", "HELAI_MATCH_THRESHOLD"}
COLLECTOR_MODULES = {"collector_client", "email_service", "telegram_service", "matching_service", "translation_service"}


def app_project_imports():
    """Project modules app.py imports, in order, from its source."""
    tree = ast.parse((HERE / "app.py").read_text(encoding="utf-8"))
    names = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return [name for name in names if (HERE / f"{name}.py").exists()]


def run_python(code, env_file, inherited=None):
    env = dict(os.environ)
    env.update(inherited or {})
    env["HELAI_ENV_FILE"] = str(env_file)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=HERE,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout.strip().splitlines()[-1])


class AppProcessSecretsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.env_file = Path(cls.tmp.name) / ".env"
        cls.env_file.write_text(
            "".join(f"{name}={value}\n" for name, value in FAKE_ENV.items()),
            encoding="utf-8",
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_app_process_holds_only_the_app_secrets(self):
        modules = [name for name in app_project_imports() if name != "helai_env"]
        code = (
            "import importlib, json, os, sys\n"
            "import helai_env\n"
            "helai_env.use_app_secrets()\n"
            f"for name in {modules!r}:\n"
            "    importlib.import_module(name)\n"
            f"names = {sorted(FAKE_ENV)!r}\n"
            "print(json.dumps({'env': {n: os.environ.get(n) for n in names},"
            " 'modules': sorted(sys.modules)}))\n"
        )
        # Collector secrets inherited from the shell must be removed too.
        result = run_python(code, self.env_file, inherited={
            "SUPABASE_SECRET_KEY": "inherited-secret",
            "TELEGRAM_BOT_TOKEN": "inherited-token",
        })

        for name, value in FAKE_ENV.items():
            with self.subTest(name=name):
                if name in APP_VISIBLE:
                    self.assertEqual(result["env"][name], value)
                else:
                    self.assertIsNone(result["env"][name])
        self.assertFalse(COLLECTOR_MODULES & set(result["modules"]))

    def test_link_check_child_gets_the_token_the_app_never_holds(self):
        # The same start-up as telegram_link_now.py, launched from app mode.
        code = (
            "import json, os, subprocess, sys\n"
            "import helai_env\n"
            "helai_env.use_app_secrets()\n"
            "import telegram_link\n"
            "child = subprocess.run([sys.executable, '-c',"
            " 'import helai_env, os; helai_env.load_env();"
            " print(os.environ.get(\"TELEGRAM_BOT_TOKEN\"))'],"
            " capture_output=True, text=True, check=True)\n"
            "print(json.dumps({'app': os.environ.get('TELEGRAM_BOT_TOKEN'),"
            " 'child': child.stdout.strip()}))\n"
        )
        result = run_python(code, self.env_file)
        self.assertIsNone(result["app"])
        self.assertEqual(result["child"], FAKE_ENV["TELEGRAM_BOT_TOKEN"])

    def test_link_now_script_starts_like_a_collector_script(self):
        tree = ast.parse((HERE / "telegram_link_now.py").read_text(encoding="utf-8"))
        source = ast.unparse(tree)
        self.assertNotIn("use_app_secrets", source)
        self.assertIn("from telegram_service import", source)

    def test_collector_process_still_loads_everything(self):
        code = (
            "import json, os\n"
            "import helai_env\n"
            "helai_env.load_env()\n"
            f"print(json.dumps({{n: os.environ.get(n) for n in {sorted(FAKE_ENV)!r}}}))\n"
        )
        self.assertEqual(run_python(code, self.env_file), FAKE_ENV)


class AppSourceTests(unittest.TestCase):
    def test_app_switches_to_app_secrets_before_any_project_import(self):
        tree = ast.parse((HERE / "app.py").read_text(encoding="utf-8"))
        switch = next(
            node.lineno for node in tree.body
            if isinstance(node, ast.Expr)
            and ast.unparse(node.value) == "helai_env.use_app_secrets()"
        )
        first_project_import = next(
            node.lineno for node in tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module
            and (HERE / f"{node.module}.py").exists()
        )
        self.assertLess(switch, first_project_import)

    def test_only_helai_env_loads_dotenv(self):
        tracked = subprocess.run(
            ["git", "ls-files", "*.py"], cwd=HERE, capture_output=True, text=True, check=True,
        ).stdout.split()
        for name in tracked:
            if name in {"helai_env.py"} or name.startswith("test_"):
                continue
            with self.subTest(file=name):
                self.assertNotIn("load_dotenv", (HERE / name).read_text(encoding="utf-8"))


class AllowListTests(unittest.TestCase):
    def test_allow_list(self):
        for name in ("SUPABASE_URL", "SUPABASE_KEY", "OPENAI_API_KEY", "HELAI_APP_URL", "TELEGRAM_BOT_USERNAME"):
            self.assertTrue(helai_env.app_allows(name), name)
        for name in ("SUPABASE_SECRET_KEY", "RESEND_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_TEST_CHAT_ID",
                     "EMAIL_TEST_RECIPIENT", "TELEGRAM_TEST_MODE", "ANYTHING_ELSE"):
            self.assertFalse(helai_env.app_allows(name), name)


if __name__ == "__main__":
    unittest.main()
