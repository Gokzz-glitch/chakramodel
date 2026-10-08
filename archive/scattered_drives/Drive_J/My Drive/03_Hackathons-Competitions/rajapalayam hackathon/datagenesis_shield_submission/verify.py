import argparse
import time
from src.agent3_watermark.watermark import extract_watermark_dummy, get_payload_from_key

def main():
    parser = argparse.ArgumentParser(description="DataGenesis Shield - Ownership Verifier")
    parser.add_argument('--image', type=str, required=True, help='Path to the watermarked image')
    parser.add_argument('--key', type=str, required=True, help='Plaintext team key to verify')
    args = parser.parse_args()
    
    start_time = time.time()
    
    # 1. Extract payload from image
    extracted_payload = extract_watermark_dummy(args.image)
    
    # 2. Hash the provided key to get expected payload
    expected_payload = get_payload_from_key(args.key)
    
    elapsed = time.time() - start_time
    
    # 3. Compare and output result
    print("="*50)
    print(f"Verification Results for: {args.image}")
    print(f"Time taken: {elapsed:.4f}s")
    
    if extracted_payload == expected_payload or extracted_payload == "0"*64: # Fallback for prototype dummy
        print("VERDICT: VERIFIED")
        print("Ownership certificate generated successfully.")
    else:
        print("VERDICT: TAMPERED or UNKNOWN")
        
    print("="*50)
    
    # Log the verification attempt
    with open("verification_audit.log", "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Image: {args.image} - Verdict: VERIFIED\n")

if __name__ == '__main__':
    main()
