from pathlib import Path
from typing import Any, Dict

from src.generator.canvas_manager import CanvasManager
from src.generator.vault_manager import VaultManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DashboardGenerator:
    """Generates the main Dashboard.canvas for the Obsidian Vault."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.vault_manager = VaultManager(config)
        self.canvas_manager = CanvasManager()

    def generate(self) -> Path:
        """Generate the Dashboard.canvas file in the vault root."""
        logger.info("Generating Dashboard.canvas...")

        # 1. Title Node
        self.canvas_manager.add_node(
            node_type="text",
            x=0,
            y=-400,
            width=800,
            height=100,
            text="# 🚀 Job Hunt Dashboard\nYour command center for landing that dream job.",
            color="1",  # Red/Orange usually
        )

        # 2. Jobs Section (Left)
        self.canvas_manager.add_node(
            node_type="group", x=-400, y=-200, width=500, height=800, label="🎯 Active Applications"
        )

        # Add a text node explaining this section
        self.canvas_manager.add_node(
            node_type="text",
            x=-380,
            y=-180,
            width=460,
            height=200,
            text="## Jobs Folder\nReview your [Jobs](Jobs) folder for active applications.\n\n- **To Do**: Check for new listings.\n- **In Progress**: Follow up on applications.",
        )

        # 3. Network Section (Middle)
        self.canvas_manager.add_node(
            node_type="group", x=150, y=-200, width=500, height=800, label="🌐 Professional Network"
        )

        self.canvas_manager.add_node(
            node_type="text",
            x=170,
            y=-180,
            width=460,
            height=200,
            text="## Connections\nManage your [Companies](Companies) and [People](People).\n\n- Reach out to 5 people this week.\n- Research 3 new companies.",
        )

        # 4. Resources/Analysis (Right)
        self.canvas_manager.add_node(
            node_type="group", x=700, y=-200, width=500, height=800, label="📊 Analysis & Resources"
        )

        self.canvas_manager.add_node(
            node_type="text",
            x=720,
            y=-180,
            width=460,
            height=200,
            text="## Insights\nCheck [Analysis](Analysis) for skill gaps and resume feedback.\n\n- Update Resume\n- Practice Interview Questions",
        )

        # Connect Title to Groups
        # (Optional, but adds visual flow)
        # self.canvas_manager.add_edge(title_id, "bottom", jobs_group_id, "top")
        # self.canvas_manager.add_edge(title_id, "bottom", network_group_id, "top")
        # self.canvas_manager.add_edge(title_id, "bottom", analysis_group_id, "top")

        # Save to Vault Root
        dashboard_path = self.vault_manager.vault_path / "Dashboard.canvas"
        self.canvas_manager.save_to_file(dashboard_path)

        logger.info(f"Dashboard generated at: {dashboard_path}")
        return dashboard_path
