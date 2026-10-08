import argparse
import time
import os
from dotenv import load_dotenv
from src.agent3_watermark.watermark import extract_watermark_dummy, get_payload_from_key

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="DataGenesis Shield - Ownership Verifier")
    parser.add_argument('--dir', type=str, required=True, help='Path to directory containing images')
    parser.add_argument('--key', type=str, required=False, help='Plaintext team key to verify')
    args = parser.parse_args()
    
    key = args.key or os.environ.get("DATA_GENESIS_TEAM_KEY")
    if not key:
        print("Error: Must provide --key or set DATA_GENESIS_TEAM_KEY environment variable.")
        return
    
    # Layer 2 harness requirement
    nonce = os.environ.get("VERIFY_NONCE")
    if nonce:
        print(f"VERIFY_NONCE: {nonce}")
        
    start_time = time.time()
    
    if not os.path.exists(args.dir):
        print(f"Directory not found: {args.dir}")
        return

    files = [f for f in os.listdir(args.dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    print(f"Total images found: {len(files)}")
    
    expected_payload = get_payload_from_key(key)
    
    for f in files:
        img_path = os.path.join(args.dir, f)
        
        try:
            extracted_payload = extract_watermark_dummy(img_path)
            if extracted_payload == expected_payload:
                verdict = "VERIFIED"
            else:
                verdict = "TAMPERED or UNKNOWN"
        except Exception:
            verdict = "TAMPERED or UNKNOWN"
            
        print(f"{f} - VERDICT: {verdict}")
        
        with open("verification_audit.log", "a") as log:
            log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Image: {img_path} - Verdict: {verdict}\n")
            
if __name__ == '__main__':
    main()
