"""Message archive regressions using FakeHerdr and real files, never live panes."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("archive_base", Path(__file__).with_name("test_herdr_lab.py"))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

class MessageArchiveTests(base.AdapterTests):
    def test_distinct_message_suffixes_preserve_every_original(self):
        self.send("first")
        first = self.lab.load("fixture-run")["messages"]["first"]
        paths = [Path(first[field]) for field in ("body_file", "rendered_template_file", "prompt_file")]
        originals = [path.read_bytes() for path in paths]
        self.send("first-role")
        self.send("first-prompt")
        self.assertEqual(self.fake.prompt_calls, 3)
        for path, original in zip(paths, originals):
            self.assertEqual(path.read_bytes(), original)
        self.assertEqual(base.lab_module.digest(paths[2].read_bytes()), first["prompt_sha256"])

    @unittest.skipUnless(os.name == "nt", "Windows case-insensitive path regression")
    def test_windows_case_alias_does_not_overwrite_or_dispatch(self):
        self.send("alpha")
        first = self.lab.load("fixture-run")["messages"]["alpha"]
        paths = [Path(first[field]) for field in ("body_file", "rendered_template_file", "prompt_file")]
        originals = [path.read_bytes() for path in paths]
        self.body.write_text("Distinct operation must not replace alpha evidence", encoding="utf-8")
        with self.assertRaises(base.lab_module.LabError):
            self.send("Alpha")
        self.assertEqual(self.fake.prompt_calls, 1)
        self.assertEqual(set(self.lab.load("fixture-run")["messages"]), {"alpha"})
        for path, original in zip(paths, originals):
            self.assertEqual(path.read_bytes(), original)
        self.assertEqual(base.lab_module.digest(paths[2].read_bytes()), first["prompt_sha256"])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-root", required=True)
    args = parser.parse_args()
    root = Path(args.test_root)
    if not root.is_absolute():
        parser.error("test-root must be absolute")
    root = root.resolve()
    installed = Path(__file__).resolve().parents[2]
    if root == installed or installed in root.parents:
        parser.error("test-root must stay outside the installed skill")
    root.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(root)
    names = ["test_distinct_message_suffixes_preserve_every_original", "test_windows_case_alias_does_not_overwrite_or_dispatch"]
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(MessageArchiveTests(name) for name in names))
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    raise SystemExit(main())
