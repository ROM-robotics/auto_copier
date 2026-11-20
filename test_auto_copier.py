from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from auto_copier import AutoPasswordZipCopierApp


@unittest.skipUnless(shutil.which("git"), "git is required for ignore matching")
class GitignoreSelectionTests(unittest.TestCase):
  def setUp(self):
    self.app = AutoPasswordZipCopierApp.__new__(AutoPasswordZipCopierApp)
    self.temp_dir = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp_dir.cleanup)
    self.root = Path(self.temp_dir.name)

  def test_git_source_uses_only_source_gitignore(self):
    source = self.root / "source"
    source.mkdir()
    (self.root / ".gitignore").write_text("from-parent.txt\n", encoding="utf-8")
    (source / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    (source / "ignored.txt").write_text("ignored", encoding="utf-8")
    (source / "normal.txt").write_text("normal", encoding="utf-8")
    (source / "from-parent.txt").write_text("parent rule must not apply", encoding="utf-8")
    nested = source / "nested"
    nested.mkdir()
    (nested / ".gitignore").write_text("nested-only.txt\n", encoding="utf-8")
    (nested / "nested-only.txt").write_text("nested rule must not apply", encoding="utf-8")
    subprocess.run(["git", "-C", str(self.root), "init", "--quiet"], check=True)
    subprocess.run(
        ["git", "-C", str(self.root), "add", "source/.gitignore", "source/normal.txt"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(self.root), "add", "--force", "source/ignored.txt"],
        check=True,
    )

    included, skipped = self.app._git_paths_to_zip(str(source))

    self.assertEqual(
        set(included),
        {
            ".gitignore",
            "normal.txt",
            "from-parent.txt",
            "nested/.gitignore",
            "nested/nested-only.txt",
        },
    )
    self.assertIn("ignored.txt", skipped)

  def test_non_git_source_expands_root_ignore_rules(self):
    source = self.root / "plain"
    (source / "ignored-dir").mkdir(parents=True)
    (source / "nested").mkdir()
    (source / ".gitignore").write_text(
        "ignored-dir/\n*.tmp\n!keep.tmp\n",
        encoding="utf-8",
    )
    (source / "ignored-dir" / "inside.txt").write_text("ignored", encoding="utf-8")
    (source / "drop.tmp").write_text("ignored", encoding="utf-8")
    (source / "keep.tmp").write_text("included", encoding="utf-8")
    (source / "nested" / "nested.tmp").write_text("ignored", encoding="utf-8")

    ignored = self.app._gitignore_paths_in_tree(str(source))

    self.assertEqual(
        ignored,
        {
            "plain/ignored-dir",
            "plain/ignored-dir/inside.txt",
            "plain/drop.tmp",
            "plain/nested/nested.tmp",
        },
    )

  @unittest.skipUnless(shutil.which("7z"), "7z is required for archive integration")
  def test_non_git_archive_omits_ignored_paths(self):
    source = self.root / "plain"
    ignored_dir = source / "ignored-dir"
    ignored_dir.mkdir(parents=True)
    (source / ".gitignore").write_text(
          "ignored-dir/\n*.tmp\n!keep.tmp\n",
          encoding="utf-8",
    )
    (ignored_dir / "inside.txt").write_text("ignored", encoding="utf-8")
    (source / "drop.tmp").write_text("ignored", encoding="utf-8")
    (source / "keep.tmp").write_text("included", encoding="utf-8")
    (source / "normal.txt").write_text("included", encoding="utf-8")
    destination = self.root / "destination"

    class Entry:
        def __init__(self, value):
          self.value = str(value)

        def get(self):
          return self.value

    class Root:
        def after(self, _delay, callback):
          callback()

    app = self.app
    app.src_entry = Entry(source)
    app.dst_entry = Entry(destination)
    app.ver_entry = Entry("v1")
    app.root = Root()
    app._job_id = 1
    app._closing_after_success = False
    app._report_progress = lambda _percent, _job_id: None
    app._headers_require_password = lambda _archive: True
    app.show_password_dialog = lambda *_args, **_kwargs: None

    app.process_zip_and_copy(1)

    archives = list(destination.glob("plain_v1_*.7z"))
    self.assertEqual(len(archives), 1)
    archive = archives[0]
    self.assertRegex(archive.name, r"^plain_v1_\d{8}_\d{6}\.7z$")
    extracted = self.root / "extracted"
    password = archive.name[::-1]
    subprocess.run(
          ["7z", "x", "-y", f"-p{password}", f"-o{extracted}", str(archive)],
          stdout=subprocess.PIPE,
          stderr=subprocess.STDOUT,
          check=True,
    )
    unpacked = extracted / "plain"
    self.assertTrue((unpacked / "keep.tmp").is_file())
    self.assertTrue((unpacked / "normal.txt").is_file())
    self.assertFalse((unpacked / "drop.tmp").exists())
    self.assertFalse((unpacked / "ignored-dir").exists())


if __name__ == "__main__":
  unittest.main()
