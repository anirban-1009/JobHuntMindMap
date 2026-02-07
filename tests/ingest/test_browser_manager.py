from unittest.mock import MagicMock, patch

import pytest

from src.ingest.browser_manager import BrowserManager
from src.utils.exceptions import ScraperError


class TestBrowserManager:
    @patch("src.ingest.browser_manager.sync_playwright")
    def test_start_creates_browser_context(self, mock_playwright_sync):
        """Test that start() initializes playwright, browser, context, and page."""
        # Setup mocks
        mock_playwright_instance = MagicMock()
        mock_playwright_sync.return_value.start.return_value = mock_playwright_instance

        mock_browser = MagicMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser

        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context

        # Test
        manager = BrowserManager(headless=True)
        manager.start()

        # Verify
        mock_playwright_sync.return_value.start.assert_called_once()
        mock_playwright_instance.chromium.launch.assert_called_with(
            headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        mock_browser.new_context.assert_called_once()
        mock_context.new_page.assert_called_once()
        assert manager.page is not None

    @patch("src.ingest.browser_manager.sync_playwright")
    def test_start_loads_session(self, mock_playwright_sync, tmp_path):
        """Test that start() loads storage state if session path exists."""
        # Setup mocks
        mock_playwright_instance = MagicMock()
        mock_playwright_sync.return_value.start.return_value = mock_playwright_instance
        mock_browser = MagicMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser

        # Create a dummy session file
        session_file = tmp_path / "session.json"
        session_file.touch()

        manager = BrowserManager(session_path=session_file)
        manager.start()

        mock_browser.new_context.assert_called_with(storage_state=str(session_file))

    @patch("src.ingest.browser_manager.sync_playwright")
    def test_stop_saves_session(self, mock_playwright_sync, tmp_path):
        """Test that stop() saves storage state."""
        # Setup mocks
        mock_playwright_instance = MagicMock()
        mock_playwright_sync.return_value.start.return_value = mock_playwright_instance
        mock_browser = MagicMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context

        session_file = tmp_path / "session.json"

        manager = BrowserManager(session_path=session_file)
        manager.start()
        manager.stop()

        mock_context.storage_state.assert_called_with(path=str(session_file))
        mock_context.close.assert_called()
        mock_browser.close.assert_called()

    def test_goto_raises_if_not_started(self):
        """Test goto raises error if browser not started."""
        manager = BrowserManager()
        with pytest.raises(ScraperError, match="Browser not started"):
            manager.goto("http://example.com")
