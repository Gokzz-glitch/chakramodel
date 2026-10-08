import serial  # type: ignore
import socket
import time
import sys
import serial.tools.list_ports  # type: ignore

# --- CONFIGURATION ---
PORT = 5555           # The socket port to listen on
BAUD_RATE = 115200    # The baud rate of your Arduino/ESP32
# ---------------------

def start_bridge():
    # 1. Detect Serial Port
    ports = [p.device for p in serial.tools.list_ports.comports()]
    if not ports:
        print("❌ No Serial ports found! Connect your Arduino/ESP32 first.")
        sys.exit(1)
    
    serial_port = ports[0]
    print(f"🔌 Using Serial Port: {serial_port} at {BAUD_RATE} baud")
    
    try:
        ser = serial.Serial(serial_port, BAUD_RATE, timeout=1)
    except Exception as e:
        print(f"❌ Could not open serial port: {e}")
        sys.exit(1)

    # 2. Start Socket Server
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Get local IP
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    try:
        server_socket.bind(('0.0.0.0', PORT))
        server_socket.listen(1)
        print(f"📡 Wireless Bridge Active!")
        print(f"👉 Tell your friend your IP: {local_ip}")
        print(f"👉 PulseAI should connect to {local_ip}:{PORT}")
    except Exception as e:
        print(f"❌ Could not start socket server: {e}")
        sys.exit(1)

    print("-" * 50)
    
    try:
        while True:
            print("⏳ Waiting for PulseAI to connect...")
            client_socket, addr = server_socket.accept()
            print(f"🤝 Connection established with {addr}")
            
            try:
                while True:
                    if ser.in_waiting > 0:
                        line = ser.readline()
                        # Forward the exact line to the client
                        client_socket.sendall(line)
                    else:
                        time.sleep(0.001) # Low latency
            except (ConnectionResetError, BrokenPipeError):
                print(f"👋 PulseAI disconnected ({addr}).")
            except Exception as e:
                print(f"⚠️  Client Error: {e}")
            finally:
                client_socket.close()
                
    except KeyboardInterrupt:
        print("\n🛑 Shutting down bridge.")
    finally:
        ser.close()
        server_socket.close()

if __name__ == "__main__":
    start_bridge()
