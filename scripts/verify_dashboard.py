from pathlib import Path

from src.generator.dashboard_generator import DashboardGenerator
from src.utils.logger import setup_logging


def verify_dashboard():
    setup_logging()

    # 1. Simulate Configuration
    test_vault_path = Path("output/verification_vault")
    config = {
        "obsidian": {
            "vault_path": str(test_vault_path),
            "folders": {"jobs": "Jobs", "companies": "Companies", "people": "People", "analysis": "Analysis"},
        }
    }

    print("--- Verifying DashboardGenerator ---")
    print(f"Target Vault Path: {test_vault_path.absolute()}")

    # 2. Ensure Vault Exists
    test_vault_path.mkdir(parents=True, exist_ok=True)

    # 3. Generate Dashboard
    generator = DashboardGenerator(config)
    dashboard_path = generator.generate()

    # 4. Verify
    if dashboard_path.exists():
        print(f"Dashboard generated successfully at: {dashboard_path}")
        print("File size:", dashboard_path.stat().st_size, "bytes")
    else:
        print("Failed to generate dashboard.")


if __name__ == "__main__":
    verify_dashboard()
