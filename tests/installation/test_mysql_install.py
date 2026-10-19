#!/usr/bin/env python3
"""Exercise the installer with a fake mysql executable; never connect to a DB."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/mysql_install.sh"
PASSWORD = 'fixture\\root"password#;\t'
FAKE_MYSQL = r'''#!/usr/bin/python3
import json, os, pathlib, signal, stat, sys
args = sys.argv[1:]
entry = {"args": args, "pwd_in_environment": "MYSQL_PWD" in os.environ,
         "cwd": str(pathlib.Path.cwd())}
if args and args[0].startswith("--defaults-extra-file="):
    defaults = pathlib.Path(args[0].split("=", 1)[1])
    entry.update(defaults=str(defaults), mode=stat.S_IMODE(defaults.stat().st_mode),
                 contents=defaults.read_text())
if "-e" not in args:
    entry["input"] = sys.stdin.read()
log = pathlib.Path(os.environ["FIXTURE_LOG"])
with log.open("a") as stream:
    stream.write(json.dumps(entry) + "\n")
count = len(log.read_text().splitlines())
if os.environ.get("FIXTURE_SIGNAL"):
    os.kill(os.getppid(), signal.SIGTERM)
if count == int(os.environ.get("FIXTURE_FAIL_AT", "0")):
    sys.exit(7)
'''


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bs-mysql-install-")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        (self.work / "bin").mkdir()
        (self.work / "private").mkdir()
        for language in ("en", "ro", "it"):
            folder = self.work / "data" / language
            folder.mkdir(parents=True)
            (folder / "sq_mysql.txt").write_text("SELECT 'language';\n")
        (self.work / "data/blueseer.schema").write_text("SELECT 'schema';\n")
        executable = self.work / "bin/mysql"
        executable.write_text(FAKE_MYSQL)
        executable.chmod(0o755)
        self.log = self.work / "calls.jsonl"

    def install(self, host="db.fixture.invalid", database="custom_db", language="ro",
                confirmation="yes", fail_at=0, terminate=False):
        result = subprocess.run(
            ["bash", str(SCRIPT)], cwd=self.work,
            input="\n".join((confirmation, host, PASSWORD, database, language)) + "\n",
            text=True, capture_output=True, timeout=10,
            env={**os.environ, "PATH": str(self.work / "bin") + os.pathsep + os.defpath,
                 "TMPDIR": str(self.work / "private"), "FIXTURE_LOG": str(self.log),
                 "FIXTURE_FAIL_AT": str(fail_at), "FIXTURE_SIGNAL": "yes" if terminate else "",
                 "MYSQL_PWD": "inherited-fixture-value"})
        calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        self.assertEqual([], list((self.work / "private").glob("blueseer-mysql.*")), "temporary credential file leaked")
        for call in calls:
            self.assertFalse(Path(call["defaults"]).exists())
        return result, calls

    def config(self):
        return dict(line.split("=", 1) for line in (self.work / "bs.cfg").read_text().splitlines())

    def test_remote_host_and_selected_database(self):
        result, calls = self.install()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(8, len(calls))
        for call in calls:
            self.assertIn("--host=db.fixture.invalid", call["args"])
            self.assertIn("--user=root", call["args"])
        queries = [call["args"][call["args"].index("-e") + 1] for call in calls if "-e" in call["args"]]
        self.assertIn("grant select,insert,delete,update on `custom_db`.* to 'bs_user'@'%';", queries)
        self.assertEqual(["custom_db", "custom_db"], [call["args"][-1] for call in calls if "input" in call])
        self.assertEqual("SELECT 'schema';\n", calls[6]["input"])
        self.assertEqual("SELECT 'language';\n", calls[7]["input"])
        self.assertEqual("custom_db", self.config()["DB"])
        self.assertEqual("db.fixture.invalid", self.config()["IP"])

    def test_credentials_are_private_escaped_and_removed(self):
        result, calls = self.install()
        self.assertEqual(0, result.returncode, result.stderr)
        for call in calls:
            self.assertEqual(0o600, call["mode"])
            self.assertEqual('[client]\npassword="fixture\\\\root\\"password#;\\t"\n', call["contents"])
            self.assertFalse(call["pwd_in_environment"])
            self.assertNotIn(PASSWORD, " ".join(call["args"]))
        self.assertNotIn(PASSWORD, result.stdout + result.stderr)

    def test_defaults(self):
        result, calls = self.install(host="", database="", language="")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("--host=localhost", calls[0]["args"])
        self.assertEqual("bsdb", self.config()["DB"])
        self.assertEqual("en", self.config()["LANGUAGE"])
        self.assertEqual("US", self.config()["COUNTRY"])

    def test_romanian_and_italian_country(self):
        for language, country in (("ro", "RO"), ("IT", "IT")):
            with self.subTest(language=language):
                result, _ = self.install(language=language)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(language.lower(), self.config()["LANGUAGE"])
                self.assertEqual(country, self.config()["COUNTRY"])

    def test_cancellation_has_no_side_effects(self):
        result, calls = self.install(confirmation="no")
        self.assertEqual(0, result.returncode)
        self.assertEqual([], calls)
        self.assertFalse((self.work / "bs.cfg").exists())

    def test_missing_language_stops_before_mysql(self):
        result, calls = self.install(language="zz")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual([], calls)
        self.assertFalse((self.work / "bs.cfg").exists())

    def test_invalid_database_stops_before_mysql(self):
        result, calls = self.install(database="bsdb; DROP DATABASE other")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual([], calls)

    def test_mysql_failure_stops_and_cleans_credentials(self):
        for fail_at in (1, 7, 8):
            with self.subTest(fail_at=fail_at):
                self.log.unlink(missing_ok=True)
                result, calls = self.install(fail_at=fail_at)
                self.assertEqual(7, result.returncode)
                self.assertEqual(fail_at, len(calls))
                self.assertNotIn("Finished install!", result.stdout)

    def test_termination_cleans_credentials(self):
        result, calls = self.install(terminate=True)
        self.assertEqual(143, result.returncode)
        self.assertEqual(1, len(calls))
        self.assertNotIn("Finished install!", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
