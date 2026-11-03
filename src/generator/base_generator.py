from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from src.generator.vault_manager import VaultManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class IndentDumper(yaml.SafeDumper):
    """Custom YAML Dumper that formats list items with 2-space indentation."""

    def increase_indent(self, flow: bool = False, indentless: bool = False):
        return super().increase_indent(flow, False)


COMPANY_BASE_COLUMNS = [
    "file.name",
    "score",
    "action_cluster",
    "domain_cluster",
    "target_tier",
    "job_count",
    "connection_count",
    "status",
    "industry",
    "location",
    "website",
]

WARM_OUTREACH_COLUMNS = [
    "file.name",
    "score",
    "domain_cluster",
    "target_tier",
    "job_count",
    "connection_count",
    "status",
]

DIRECT_APPLY_COLUMNS = [
    "file.name",
    "score",
    "domain_cluster",
    "target_tier",
    "job_count",
    "connection_count",
    "status",
]


class BaseGenerator:
    """Manages generation and synchronization of Obsidian Base (.base) files."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.vault_manager = VaultManager(config)

    @property
    def base_file_path(self) -> Path:
        """Returns the absolute path to Dashboard.base in the vault root."""
        return self.vault_manager.vault_path / "Dashboard.base"

    def generate_or_update(self, db: Optional[Any] = None) -> Path:
        """Generates or updates Dashboard.base with company views, order, and sorting."""
        logger.info("Synchronizing Obsidian Dashboard.base...")
        base_path = self.base_file_path

        existing_data: Optional[Dict[str, Any]] = None
        if base_path.exists():
            try:
                raw = base_path.read_text(encoding="utf-8")
                loaded = yaml.safe_load(raw)
                if isinstance(loaded, dict) and "views" in loaded:
                    existing_data = loaded
            except Exception as e:
                logger.warning(f"Could not parse existing Dashboard.base ({e}). Regenerating.")

        if existing_data:
            updated_data = self._update_existing_views(existing_data)
        else:
            updated_data = self._create_default_base()

        # Write formatted YAML
        try:
            content = yaml.dump(
                updated_data,
                Dumper=IndentDumper,
                sort_keys=False,
                default_flow_style=False,
                allow_unicode=True,
            )
            base_path.parent.mkdir(parents=True, exist_ok=True)
            base_path.write_text(content, encoding="utf-8")
            logger.info(f"Updated Dashboard.base at: {base_path}")
        except Exception as e:
            logger.error(f"Failed to write Dashboard.base: {e}")

        return base_path

    def _create_default_base(self) -> Dict[str, Any]:
        """Builds a complete default Dashboard.base structure."""
        return {
            "views": [
                {
                    "type": "table",
                    "name": "Jobs",
                    "filters": {"and": ["score >= 80"]},
                    "order": [
                        "job_id",
                        "file.name",
                        "applied",
                        "score",
                        "applied_at",
                        "title",
                        "company",
                        "link",
                        "poc_link",
                        "status",
                        "posted_date",
                        "location",
                    ],
                    "sort": [
                        {"property": "score", "direction": "DESC"},
                        {"property": "posted_date", "direction": "DESC"},
                    ],
                },
                self._build_companies_view(),
                self._build_cluster_view("Warm Outreach", WARM_OUTREACH_COLUMNS),
                self._build_cluster_view("Direct Apply", DIRECT_APPLY_COLUMNS),
                {
                    "type": "table",
                    "name": "People",
                    "filters": {"and": ['type == "person"']},
                    "order": [
                        "file.name",
                        "title",
                        "company",
                        "connected_on",
                        "last_contacted",
                    ],
                },
            ]
        }

    def _update_existing_views(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Merges company evaluation columns and action cluster views into existing base."""
        views = data.get("views", [])
        if not isinstance(views, list):
            views = []

        view_names = {v.get("name") for v in views if isinstance(v, dict)}

        # 1. Update or add 'Companies' view
        companies_view = None
        for v in views:
            if isinstance(v, dict) and v.get("name") == "Companies":
                companies_view = v
                break

        if companies_view:
            companies_view["order"] = self._merge_order(companies_view.get("order", []), COMPANY_BASE_COLUMNS)
            if "sort" not in companies_view or not companies_view["sort"]:
                companies_view["sort"] = [{"property": "score", "direction": "DESC"}]
        else:
            views.append(self._build_companies_view())

        # 2. Ensure 'Warm Outreach' view exists
        if "Warm Outreach" not in view_names and "Companies: Warm Outreach" not in view_names:
            views.append(self._build_cluster_view("Warm Outreach", WARM_OUTREACH_COLUMNS))

        # 3. Ensure 'Direct Apply' view exists
        if "Direct Apply" not in view_names and "Companies: Direct Apply" not in view_names:
            views.append(self._build_cluster_view("Direct Apply", DIRECT_APPLY_COLUMNS))

        return {"views": views}

    def _build_companies_view(self) -> Dict[str, Any]:
        """Builds the primary Companies table view."""
        return {
            "type": "table",
            "name": "Companies",
            "filters": {"and": ['type == "company"']},
            "order": list(COMPANY_BASE_COLUMNS),
            "sort": [{"property": "score", "direction": "DESC"}],
        }

    def _build_cluster_view(self, cluster_name: str, columns: List[str]) -> Dict[str, Any]:
        """Builds a dedicated cluster table view (e.g. Warm Outreach)."""
        return {
            "type": "table",
            "name": cluster_name,
            "filters": {
                "and": [
                    'type == "company"',
                    f'action_cluster == "{cluster_name}"',
                ]
            },
            "order": list(columns),
            "sort": [{"property": "score", "direction": "DESC"}],
        }

    def _merge_order(self, existing_order: List[str], required_columns: List[str]) -> List[str]:
        """Combines existing column order with required columns, avoiding duplicates."""
        merged = []
        for col in required_columns:
            merged.append(col)

        # Append any custom columns the user had in their base that aren't in required
        for col in existing_order:
            if col not in merged:
                merged.append(col)

        return merged
