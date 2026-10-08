import serial
import time

# 1. Setup the USB Connection
# Change 'COM4' to whatever port your ESP32 is plugged into
# Make sure 115200 matches the Serial.begin(115200) in your Arduino code
usb_port = 'COM4'
baud_rate = 115200

print(f"🔄 Attempting to connect to ESP32 on {usb_port}...")

try:
    # Open the serial port
    esp32 = serial.Serial(usb_port, baud_rate, timeout=1)
    print("✅ Direct USB Connection Established!")
    print("📡 Listening for live ECG data...")
    print("-" * 50)
    
except Exception as e:
    print(f"❌ CONNECTION ERROR: Could not open {usb_port}.")
    print("Did you forget to close the Arduino Serial Monitor? Is the board plugged in?")
    print(f"Details: {e}")
    exit()

# 2. The Real-Time Listener Loop
try:
    while True:
        # Check if there is data waiting in the USB cable
        if esp32.in_waiting > 0:
            # Read the line, decode it from bytes to string, and strip extra spaces
            try:
                raw_data = esp32.readline().decode('utf-8').strip()
                
                # Print it straight to your Antigravity terminal
                if raw_data:
                    print(f"⚡ Live Data: {raw_data}")
                    
                    # You can add your AI Agent logic right here!
                    # For example: if "BPM" in raw_data: trigger_ai(raw_data)
            except UnicodeDecodeError:
                pass
                
        time.sleep(0.01) # Tiny sleep to prevent your CPU from maxing out

except KeyboardInterrupt:
    print("\n🛑 Closing USB connection. System Offline.")
    esp32.close()
