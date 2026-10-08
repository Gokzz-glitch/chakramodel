import pytest
import os
import yaml
from pathlib import Path
from pydantic import ValidationError

def test_config_loading_defaults(tmp_path):
    from chakra.config import ChakraConfig
    
    # Normally loads from configs/default.yaml
    # We will let the module use the real configs/default.yaml in the project for this test
    config = ChakraConfig.load_config()
    
    # Assert mandatory top level keys exist
    assert hasattr(config, "model")
    assert hasattr(config, "tracking")
    assert hasattr(config, "persistence")
    assert hasattr(config, "conformal")
    assert hasattr(config, "render")

def test_config_overrides(tmp_path):
    from chakra.config import ChakraConfig
    
    # Create a temporary yaml override
    override_yaml = tmp_path / "jetson_agx_fp16.yaml"
    with open(override_yaml, "w") as f:
        yaml.dump({"model": {"backbone": "yolov11m", "conf_threshold": 0.5}}, f)
        
    config = ChakraConfig.load_config(config_path=override_yaml)
    assert config.model.backbone == "yolov11m"
    assert config.model.conf_threshold == 0.5
    
    # CLI override simulation
    config_cli = ChakraConfig.load_config(config_path=override_yaml, cli_args=["--model.conf_threshold", "0.30"])
    assert config_cli.model.conf_threshold == 0.30
