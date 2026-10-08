from src.agent1_gan.gan import run_gan_training, generate_synthetic_data
from src.agent2_cnn.cnn import run_cnn_training
from src.agent3_watermark.watermark import run_watermark_batch

def execute_pipeline(config):
    print("="*50)
    print("Starting DataGenesis Shield Pipeline")
    print("="*50)
    
    if config['pipeline']['run_gan']:
        run_gan_training(config)
        generate_synthetic_data(config)
        
    if config['pipeline']['run_watermark_synthetic']:
        run_watermark_batch(config, 
                            source_dir="output/synthetic_data", 
                            output_dir="output/watermarked_data")
                            
    if config['pipeline']['run_cnn']:
        run_cnn_training(config)
        
    print("="*50)
    print("Pipeline execution completed successfully.")
    print("="*50)
