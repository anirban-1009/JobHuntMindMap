import pathlib
import pytest
import yaml

from src.generator.base_generator import (
    BaseGenerator,
    COMPANY_BASE_COLUMNS,
)


@pytest.fixture
def mock_vault_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    return vault


@pytest.fixture
def base_config(mock_vault_dir: pathlib.Path) -> dict:
    return {
        "obsidian": {
            "vault_path": str(mock_vault_dir),
            "folders": {
                "jobs": "Jobs",
                "companies": "Companies",
                "people": "People",
                "analysis": "Analysis",
            },
        }
    }


def test_create_default_base(base_config: dict, mock_vault_dir: pathlib.Path):
    """Test generating Dashboard.base from scratch when none exists."""
    generator = BaseGenerator(base_config)
    base_file = generator.generate_or_update()

    assert base_file.exists()
    content = yaml.safe_load(base_file.read_text(encoding="utf-8"))
    assert "views" in content
    views = content["views"]
    view_names = [v["name"] for v in views]

    assert "Jobs" in view_names
    assert "Companies" in view_names
    assert "Warm Outreach" in view_names
    assert "Direct Apply" in view_names
    assert "People" in view_names

    companies_view = next(v for v in views if v["name"] == "Companies")
    assert companies_view["order"] == COMPANY_BASE_COLUMNS
    assert companies_view["sort"] == [{"property": "score", "direction": "DESC"}]


def test_update_existing_base(base_config: dict, mock_vault_dir: pathlib.Path):
    """Test updating an existing Dashboard.base, preserving existing views while augmenting Companies."""
    existing_content = """
views:
  - type: table
    name: Jobs
    filters:
      and:
        - score >= 80
    order:
      - job_id
      - file.name
      - score
  - type: table
    name: Companies
    filters:
      and:
        - type == "company"
    order:
      - file.name
      - industry
      - location
      - custom_column
  - type: table
    name: People
    filters:
      and:
        - type == "person"
    order:
      - file.name
      - title
"""
    base_path = mock_vault_dir / "Dashboard.base"
    base_path.write_text(existing_content, encoding="utf-8")

    generator = BaseGenerator(base_config)
    generator.generate_or_update()

    updated = yaml.safe_load(base_path.read_text(encoding="utf-8"))
    views = updated["views"]
    view_names = [v["name"] for v in views]

    # Verify existing views are preserved
    assert "Jobs" in view_names
    assert "People" in view_names
    assert "Companies" in view_names
    assert "Warm Outreach" in view_names
    assert "Direct Apply" in view_names

    companies_view = next(v for v in views if v["name"] == "Companies")
    # All required columns are present
    for col in COMPANY_BASE_COLUMNS:
        assert col in companies_view["order"]
    # User's custom column was preserved
    assert "custom_column" in companies_view["order"]
    # Sorted by score DESC
    assert companies_view["sort"] == [{"property": "score", "direction": "DESC"}]
