from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Project-local .env (backend/.env, gitignored) wins over inherited shell env:
# this machine carries a global OPENAI_API_KEY for other projects, and HOVOR
# must use its own key, not silently bill a neighbor's.
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)


class Settings(BaseSettings):
    app_name: str = "HOVOR!"
    database_url: str = "sqlite:///./hovor.db"
    content_dir: Path = Path(__file__).resolve().parent.parent / "content" / "seed"

    # Session composition knobs (spec §5)
    retrieval_batch_size: int = 6      # Phase A: items near the forgetting boundary
    new_material_batch_size: int = 5   # Phase B: tightly constrained new language
    debrief_max_corrections: int = 2   # Phase D: never dump twelve corrections

    # XP anti-farming (spec §16.1): novelty multiplier per repeated success
    # on the same (item, mode) within a day: 1.0, 0.5, 0.25, then 0.
    xp_novelty_decay: list[float] = [1.0, 0.5, 0.25]

    model_config = {"env_prefix": "HOVOR_"}


settings = Settings()
