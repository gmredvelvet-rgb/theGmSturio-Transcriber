"""Campaign management — each campaign has its own folder, config, and transcriptions."""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

CAMPAIGNS_ROOT_DEFAULT = Path("campaigns")
CAMPAIGN_CONFIG_FILE = "campaign.json"


@dataclass
class Campaign:
    """An RPG campaign with persistent configuration."""

    name: str
    path: Path
    discord_webhook: str = ""
    sessions: list[str] = field(default_factory=list)

    @property
    def config_path(self) -> Path:
        return self.path / CAMPAIGN_CONFIG_FILE

    @property
    def transcripts_dir(self) -> Path:
        d = self.path / "transcripts"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def summaries_dir(self) -> Path:
        d = self.path / "summaries"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(self) -> None:
        """Save the campaign configuration to disk."""
        self.path.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self.name,
            "discord_webhook": self.discord_webhook,
            "sessions": self.sessions,
        }
        self.config_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Campaign saved: %s", self.name)

    @classmethod
    def load(cls, path: Path) -> "Campaign":
        """Load a campaign from its directory."""
        config_path = path / CAMPAIGN_CONFIG_FILE
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration not found in: {path}")

        data = json.loads(config_path.read_text(encoding="utf-8"))
        return cls(
            name=data.get("name", path.name),
            path=path,
            discord_webhook=data.get("discord_webhook", ""),
            sessions=data.get("sessions", []),
        )


class CampaignManager:
    """Manages all locally stored campaigns."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or CAMPAIGNS_ROOT_DEFAULT).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def list_campaigns(self) -> list[Campaign]:
        """List all existing campaigns."""
        campaigns: list[Campaign] = []
        if not self.root.exists():
            return campaigns

        for d in sorted(self.root.iterdir()):
            config = d / CAMPAIGN_CONFIG_FILE
            if d.is_dir() and config.exists():
                try:
                    campaigns.append(Campaign.load(d))
                except Exception as e:
                    logger.warning("Error loading campaign %s: %s", d.name, e)
        return campaigns

    def create_campaign(self, name: str) -> Campaign:
        """Create a new campaign."""
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip()
        folder_name = safe_name.replace(" ", "_")
        path = self.root / folder_name

        if path.exists():
            raise ValueError(f"A campaign with that name already exists: {name}")

        campaign = Campaign(name=name, path=path)
        campaign.save()
        logger.info("Campaign created: %s at %s", name, path)
        return campaign

    def delete_campaign(self, campaign: Campaign) -> None:
        """Delete a campaign and all its files."""
        import shutil

        if campaign.path.exists():
            shutil.rmtree(campaign.path)
            logger.info("Campaign deleted: %s", campaign.name)

    def get_campaign(self, name: str) -> Campaign | None:
        """Find a campaign by name."""
        for c in self.list_campaigns():
            if c.name == name:
                return c
        return None
