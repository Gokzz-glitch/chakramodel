import logging
import asyncio
import sys
import json
import time
import math
import random
import os
import struct
import binascii
from pathlib import Path
import serial # pyre-ignore[21]
import serial.tools.list_ports # pyre-ignore[21]
from typing import Callable, Optional, List, Any
from paho.mqtt import client as mqtt # pyre-ignore[21]
import numpy as np  # type: ignore
from scipy.signal import resample  # type: ignore
try:
    import bleak # pyre-ignore[21]
except ImportError:
    bleak = None
try:
    import wfdb  # type: ignore
except Exception:
    wfdb = None


logger = logging.getLogger(__name__)


def _crc16_ccitt(data: bytes, seed: int = 0xFFFF) -> int:
    crc = seed
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def _cobs_decode(data: bytes) -> bytes:
    if not data:
        return b""
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        code = data[i]
        if code == 0:
            raise ValueError("invalid COBS code 0")
        i += 1
        end = i + code - 1
        if end > n:
            raise ValueError("truncated COBS frame")
        out.extend(data[i:end])
        i = end
        if code != 0xFF and i < n:
            out.append(0)
    return bytes(out)

class DataIngestor:
    """
    Unified ingestion engine for PulseAI.
    Subscribes to multiple sources and emits a unified stream of ECG samples.
    """
    def __init__(self, on_data_callback: Callable[[float], None], on_status_callback: Optional[Callable[[bool], None]] = None):
        self.on_data = on_data_callback
        self.on_status = on_status_callback # True = leads on, False = leads off
        self.realtime_only = os.getenv("PULSEAI_REALTIME_ONLY", "1").strip().lower() not in ("0", "false", "no")
        default_source = os.getenv("PULSEAI_DEFAULT_SOURCE", "SERIAL").strip().upper() or "SERIAL"
        if self.realtime_only and default_source == "SIMULATION":
            default_source = "SERIAL"
        self.active_source = default_source
        
        # Sources Config
        self.mqtt_broker = "broker.hivemq.com"
        self.mqtt_topic = "pulseai/ecg/data"
        self.serial_port = "COM4"
        self.serial_baud = 115200
        self.serial_fallback_source = os.getenv("PULSEAI_SERIAL_FALLBACK_SOURCE", "NONE").strip().upper() or "NONE"
        self.mitbih_path = Path(
            os.getenv(
                "PULSEAI_MITBIH_PATH",
                str(Path(__file__).resolve().parents[1] / "mit-bih-arrhythmia-database-1.0.0"),
            )
        )
        
        # Socket Config (Wireless Stream)
        self.socket_remote_host = "192.168.1.10" # IP of the Friend's laptop (Server)
        self.socket_remote_port = 5555
        
        # State
        self.is_running = False
        self._tasks: List[asyncio.Task] = []
        self._mqtt_client: Optional[Any] = None
        self._serial_conn: Optional[serial.Serial] = None
        self.simulation_mode = "1"
        self._serial_missing_since: Optional[float] = None
        self._recorded_samples: list[float] = []
        self._recorded_index = 0
        self._recorded_loaded = False
        self._packet_error_count = 0

    def _decode_packetized_sample(self, line: str) -> Optional[float]:
        """Decode a binary packet in CB:<hex> format with COBS + CRC16.

        Payload layout after COBS decode: <float32_le><crc16_le>.
        """
        if not line.startswith("CB:"):
            return None

        hex_payload = line[3:].strip()
        if not hex_payload:
            self._packet_error_count += 1
            return None

        try:
            encoded = bytes.fromhex(hex_payload)
            decoded = _cobs_decode(encoded)
            if len(decoded) != 6:
                raise ValueError("unexpected payload length")
            data_part = decoded[:4]
            crc_recv = int.from_bytes(decoded[4:6], "little", signed=False)
            crc_calc = _crc16_ccitt(data_part)
            if crc_recv != crc_calc:
                raise ValueError("crc mismatch")
            return float(struct.unpack("<f", data_part)[0])
        except (ValueError, struct.error, binascii.Error):
            self._packet_error_count += 1
            return None


    def _update_status(self, leads_on: bool):
        cb = self.on_status
        if cb is not None:
            cb(leads_on)

    def set_source(self, source: str):
        """Set the active data source (SIMULATION, MQTT, SERIAL, BLUETOOTH, HTTP, RECORDED_REAL)."""
        normalized = source.upper()
        if normalized in ("REAL", "REALDATA", "RECORDED", "MITBIH"):
            normalized = "RECORDED_REAL"
        if self.realtime_only and normalized == "SIMULATION":
            logger.warning("⛔ Realtime-only policy is active. Blocking SIMULATION source; forcing SERIAL.")
            normalized = "SERIAL"
        logger.info(f"🔄 Switching data source to: {normalized}")
        self.active_source = normalized

    async def start(self):
        """Initialize all ingestion tasks."""
        self.is_running = True
        
        # Launch Simulation Task
        self._tasks.append(asyncio.create_task(self._run_simulation()))
        
        # Launch MQTT Task
        self._tasks.append(asyncio.create_task(self._run_mqtt()))
        
        # Launch Serial Task
        self._tasks.append(asyncio.create_task(self._run_serial()))
        
        # Launch Socket Task
        self._tasks.append(asyncio.create_task(self._run_socket()))

        # Launch recorded-real playback task
        self._tasks.append(asyncio.create_task(self._run_recorded_real()))

    async def stop(self):
        self.is_running = False
        for t in self._tasks:
            t.cancel()
        if self._mqtt_client is not None:
            try:
                self._mqtt_client.loop_stop()  # type: ignore
                self._mqtt_client.disconnect()  # type: ignore
            except Exception:
                pass
        conn = self._serial_conn
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    async def ingest_http(self, value: float):
        """Manual ingestion via HTTP POST."""
        if self.active_source == "HTTP" or self.active_source == "REMOTE":
            self.on_data(value)

    def _ensure_recorded_real_loaded(self) -> bool:
        if self._recorded_loaded:
            return len(self._recorded_samples) > 0

        self._recorded_loaded = True
        records_file = self.mitbih_path / "RECORDS"
        if wfdb is None:
            logger.error("wfdb is not installed; cannot load RECORDED_REAL source. Install with `pip install wfdb`.")
            return False
        if not records_file.exists():
            logger.error(f"Missing MIT-BIH RECORDS file at {records_file}")
            return False

        try:
            max_records = max(1, int(os.getenv("PULSEAI_REALDATA_RECORDS", "4")))
        except ValueError:
            max_records = 4
        try:
            max_seconds = max(30, int(os.getenv("PULSEAI_REALDATA_SECONDS", "120")))
        except ValueError:
            max_seconds = 120

        max_samples = 500 * max_seconds
        records = [r.strip() for r in records_file.read_text(encoding="utf-8", errors="ignore").splitlines() if r.strip()]
        selected = records[:max_records]
        stream: list[float] = []

        for rec in selected:
            if len(stream) >= max_samples:
                break
            try:
                rec_path = str(self.mitbih_path / rec)
                sig, fields = wfdb.rdsamp(rec_path, channels=[0])
                if sig is None or len(sig) == 0:
                    continue
                raw = np.asarray(sig[:, 0], dtype=np.float32)
                src_fs = float(fields.get("fs", 360.0))
                if int(round(src_fs)) != 500 and len(raw) > 8:
                    n_out = max(8, int(len(raw) * (500.0 / max(src_fs, 1.0))))
                    raw = resample(raw, n_out).astype(np.float32)
                stream.extend(float(v) for v in raw.tolist())
            except Exception as exc:
                logger.warning(f"Could not load MIT-BIH record {rec}: {exc}")

        if not stream:
            logger.error("RECORDED_REAL source has no usable samples from MIT-BIH.")
            return False

        self._recorded_samples = stream[:max_samples]
        self._recorded_index = 0
        logger.info(
            f"📚 Loaded RECORDED_REAL stream from MIT-BIH: records={len(selected)} samples={len(self._recorded_samples)}"
        )
        return True

    # --- Private Implementation ---

    async def _run_simulation(self):
        """Clinical ECG simulator capable of dynamic disease states."""
        sim_time = 0.0
        freq = 500.0
        dt = 1.0 / freq
        chunk_size = 50
        time_since_last_beat = 0.0
        current_rr = 0.8

        while self.is_running:
            if self.active_source == "SIMULATION":
                mode = self.simulation_mode
                if mode == "0":
                    self._update_status(False)
                else:
                    self._update_status(True)

                for _ in range(chunk_size):
                    v = 0.0
                    if mode == "0":
                        v = random.uniform(-0.02, 0.02)
                        time_since_last_beat += dt  # type: ignore
                    elif mode == "5":
                        v = 2.0 * math.sin(sim_time * 15.0) + 1.2 * math.cos(sim_time * 25.0) + random.uniform(-0.5, 0.5)  # type: ignore
                        time_since_last_beat += dt  # type: ignore
                    else:
                        if mode == "1": hr, target_rr = 75.0, 60.0 / 75.0
                        elif mode == "3": hr, target_rr = 150.0, 60.0 / 150.0
                        elif mode == "4": hr, target_rr = 180.0, 60.0 / 180.0
                        elif mode == "6": hr, target_rr = 40.0, 60.0 / 40.0
                        else: target_rr = current_rr  # AFib

                        if time_since_last_beat >= target_rr:
                            time_since_last_beat = 0.0
                            if mode == "2":
                                current_rr = random.uniform(0.4, 1.2)

                        qrs_pos = time_since_last_beat * freq
                        noise = random.uniform(-0.02, 0.02)

                        if mode == "4":
                            qrs = 2.5 * math.exp(-((qrs_pos - 50.0)**2.0) / 40.0)
                            t_wave = -0.8 * math.exp(-((qrs_pos - 100.0)**2.0) / 20.0)
                            v = qrs + t_wave + noise
                        else:
                            qrs = 1.5 * math.exp(-((qrs_pos - 100.0)**2.0) / 10.0)
                            t_wave = 0.35 * math.exp(-((qrs_pos - 200.0)**2.0) / 200.0)

                            if mode == "3":
                                f_wave = 0.3 * math.sin(sim_time * 80.0)
                                v = qrs + t_wave + f_wave + noise
                            elif mode == "2":
                                v = qrs + t_wave + 0.1 * math.sin(sim_time * 40.0) + noise
                            else:
                                p_wave = 0.15 * math.exp(-((qrs_pos - 50.0)**2.0) / 50.0)
                                v = p_wave + qrs + t_wave + noise

                    self.on_data(v)
                    sim_time += dt
                    
                    # Print live numerical feed on the same terminal line for the "hacker" visual!
                    if int(sim_time * freq) % 15 == 0:
                        sys.stdout.write(f"\r🫀 Live ECG Telemetry [Mode {mode}]: {v:+.5f} mV    ")
                        sys.stdout.flush()

                await asyncio.sleep(chunk_size / freq)
            else:
                await asyncio.sleep(1.0)

    async def _run_mqtt(self):
        """Bridge MQTT data to local stream."""
        def on_connect(client, userdata, flags, rc):
            client.subscribe(self.mqtt_topic)  # type: ignore
            logger.info(f"✅ Ingestor MQTT Connected: {self.mqtt_topic}")

        def on_message(client, userdata, msg):
            if self.active_source == "MQTT":
                try:
                    payload = msg.payload.decode().strip()
                    if payload == "LEADS_OFF":
                        self._update_status(False)
                    else:
                        self._update_status(True)
                        self.on_data(float(payload))
                except Exception:
                    pass

        try:
            client = mqtt.Client(client_id=f"PulseAI-Ingestor-{random.randint(0,1000)}")  # type: ignore
            client.on_connect = on_connect  # type: ignore
            client.on_message = on_message  # type: ignore
            client.connect_async(self.mqtt_broker, 1883)  # type: ignore
            client.loop_start()  # type: ignore
            self._mqtt_client = client
        except Exception as e:
            logger.error(f"MQTT Ingestion Error: {e}")

    async def _run_serial(self):
        """Read from direct USB connection."""
        count = 0
        while self.is_running:
            if self.active_source == "SERIAL":
                try:
                    if not self._serial_conn:
                        ports = [p.device for p in serial.tools.list_ports.comports()]
                        target_port = None
                        
                        # Try preferred port first
                        if self.serial_port in ports:
                            target_port = self.serial_port
                        elif ports:
                            target_port = ports[0]
                            
                        if not target_port:
                            if self._serial_missing_since is None:
                                self._serial_missing_since = time.time()
                            if (
                                self.realtime_only
                                and self.serial_fallback_source == "RECORDED_REAL"
                                and time.time() - self._serial_missing_since >= 2.0
                                and self.active_source == "SERIAL"
                            ):
                                logger.warning("⚠️ No serial port detected. Optional fallback enabled -> RECORDED_REAL.")
                                self.set_source("RECORDED_REAL")
                            await asyncio.sleep(2)
                            continue
                            
                        self._serial_conn = serial.Serial(target_port, self.serial_baud, timeout=0.1)
                        self._serial_missing_since = None
                        logger.info(f"🔌 Serial connected on {target_port}")

                    conn = self._serial_conn
                    if conn is not None and conn.in_waiting > 0:
                        line = conn.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            if line == "LEADS_OFF":
                                self._update_status(False)
                            else:
                                packet_val = self._decode_packetized_sample(line)
                                try:
                                    val = packet_val if packet_val is not None else float(line)
                                    self._update_status(True)
                                    self.on_data(val)
                                    count += 1
                                    if count % 15 == 0:
                                        sys.stdout.write(f"\r🔌 [HW SENSOR LIVE] Telemetry: {val:+.5f} mV   ")
                                        sys.stdout.flush()
                                except ValueError:
                                    pass
                except Exception as e:
                    logger.warning(f"Serial Ingestion Error: {e}")
                    self._serial_conn = None
                    if self._serial_missing_since is None:
                        self._serial_missing_since = time.time()
            await asyncio.sleep(0.01)

    async def _run_recorded_real(self):
        """Replay recorded real ECG from MIT-BIH when hardware serial is unavailable."""
        count = 0
        chunk_size = 50
        fs = 500.0
        while self.is_running:
            if self.active_source == "RECORDED_REAL":
                if not self._ensure_recorded_real_loaded():
                    await asyncio.sleep(2.0)
                    continue

                self._update_status(True)
                for _ in range(chunk_size):
                    if not self._recorded_samples:
                        break
                    val = self._recorded_samples[self._recorded_index]
                    self._recorded_index = (self._recorded_index + 1) % len(self._recorded_samples)
                    self.on_data(val)
                    count += 1
                    if count % 200 == 0:
                        sys.stdout.write(f"\r📚 [RECORDED REAL] MIT-BIH Telemetry: {val:+.5f} mV   ")
                        sys.stdout.flush()

                await asyncio.sleep(chunk_size / fs)
            else:
                await asyncio.sleep(1.0)

    async def _run_socket(self):
        """Connect to a remote data stream (Wireless Bridge)."""
        while self.is_running:
            if self.active_source == "SOCKET" or self.active_source == "WIRELESS":
                try:
                    logger.info(f"📡 Attempting connection to Wireless Bridge at {self.socket_remote_host}:{self.socket_remote_port}...")
                    reader, writer = await asyncio.open_connection(
                        self.socket_remote_host, self.socket_remote_port
                    )
                    
                    logger.info(f"🤝 Wireless connection established with {self.socket_remote_host}")
                    
                    while self.is_running and self.active_source in ["SOCKET", "WIRELESS"]:
                        data = await reader.readline()
                        if not data:
                            break
                        line = data.decode().strip()
                        if line:
                            if line == "LEADS_OFF":
                                self._update_status(False)
                            else:
                                try:
                                    val = float(line)
                                    self._update_status(True)
                                    self.on_data(val)
                                except ValueError:
                                    pass
                    
                    writer.close()
                    await writer.wait_closed()
                    logger.info("👋 Wireless connection closed.")
                    
                except Exception as e:
                    logger.warning(f"Socket Connection Error: {e}. Retrying in 5s...")
                    await asyncio.sleep(5)
            else:
                await asyncio.sleep(1.0)

    async def _run_bluetooth(self):
        """Placeholder for BLE ingestion (requires bleak)."""
        # FUTURE: Implement scanning and characteristic reading
        pass
