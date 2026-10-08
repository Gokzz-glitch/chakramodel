import argparse
import yaml
import os
from dotenv import load_dotenv
from src.orchestrator import execute_pipeline

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="DataGenesis Shield Orchestrator")
    parser.add_argument('--config', type=str, default='config/pipeline.yaml', help='Path to pipeline YAML config')
    args = parser.parse_args()
    
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)
        
    env_key = os.environ.get("DATA_GENESIS_TEAM_KEY")
    if env_key:
        config['watermark']['payload'] = env_key
        
    execute_pipeline(config)

if __name__ == '__main__':
    main()
