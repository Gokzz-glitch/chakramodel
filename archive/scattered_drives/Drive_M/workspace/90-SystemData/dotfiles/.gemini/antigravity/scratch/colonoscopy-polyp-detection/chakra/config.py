from typing import Optional, List
import yaml
import sys
from pathlib import Path
from pydantic import BaseModel
from pydantic_settings import BaseSettings

class ModelConfig(BaseModel):
    backbone: str = "yolov11m"
    conf_threshold: float = 0.25

class TrackingConfig(BaseModel):
    algorithm: str = "botsort"
    conf_high: float = 0.60
    conf_low: float = 0.15
    gmc_method: str = "ecc"

class PersistenceConfig(BaseModel):
    min_hits: int = 3
    max_age: int = 8
    alpha_ema: float = 0.7

class ConformalConfig(BaseModel):
    enabled: bool = True

class RenderConfig(BaseModel):
    show_labels: bool = True

class ChakraConfig(BaseSettings):
    model: ModelConfig = ModelConfig()
    tracking: TrackingConfig = TrackingConfig()
    persistence: PersistenceConfig = PersistenceConfig()
    conformal: ConformalConfig = ConformalConfig()
    render: RenderConfig = RenderConfig()

    @classmethod
    def load_config(cls, config_path: str = "configs/default.yaml", cli_args: Optional[List[str]] = None) -> "ChakraConfig":
        config_data = {}
        path = Path(config_path)
        if path.exists():
            with open(path, "r") as f:
                config_data = yaml.safe_load(f) or {}
                
        # Parse CLI overrides (simple implementation for test cases: --key.subkey value)
        if cli_args is None:
            cli_args = sys.argv[1:]
            
        i = 0
        while i < len(cli_args):
            arg = cli_args[i]
            if arg.startswith("--"):
                key_path = arg[2:].split(".")
                if i + 1 < len(cli_args) and not cli_args[i+1].startswith("--"):
                    value = cli_args[i+1]
                    i += 1
                    
                    # Convert types naively for simplicity
                    try:
                        value = float(value) if "." in value else int(value)
                    except ValueError:
                        pass
                    
                    # Traverse and set
                    current = config_data
                    for k in key_path[:-1]:
                        current = current.setdefault(k, {})
                    current[key_path[-1]] = value
            i += 1
            
        return cls(**config_data)
