import pathlib
from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from src.utils.exceptions import ScraperError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BrowserManager:
    """Manages Playwright browser setup, context, and persistent sessions."""

    def __init__(self, headless: bool = False, session_path: Optional[pathlib.Path] = None):
        """
        Initialize the BrowserManager.

        Args:
            headless (bool): Run browser in headless mode. Defaults to False for visibility.
            session_path (pathlib.Path): Path to store/load browser cookies/state.
        """
        self.headless = headless
        self.session_path = session_path
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def start(self):
        """Starts the browser instance."""
        try:
            self.playwright = sync_playwright().start()

            # Using chromium
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-setuid-sandbox"],  # Docker compatibility
            )

            # Load state if exists, otherwise create new context
            if self.session_path and self.session_path.exists():
                logger.info(f"Loading session from {self.session_path}")
                self.context = self.browser.new_context(storage_state=str(self.session_path))
            else:
                self.context = self.browser.new_context()

            self.page = self.context.new_page()

        except Exception as e:
            raise ScraperError(f"Failed to start browser: {e}") from e

    def stop(self):
        """Stops the browser and saves state if configured."""
        try:
            if self.session_path and self.context:
                # Create parent dir if needed
                self.session_path.parent.mkdir(parents=True, exist_ok=True)
                self.context.storage_state(path=str(self.session_path))
                logger.info(f"Session saved to {self.session_path}")

            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.error(f"Error stopping browser: {e}")

    def goto(self, url: str):
        """Navigates to a URL."""
        if not self.page:
            raise ScraperError("Browser not started. Call start() first.")
        try:
            self.page.goto(url, wait_until="domcontentloaded")
        except Exception as e:
            raise ScraperError(f"Failed to navigate to {url}: {e}") from e

    def login_manual(self, login_url: str = "https://www.linkedin.com/login", success_selector: str = ".global-nav"):
        """
        Pauses execution to allow manual login, then saves state.

        Args:
            login_url: URL to open for login.
            success_selector: CSS selector that indicates successful login (e.g., nav bar).
        """
        if not self.page:
            self.start()

        if self.headless:
            logger.warning("Manual login requires a visible browser. Re-initialize with headless=False.")
            # We can't easily switch mode without restarting.
            # For now, just warn.

        logger.info("Initiating manual login...")
        self.goto(login_url)

        try:
            # Check if likely already logged in (cookies worked)
            if self.page.locator(success_selector).count() > 0:
                logger.info("Already logged in!")
                return

            logger.info("Please log in to LinkedIn in the browser window.")
            logger.info("The script will wait until it detects you are logged in...")

            # Wait for user to log in
            self.page.wait_for_selector(success_selector, timeout=300000)  # 5 minutes
            logger.info("Login detected!")

            # State will be saved on stop() or we can force it now
            if self.session_path:
                self.context.storage_state(path=str(self.session_path))
                logger.info("Session saved!")

        except Exception as e:
            raise ScraperError(f"Login timeout or error: {e}") from e

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
