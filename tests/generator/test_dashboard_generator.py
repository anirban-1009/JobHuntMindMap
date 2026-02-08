import pathlib
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from src.generator.dashboard_generator import DashboardGenerator


@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """Provides a mock configuration for the DashboardGenerator."""
    return {"vault": {"path": "data/vault"}, "user": {"name": "Test User"}}


class TestDashboardGenerator:
    """Test suite for the DashboardGenerator class."""

    @patch("src.generator.dashboard_generator.VaultManager")
    @patch("src.generator.dashboard_generator.CanvasManager")
    def test_dashboard_generation_flow(
        self, mock_canvas_class: MagicMock, mock_vault_class: MagicMock, mock_config: Dict[str, Any]
    ) -> None:
        """Verify the full dashboard generation process, including node creation and saving."""
        # Setup mocks
        mock_vault_manager = mock_vault_class.return_value
        mock_vault_manager.vault_path = pathlib.Path("/tmp/mock_vault")

        mock_canvas_manager = mock_canvas_class.return_value

        # Instantiate and run
        generator = DashboardGenerator(mock_config)
        result_path = generator.generate()

        # Assertions
        assert result_path == pathlib.Path("/tmp/mock_vault/Dashboard.canvas")

        # Check that nodes were added (at least some of them)
        assert mock_canvas_manager.add_node.call_count >= 6

        # Verify save was called with the correct path
        mock_canvas_manager.save_to_file.assert_called_once_with(result_path)

    @patch("src.generator.dashboard_generator.VaultManager")
    @patch("src.generator.dashboard_generator.CanvasManager")
    def test_dashboard_init(
        self, mock_canvas_class: MagicMock, mock_vault_class: MagicMock, mock_config: Dict[str, Any]
    ) -> None:
        """Verify correct initialization of the DashboardGenerator."""
        generator = DashboardGenerator(mock_config)
        assert generator.config == mock_config
        mock_vault_class.assert_called_with(mock_config)
        mock_canvas_class.assert_called_once()
