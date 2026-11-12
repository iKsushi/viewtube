"""Isolated packaging contract tests; generated fixtures are never submission logs."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

try:
    from compression import zstd
except ImportError:
    zstd = None


class PackageTests(unittest.TestCase):
    def test_explicit_multiple_sessions_and_rejections(self):
        self.packaging_contract(compressed=False)

    @unittest.skipIf(
        zstd is None, "Compressed fixture generation requires Python 3.14+"
    )
    def test_compressed_native_sessions_preserved(self):
        self.packaging_contract(compressed=True)

    def packaging_contract(self, compressed):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            (root / "scripts").mkdir(parents=True)
            shutil.copy(
                Path(__file__).with_name("package.py"), root / "scripts/package.py"
            )
            for args in [
                ("init",),
                ("add", "."),
                (
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.com",
                    "commit",
                    "-m",
                    "fixture",
                ),
            ]:
                subprocess.run(
                    ["git", "-C", str(root), *args], check=True, capture_output=True
                )
            sessions = []
            for sid in ["fixture-one", "fixture-two"]:
                path = Path(temp) / (
                    f"{sid}.jsonl.zst" if compressed else f"{sid}.jsonl"
                )
                data = (
                    json.dumps({"type": "session_meta", "payload": {"id": sid}}) + "\n"
                ).encode()
                path.write_bytes(zstd.compress(data) if compressed else data)
                sessions.append(path)
            output = Path(temp) / "submission.zip"
            base = [
                sys.executable,
                str(root / "scripts/package.py"),
                "--output",
                str(output),
            ]
            for path in sessions:
                base += ["--session", str(path)]
            self.assertNotEqual(
                subprocess.run(base, check=False, capture_output=True).returncode, 0
            )
            approved = base + [
                "--allow-session-id",
                "fixture-one",
                "--allow-session-id",
                "fixture-two",
            ]
            subprocess.run(approved, check=True, capture_output=True)
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                for path in sessions:
                    self.assertEqual(
                        archive.read("viewtube/ai/sessions/" + path.name),
                        path.read_bytes(),
                    )
                self.assertIn("viewtube/.git/HEAD", archive.namelist())
            self.assertNotEqual(
                subprocess.run(
                    approved + ["--session", str(sessions[0])],
                    check=False,
                    capture_output=True,
                ).returncode,
                0,
            )


if __name__ == "__main__":
    unittest.main()
