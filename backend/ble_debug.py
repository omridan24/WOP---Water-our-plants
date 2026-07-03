#!/usr/bin/env python3
"""
BLE Debug Script — Run OUTSIDE Docker on the Raspberry Pi directly.

Usage:
    python3 ble_debug.py 00:0E:0B:1C:5F:C9

This will:
  1. Connect to the HM-11 module
  2. List all services and characteristics
  3. Subscribe to notifications on FFE1
  4. Print everything received for 30 seconds
  5. Send a PING command to test TX

This helps us figure out:
  - Is the Pi's Bluetooth able to receive data at all?
  - Is it a Docker/BlueZ issue or a hardware issue?
"""

import asyncio
import sys


async def main(address: str):
    # Import here so the script fails fast if bleak isn't installed
    try:
        from bleak import BleakClient
    except ImportError:
        print("ERROR: bleak not installed. Run: pip3 install bleak")
        return

    CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
    rx_count = 0

    def on_notify(sender, data: bytearray):
        nonlocal rx_count
        rx_count += 1
        text = data.decode("utf-8", errors="replace")
        print(f"  RX #{rx_count} from {sender}: {repr(text)}")

    def on_disconnect(client):
        print(f"\n❌ DISCONNECTED from {address}")

    print(f"🔌 Connecting to {address}...")
    async with BleakClient(
        address,
        disconnected_callback=on_disconnect,
        timeout=20.0,
    ) as client:
        print(f"✅ Connected! (MTU: {client.mtu_size})")

        # Step 1: List all services and characteristics
        print("\n📋 GATT Services:")
        for service in client.services:
            print(f"  Service: {service.uuid} — {service.description}")
            for char in service.characteristics:
                props = ", ".join(char.properties)
                print(f"    Char: {char.uuid} [{props}]")

        # Step 2: Check if FFE1 exists and supports notify
        char = None
        for service in client.services:
            for c in service.characteristics:
                if c.uuid == CHAR_UUID:
                    char = c
                    break

        if not char:
            print(f"\n❌ Characteristic {CHAR_UUID} NOT FOUND on this device!")
            print("   This means the UUID is wrong or the HM-11 firmware is different.")
            return

        props = char.properties
        print(f"\n🔍 FFE1 properties: {props}")

        if "notify" not in props:
            print("⚠️  FFE1 does NOT have 'notify' property!")
            print("   Trying 'read' instead...")

            # Try polling via read
            for i in range(10):
                try:
                    val = await client.read_gatt_char(CHAR_UUID)
                    print(f"  READ #{i}: {repr(val.decode('utf-8', errors='replace'))}")
                except Exception as e:
                    print(f"  READ #{i} error: {e}")
                await asyncio.sleep(2)
            return

        # Step 3: Subscribe to notifications
        print(f"\n📡 Subscribing to notifications on {CHAR_UUID}...")
        await client.start_notify(CHAR_UUID, on_notify)
        print("✅ Subscribed! Listening for 30 seconds...\n")

        # Step 4: Wait and count
        for i in range(30):
            await asyncio.sleep(1)
            if i == 5 and rx_count == 0:
                print("   ⏳ 5 seconds in, still no data... (Arduino sends every 2s)")
            if i == 10 and rx_count == 0:
                print("   ⚠️  10 seconds, no data. Trying to send PING...")
                try:
                    await client.write_gatt_char(
                        CHAR_UUID, b"PING\n", response=False
                    )
                    print("   📤 Sent PING, waiting for PONG...")
                except Exception as e:
                    print(f"   ❌ Write failed: {e}")
            if i == 15 and rx_count == 0:
                print("   ⚠️  15 seconds, still nothing. Trying write WITH response...")
                try:
                    await client.write_gatt_char(
                        CHAR_UUID, b"STATUS\n", response=True
                    )
                    print("   📤 Sent STATUS (with response=True)")
                except Exception as e:
                    print(f"   ❌ Write with response failed: {e}")

        await client.stop_notify(CHAR_UUID)

        print(f"\n{'='*50}")
        print(f"📊 RESULT: Received {rx_count} notification(s) in 30 seconds")
        if rx_count > 0:
            print("✅ BLE data reception works! The issue is in Docker/ble_bridge.")
        else:
            print("❌ No data received. Possible causes:")
            print("   1. HM-11 module is not transmitting (check Arduino Serial Monitor)")
            print("   2. HM-11 firmware doesn't support BLE notifications (needs AT+NOTI1)")
            print("   3. Another device is already connected to the HM-11 (HM-11 only supports 1 connection)")
            print("   4. BlueZ on Pi needs reset: sudo systemctl restart bluetooth")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ble_debug.py <BLE_ADDRESS>")
        print("Example: python3 ble_debug.py 00:0E:0B:1C:5F:C9")
        sys.exit(1)

    asyncio.run(main(sys.argv[1]))
