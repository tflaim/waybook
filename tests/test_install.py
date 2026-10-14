"""install.sh creates a venv and a ~/.local/bin symlink under a temporary HOME."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "install.sh"
_OLD_INTERPRETER = """\
#!/bin/sh
if [ "$1" = "-c" ]; then
    printf '%s\\n' '3.9.6'
    exit 0
fi
exit 1
"""
_PYTHON_NAMES = ("python3.13", "python3.12", "python3.11", "python3")


def _env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("PYTHONPATH", None)
    env.pop("WAYBOOK_NOW", None)
    env.pop("WAYBOOK_AGENT", None)
    env.pop("WAYBOOK_ROLE", None)
    # The installer must work without pipx on PATH. Point it at this
    # interpreter so a machine whose python3 is older than 3.11 still passes.
    env["PATH"] = "/usr/bin:/bin"
    env["WAYBOOK_PYTHON"] = sys.executable
    return env


def _run(
    home: Path,
    *args: str,
    env: dict[str, str] | None = None,
    command: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    run_env = _env(home) if env is None else env
    return subprocess.run(
        command if command is not None else ["sh", str(INSTALL), *args],
        cwd=str(ROOT),
        env=run_env,
        capture_output=True,
        text=True,
    )


def _plant_interpreters(directory: Path, good_name: str | None = None) -> None:
    """Install fake 3.9.6 interpreters, optionally with one real versioned name."""
    directory.mkdir(parents=True, exist_ok=True)
    old = directory / "old-python"
    old.write_text(_OLD_INTERPRETER, encoding="utf-8")
    old.chmod(0o755)
    for name in _PYTHON_NAMES:
        link = directory / name
        if link.is_symlink() or link.exists():
            link.unlink()
        if name == good_name:
            link.symlink_to(sys.executable)
        else:
            link.symlink_to(old.name)


def _venv_executable(venv: Path) -> Path:
    for line in (venv / "pyvenv.cfg").read_text(encoding="utf-8").splitlines():
        if line.startswith("executable = "):
            return Path(line.split("=", 1)[1].strip())
    raise AssertionError("pyvenv.cfg has no executable")


class InstallTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name) / "home"
        self.home.mkdir()

    def test_script_does_not_call_pipx(self):
        text = INSTALL.read_text(encoding="utf-8")
        self.assertNotIn("pipx", text)
        mode = INSTALL.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR)

    def test_install_and_rerun_under_temporary_home(self):
        first = _run(self.home)
        self.assertEqual(first.returncode, 0, first.stderr)
        link = self.home / ".local/bin/waybook"
        venv = self.home / ".local/share/waybook/venv"
        self.assertTrue(link.is_symlink(), first.stderr)
        self.assertEqual(os.readlink(link), str(venv / "bin/waybook"))
        shim = venv / "bin/waybook"
        self.assertTrue(shim.is_file())
        shebang = shim.read_text(encoding="utf-8").splitlines()[0]
        self.assertTrue(shebang.startswith("#!"), shebang)
        self.assertIn(str(venv / "bin"), shebang)
        project = self.home / "proj"
        project.mkdir()
        ran = subprocess.run(
            [str(link), "init", "--project-id", "demo"],
            cwd=str(project),
            env=_env(self.home),
            capture_output=True,
            text=True,
        )
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertTrue((project / ".waybook" / "config.toml").is_file())
        again = _run(self.home)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), str(venv / "bin/waybook"))
        reran = subprocess.run(
            [str(link), "verify"],
            cwd=str(project),
            env=_env(self.home),
            capture_output=True,
            text=True,
        )
        self.assertEqual(reran.returncode, 0, reran.stderr)

    def test_warns_when_local_bin_is_not_on_path(self):
        link = self.home / ".local/bin/waybook"
        link.parent.mkdir(parents=True)
        link.write_text("keep\n", encoding="utf-8")
        refused = _run(self.home)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn(f"warning: {self.home / '.local/bin'} is not on PATH", refused.stderr)
        self.assertEqual(link.read_text(encoding="utf-8"), "keep\n")

    def test_no_path_warning_when_local_bin_is_on_path(self):
        link = self.home / ".local/bin/waybook"
        link.parent.mkdir(parents=True)
        link.write_text("keep\n", encoding="utf-8")
        env = _env(self.home)
        env["PATH"] = str(self.home / ".local/bin") + os.pathsep + env["PATH"]
        result = _run(self.home, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("is not on PATH", result.stderr)
        self.assertEqual(link.read_text(encoding="utf-8"), "keep\n")

    def test_refuses_foreign_symlink(self):
        link = self.home / ".local/bin/waybook"
        link.parent.mkdir(parents=True)
        link.symlink_to("/usr/bin/true")
        refused = _run(self.home)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("refusing to overwrite", refused.stderr)
        self.assertEqual(os.readlink(link), "/usr/bin/true")

    def test_repairs_dangling_symlink_into_the_venv(self):
        venv = self.home / ".local/share/waybook/venv"
        link = self.home / ".local/bin/waybook"
        link.parent.mkdir(parents=True)
        link.symlink_to(venv / "bin/waybook.old")
        result = _run(self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.readlink(link), str(venv / "bin/waybook"))
        self.assertTrue((venv / "bin/waybook").is_file())

    def test_repairs_stale_symlink_and_rebuilds_broken_python(self):
        venv = self.home / ".local/share/waybook/venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text("home = /usr\ninclude-system-site-packages = false\n", encoding="utf-8")
        python = venv / "bin/python"
        python.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        python.chmod(0o755)
        link = self.home / ".local/bin/waybook"
        link.parent.mkdir(parents=True)
        link.symlink_to(venv / "bin/python")
        result = _run(self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"rebuilding {venv}", result.stderr)
        self.assertEqual(os.readlink(link), str(venv / "bin/waybook"))
        probe = subprocess.run(
            [str(venv / "bin/python"), "-c", "import waybook"],
            env=_env(self.home),
            capture_output=True,
            text=True,
        )
        self.assertEqual(probe.returncode, 0, probe.stderr)

    def test_refuses_to_replace_a_non_venv_directory(self):
        venv = self.home / ".local/share/waybook/venv"
        venv.mkdir(parents=True)
        marker = venv / "keep.txt"
        marker.write_text("keep\n", encoding="utf-8")
        refused = _run(self.home)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("refusing to overwrite", refused.stderr)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep\n")
        self.assertFalse((self.home / ".local/bin/waybook").exists())

    def test_force_warns_before_removing_a_non_venv_directory(self):
        venv = self.home / ".local/share/waybook/venv"
        venv.mkdir(parents=True)
        marker = venv / "keep.txt"
        marker.write_text("keep\n", encoding="utf-8")
        forced = _run(self.home, "--force")
        self.assertEqual(forced.returncode, 0, forced.stderr)
        self.assertIn(f"warning: removing {venv} because it is not a virtualenv", forced.stderr)
        self.assertFalse(marker.exists())
        self.assertTrue((venv / "bin/waybook").is_file())

    def test_refuses_to_overwrite_without_force(self):
        link = self.home / ".local/bin/waybook"
        link.parent.mkdir(parents=True)
        link.write_text("keep me\n", encoding="utf-8")
        refused = _run(self.home)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("refusing to overwrite", refused.stderr)
        self.assertIn(str(link), refused.stderr)
        self.assertEqual(link.read_text(encoding="utf-8"), "keep me\n")
        self.assertFalse(link.is_symlink())
        self.assertFalse((self.home / ".local/share/waybook/venv").exists())
        forced = _run(self.home, "--force")
        self.assertEqual(forced.returncode, 0, forced.stderr)
        self.assertTrue(link.is_symlink())
        self.assertTrue((self.home / ".local/share/waybook/venv/bin/waybook").is_file())

    def test_rejects_interpreters_older_than_3_11(self):
        bindir = Path(self._tmp.name) / "old-bin"
        _plant_interpreters(bindir)
        env = _env(self.home)
        env.pop("WAYBOOK_PYTHON", None)
        env["PATH"] = str(bindir) + os.pathsep + "/usr/bin:/bin"
        # bash execs the last command of `sh -c '"$0" "$@"'`, so this Python
        # stays the installer's parent. Rejection must not depend on that.
        bash = "/bin/bash"
        if os.access(bash, os.X_OK):
            command = [bash, "-c", '"$0" "$@"', str(INSTALL)]
        else:
            command = ["sh", str(INSTALL)]
        refused = _run(self.home, env=env, command=command)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("No suitable interpreter was found.", refused.stderr)
        self.assertIn("3.9.6", refused.stderr)
        for name in _PYTHON_NAMES:
            self.assertIn(f"Found {name} (", refused.stderr)
        self.assertIn("WAYBOOK_PYTHON", refused.stderr)
        self.assertIn("--python", refused.stderr)
        self.assertIn("3.11", refused.stderr)
        self.assertNotIn("is not on PATH", refused.stderr)
        self.assertFalse((self.home / ".local/share/waybook/venv").exists())
        self.assertFalse((self.home / ".local/bin/waybook").exists())

    def test_prefers_versioned_python_over_old_python3(self):
        bindir = Path(self._tmp.name) / "versioned-bin"
        _plant_interpreters(bindir, good_name="python3.12")
        env = _env(self.home)
        env.pop("WAYBOOK_PYTHON", None)
        env["PATH"] = str(bindir) + os.pathsep + "/usr/bin:/bin"
        result = _run(self.home, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        venv = self.home / ".local/share/waybook/venv"
        self.assertTrue(_venv_executable(venv).samefile(sys.executable))
        self.assertNotIn("old-python", (venv / "pyvenv.cfg").read_text(encoding="utf-8"))

    def test_explicit_interpreter_is_used_when_path_python_is_old(self):
        bindir = Path(self._tmp.name) / "override-bin"
        _plant_interpreters(bindir)
        env = _env(self.home)
        env["PATH"] = str(bindir) + os.pathsep + "/usr/bin:/bin"
        result = _run(self.home, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        venv = self.home / ".local/share/waybook/venv"
        self.assertTrue(_venv_executable(venv).samefile(sys.executable))

    def test_python_flag_overrides_an_old_environment_interpreter(self):
        bindir = Path(self._tmp.name) / "flag-bin"
        _plant_interpreters(bindir)
        env = _env(self.home)
        env["WAYBOOK_PYTHON"] = str(bindir / "old-python")
        env["PATH"] = str(bindir) + os.pathsep + "/usr/bin:/bin"
        forced = _run(self.home, "--python", sys.executable, env=env)
        self.assertEqual(forced.returncode, 0, forced.stderr)
        venv = self.home / ".local/share/waybook/venv"
        self.assertTrue(_venv_executable(venv).samefile(sys.executable))

    def test_refuses_runnable_python_without_pyvenv_cfg(self):
        venv = self.home / ".local/share/waybook/venv"
        (venv / "bin").mkdir(parents=True)
        python = venv / "bin/python"
        python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        python.chmod(0o755)
        marker = venv / "keep.txt"
        marker.write_text("keep\n", encoding="utf-8")
        refused = _run(self.home)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("refusing to overwrite", refused.stderr)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep\n")
        self.assertFalse((self.home / ".local/bin/waybook").exists())

    def test_rebuilds_when_interpreter_is_not_a_virtualenv(self):
        venv = self.home / ".local/share/waybook/venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
        python = venv / "bin/python"
        # Runs, but reports sys.prefix == sys.base_prefix.
        python.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = \"-c\" ]; then\n"
            "  case \"$2\" in\n"
            "    *base_prefix*) exit 1 ;;\n"
            "  esac\n"
            "  exit 0\n"
            "fi\n"
            "exit 1\n",
            encoding="utf-8",
        )
        python.chmod(0o755)
        marker = venv / "keep.txt"
        marker.write_text("keep\n", encoding="utf-8")
        result = _run(self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("not a virtualenv interpreter", result.stderr)
        self.assertFalse(marker.exists())
        probe = subprocess.run(
            [str(venv / "bin/python"), "-c", "import sys; raise SystemExit(0 if sys.prefix != sys.base_prefix else 1)"],
            env=_env(self.home),
            capture_output=True,
            text=True,
        )
        self.assertEqual(probe.returncode, 0, probe.stderr)

    def test_rebuilds_when_existing_venv_python_version_differs(self):
        venv = self.home / ".local/share/waybook/venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text("home = /usr\ninclude-system-site-packages = false\n", encoding="utf-8")
        python = venv / "bin/python"
        python.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = \"-c\" ]; then\n"
            "  case \"$2\" in\n"
            "    *version_info*) printf '%s\\n' '0.0.1'; exit 0 ;;\n"
            "    *base_prefix*) exit 0 ;;\n"
            "  esac\n"
            "  exit 0\n"
            "fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        python.chmod(0o755)
        marker = venv / "keep.txt"
        marker.write_text("keep\n", encoding="utf-8")
        result = _run(self.home, "--python", sys.executable)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("does not match", result.stderr)
        self.assertFalse(marker.exists())
        version = subprocess.run(
            [str(venv / "bin/python"), "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
            env=_env(self.home),
            capture_output=True,
            text=True,
            check=True,
        )
        expected = subprocess.run(
            [sys.executable, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(version.stdout, expected.stdout)

    def test_reuses_existing_venv_when_python_version_matches(self):
        venv = self.home / ".local/share/waybook/venv"
        created = subprocess.run(
            [sys.executable, "-m", "venv", str(venv)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        marker = venv / "keep.txt"
        marker.write_text("keep\n", encoding="utf-8")
        result = _run(self.home, "--python", sys.executable)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("rebuilding", result.stderr)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep\n")
        self.assertTrue((venv / "pyvenv.cfg").is_file())

    def test_requested_old_interpreter_is_rejected(self):
        bindir = Path(self._tmp.name) / "reject-override"
        _plant_interpreters(bindir)
        env = _env(self.home)
        env["WAYBOOK_PYTHON"] = str(bindir / "old-python")
        refused = _run(self.home, env=env)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("3.9.6", refused.stderr)
        self.assertIn("not Python 3.11 or newer", refused.stderr)
        self.assertIn("WAYBOOK_PYTHON", refused.stderr)
        self.assertNotIn("is not on PATH", refused.stderr)
        self.assertFalse((self.home / ".local/share/waybook/venv").exists())


if __name__ == "__main__":
    unittest.main()
