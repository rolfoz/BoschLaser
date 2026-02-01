import asyncio
import struct
import sys
import json
import os
from bleak import BleakClient, BleakScanner
from pynput.keyboard import Controller

CONFIG_FILE = "config.json"
CHARACTERISTIC_UUID = "02a6c0d1-0451-4000-b000-fb3210111989"
AUTO_SYNC_CMD = bytearray([0xC0, 0x55, 0x02, 0x01, 0x00, 0x1A])
DATA_PREFIX = bytearray([0xC0, 0x55, 0x10, 0x06])

keyboard = Controller()

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            if data.get("mac_address"):
                return data["mac_address"]
    return None

def save_config(mac):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"mac_address": mac}, f)

async def pick_device():
    print("Scanning for Bluetooth devices (looking for GLM)...")
    devices = await BleakScanner.discover(timeout=5.0)
    
    # Filter for Bosch-looking names or show all
    glm_devices = [d for d in devices if d.name and "GLM" in d.name.upper()]
    target_list = glm_devices if glm_devices else devices

    if not target_list:
        print("No Bluetooth devices found. Is Bluetooth turned on?")
        sys.exit(1)

    print("\nAvailable Devices:")
    for i, dev in enumerate(target_list):
        print(f"[{i}] {dev.name} - {dev.address}")

    while True:
        try:
            choice = int(input("\nSelect the number of your device: "))
            if 0 <= choice < len(target_list):
                selected_mac = target_list[choice].address
                save_config(selected_mac)
                return selected_mac
        except ValueError:
            pass
        print("Invalid selection.")

def notification_handler(sender, data):
    if len(data) > 11 and data[:4] == DATA_PREFIX:
        try:
            meters = struct.unpack("<f", data[7:11])[0]
            text = f"{meters:.3f}"
            print(f"--> Measurement: {text} m")
            keyboard.type(text)
            keyboard.press('\n')
            keyboard.release('\n')
        except Exception as e:
            print(f"Parsing error: {e}")
    else:
        sys.stdout.write(f"\rStatus: {data.hex().upper()}   ")
        sys.stdout.flush()

async def main():
    mac_address = load_config()
    
    if not mac_address:
        mac_address = await pick_device()

    print(f"\nTargeting: {mac_address}")
    
    try:
        async with BleakClient(mac_address) as client:
            print(f"Connected to {mac_address}")
            await client.start_notify(CHARACTERISTIC_UUID, notification_handler)
            await client.write_gatt_char(CHARACTERISTIC_UUID, AUTO_SYNC_CMD, response=True)
            
            print("\n--- READY ---")
            print("Press the measure button on the laser. Ctrl+C to exit.")
            while True:
                await asyncio.sleep(1)
    except Exception as e:
        print(f"\nConnection Error: {e}")
        print("Tip: If the address changed, delete config.json and run again.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
