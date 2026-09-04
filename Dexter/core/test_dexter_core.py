"""
Smoke test suite for Dexter core modules.
"""

import sys
import unittest
from pathlib import Path

# Add Dexter root to path (this resolves to Dexter/, not DEV/ — core/ is one level
# under Dexter/, and Dexter/ itself is what needs to be on sys.path for `core.*` imports)
DEXTER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEXTER_ROOT))

from core.config import settings
from core.vault_bridge import VaultBridge
from core.memory_sync import MemorySync
from core.dispatcher import TaskDispatcher


class TestDexterCore(unittest.TestCase):
    def setUp(self):
        self.vault = VaultBridge()
        self.memory = MemorySync(self.vault)
        self.dispatcher = TaskDispatcher()

    def test_vault_structure(self):
        """Verify standard vault directories are created."""
        self.assertTrue(settings.vault_path.exists())
        self.assertTrue(settings.inbox_dir.exists())
        self.assertTrue(settings.agents_dir.exists())
        self.assertTrue(settings.active_tasks_dir.exists())
        self.assertTrue(settings.completed_tasks_dir.exists())
        self.assertTrue(settings.memory_dir.exists())

    def test_markdown_parsing_and_serialization(self):
        """Test YAML frontmatter parsing and reconstruction."""
        sample_content = "---\ntitle: 'Test Task'\ntype: task\npriority: high\n---\n\n# Body Heading\nThis is content."
        meta, body = self.vault.parse_markdown(sample_content)
        self.assertEqual(meta.get("title"), "Test Task")
        self.assertEqual(meta.get("priority"), "high")
        self.assertIn("# Body Heading", body)

        serialized = self.vault.serialize_markdown(meta, body)
        self.assertIn("title: Test Task", serialized)
        self.assertIn("# Body Heading", serialized)

    def test_task_lifecycle(self):
        """Test creating, reading, listing, and completing a task note."""
        task_path = self.vault.create_task(
            title="Unit Test Task",
            description="Testing Dexter automated task management",
            priority="low",
            assigned_agent="test_agent"
        )
        self.assertTrue(task_path.exists())

        # Read back
        meta, body = self.vault.read_note(task_path)
        self.assertEqual(meta.get("title"), "Unit Test Task")
        self.assertEqual(meta.get("assigned_agent"), "test_agent")

        # List tasks
        tasks = self.vault.list_tasks(settings.active_tasks_dir)
        self.assertTrue(any(t["file_name"] == task_path.name for t in tasks))

        # Complete task
        completed_path = self.vault.complete_task(task_path, agent_summary="Completed successfully in unit test.")
        self.assertTrue(completed_path.exists())
        self.assertFalse(task_path.exists())

        # Verify completed contents
        comp_meta, comp_body = self.vault.read_note(completed_path)
        self.assertEqual(comp_meta.get("status"), "completed")
        self.assertIn("Completed successfully in unit test", comp_body)

        # Cleanup
        completed_path.unlink()

    def test_memory_sync(self):
        """Test reading shared context and building unified prompts."""
        prompt = self.memory.build_unified_system_prompt(agent_role="Test Role")
        self.assertIn("Dexter Agent Directives (Test Role)", prompt)
        self.assertIn("System Directives", prompt)

    def test_dispatcher_routing(self):
        """Test intelligent model routing heuristics."""
        self.assertEqual(self.dispatcher.route_model("refactor files and run tests"), "claude-code")
        self.assertEqual(self.dispatcher.route_model("analyze notes across the vault"), "gemini")
        self.assertEqual(self.dispatcher.route_model("complex architectural design pattern"), "claude")
        self.assertEqual(self.dispatcher.route_model("any general task", forced_target="antigravity"), "antigravity")


if __name__ == "__main__":
    unittest.main()
