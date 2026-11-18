import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ai.tools import computer


class ComputerToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.roots = patch.object(computer, "ROOTS", [self.root])
        self.roots.start()
        self.addCleanup(self.roots.stop)
        self.approvals = self.root / "approvals.json"
        config = patch.object(computer, "COMMAND_APPROVALS", self.approvals)
        config.start()
        self.addCleanup(config.stop)

    def test_find_project_skips_dependencies_and_symlinks(self):
        project = self.root / "Projects" / "SPEC2RTL"
        project.mkdir(parents=True)
        (self.root / "node_modules" / "SPEC2RTL").mkdir(parents=True)
        (self.root / "linked-SPEC2RTL").symlink_to(project)
        result = computer.find_local_items.invoke({"name": "spec2rtl", "kind": "directory"})
        self.assertEqual(result, str(project))

    @patch("ai.tools.computer.subprocess.run")
    def test_open_project_uses_exact_path_and_editor(self, run):
        run.return_value.stdout = ""
        project = self.root / "SPEC2RTL space"
        project.mkdir()
        result = computer.open_project.invoke({"path": str(project)})
        self.assertIn("Opened", result)
        self.assertEqual(run.call_args.args[0], ["open", "-a", "Visual Studio Code", str(project)])

    def test_move_preserves_bytes_and_refuses_overwrite(self):
        source = self.root / "report.txt"
        source.write_bytes(b"report\x00data")
        destination = self.root / "organized" / "report.txt"
        result = computer.organize_local_file.invoke({"source": str(source), "destination": str(destination)})
        self.assertIn("Moved", result)
        self.assertFalse(source.exists())
        self.assertEqual(destination.read_bytes(), b"report\x00data")
        source.write_text("another")
        result = computer.organize_local_file.invoke({"source": str(source), "destination": str(destination)})
        self.assertIn("already exists", result)
        self.assertEqual(source.read_text(), "another")

    @patch("ai.tools.computer.subprocess.run")
    def test_paths_outside_roots_and_symlink_escapes_are_refused(self, run):
        outside = self.root.parent
        (self.root / "escape").symlink_to(outside)
        for path in (str(outside), str(self.root / "escape")):
            self.assertIn("must be inside", computer.open_project.invoke({"path": path}))
        run.assert_not_called()

    @patch("ai.tools.computer.subprocess.run")
    def test_command_requires_exact_argv_and_cwd(self, run):
        run.return_value.stdout = "started"
        self.approvals.write_text(json.dumps([{"argv": ["npm", "run", "dev"], "cwd": str(self.root)}]))
        result = computer.run_approved_command.invoke({
            "argv": ["npm", "run", "dev"], "working_directory": str(self.root),
        })
        self.assertEqual(result, "started")
        self.assertEqual(run.call_args.kwargs["cwd"], str(self.root))
        self.assertNotIn("shell", run.call_args.kwargs)
        run.reset_mock()
        subfolder = self.root / "other"
        subfolder.mkdir()
        for args, cwd in ((["npm", "run", "dev", "--", "extra"], self.root),
                          (["npm", "run", "dev"], subfolder),
                          (["sh", "-c", "echo bad"], self.root)):
            result = computer.run_approved_command.invoke({"argv": args, "working_directory": str(cwd)})
            self.assertIn("not approved", result)
        run.assert_not_called()

    def test_builtin_command_runs_without_config(self):
        result = computer.run_approved_command.invoke({"argv": ["pwd"], "working_directory": str(self.root)})
        self.assertEqual(result, str(self.root))

    @patch("ai.tools.computer.subprocess.run")
    def test_command_failures_and_timeouts_return_status(self, run):
        for error, expected in ((subprocess.TimeoutExpired("pwd", 60), "timed out"),
                                (subprocess.CalledProcessError(1, "pwd", stderr="failure"), "failure")):
            run.side_effect = error
            result = computer.run_approved_command.invoke({"argv": ["pwd"], "working_directory": str(self.root)})
            self.assertIn(expected, result)

    @patch("ai.tools.computer.subprocess.run")
    def test_window_and_settings_use_structured_arguments(self, run):
        run.return_value.stdout = "Window minimized."
        computer.manage_app_window.invoke({"app_name": "vscode", "action": "minimize"})
        self.assertEqual(run.call_args.args[0][2:4], ["Visual Studio Code", "minimize"])
        self.assertIn("AXMinimized", run.call_args.kwargs["input"])
        computer.open_system_settings.invoke({"section": "privacy"})
        self.assertEqual(run.call_args.args[0], ["open", "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension"])

    @patch("ai.agents.system_agent.create_agent")
    @patch("ai.agents.system_agent.get_llm")
    def test_system_agent_exposes_all_computer_tools(self, llm, create):
        from ai.agents.system_agent import system_agent
        system_agent()
        names = {tool.name for tool in create.call_args.kwargs["tools"]}
        self.assertTrue({"find_local_items", "organize_local_file", "open_project",
                         "run_approved_command", "manage_app_window", "open_system_settings"} <= names)
