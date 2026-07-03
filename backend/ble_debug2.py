#!/usr/bin/env python3
"""
BLE Debug Script v2 — Deeper HM-11 diagnostics.

Tests:
  1. Notification-based reception (the normal way)
  2. Polling via read_gatt_char (fallback)  
  3. AT command probe to check HM-11 firmware config
  4. Write-then-read roundtrip test

Usage:
    /tmp/ble-test/bin/python ble_debug2.py 00:0E:0B:1C:5F:C9
"""

import asyncio
import sys


async def main(address: str):
    from bleak import BleakClient

    CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
    rx_buffer = []

    def on_notify(sender, data: bytearray):
        text = data.decode("utf-8", errors="replace")
        rx_buffer.append(text)
        print(f"  📥 NOTIFY: {repr(text)}")

    print(f"🔌 Connecting to {address}...")
    async with BleakClient(address, timeout=20.0) as client:
        print(f"✅ Connected!\n")

        # ── Test 1: Subscribe + listen briefly ──
        print("═" * 50)
        print("TEST 1: Notifications (5 seconds)")
        print("═" * 50)
        await client.start_notify(CHAR_UUID, on_notify)
        await asyncio.sleep(5)
        await client.stop_notify(CHAR_UUID)
        if rx_buffer:
            print(f"  ✅ Got {len(rx_buffer)} notification(s)!")
        else:
            print("  ❌ No notifications received.\n")

        # ── Test 2: Polling via read ──
        print("═" * 50)
        print("TEST 2: Polling via read_gatt_char (10 reads, 1s apart)")
        print("═" * 50)
        for i in range(10):
            try:
                val = await client.read_gatt_char(CHAR_UUID)
                text = val.decode("utf-8", errors="replace")
                if text and text.strip():
                    print(f"  📖 READ #{i+1}: {repr(text)}")
                else:
                    print(f"  📖 READ #{i+1}: (empty)")
            except Exception as e:
                print(f"  ❌ READ #{i+1} error: {e}")
                break
            await asyncio.sleep(1)

        # ── Test 3: AT command probe ──
        # HM-11 responds to AT commands ONLY when NOT connected from its perspective.
        # But we can try — some firmware versions respond even while connected.
        print()
        print("═" * 50)
        print("TEST 3: AT command probe (checking HM-11 config)")
        print("═" * 50)
        
        # Re-subscribe for responses
        at_responses = []
        def on_at_notify(sender, data: bytearray):
            text = data.decode("utf-8", errors="replace")
            at_responses.append(text)
            print(f"  📥 AT RESPONSE: {repr(text)}")
        
        await client.start_notify(CHAR_UUID, on_at_notify)

        at_commands = [
            ("AT", "Should respond with 'OK' if HM-11 is in AT mode"),
            ("STATUS\n", "WOP Arduino command — should respond with WOP:DATA:..."),
            ("PING\n", "WOP Arduino command — should respond with WOP:PONG"),
        ]
        
        for cmd, desc in at_commands:
            print(f"\n  📤 Sending: {repr(cmd)} — {desc}")
            try:
                await client.write_gatt_char(
                    CHAR_UUID, cmd.encode("utf-8"), response=False
                )
            except Exception as e:
                print(f"  ❌ Write failed: {e}")
            await asyncio.sleep(3)  # Give time to respond
            
            if at_responses:
                print(f"  ✅ Got response(s): {''.join(at_responses)}")
                at_responses.clear()
            else:
                print(f"  ❌ No response")

        # Also try reading right after write
        print(f"\n  📤 Sending PING, then immediately reading...")
        try:
            await client.write_gatt_char(
                CHAR_UUID, b"PING\n", response=False
            )
            await asyncio.sleep(0.5)
            val = await client.read_gatt_char(CHAR_UUID)
            text = val.decode("utf-8", errors="replace")
            print(f"  📖 READ after PING: {repr(text)}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

        await client.stop_notify(CHAR_UUID)

        # ── Summary ──
        print()
        print("═" * 50)
        print("SUMMARY")
        print("═" * 50)
        total = len(rx_buffer) + len(at_responses)
        if total > 0:
            print("✅ The HM-11 IS sending data back in some form.")
            print("   We can adjust ble_bridge.py to match this behavior.")
        else:
            print("❌ The HM-11 accepted writes but sent NOTHING back.")
            print()
            print("🔧 NEXT STEPS to try on the Arduino Serial Monitor:")
            print()
            print("   1. Open Arduino IDE Serial Monitor (9600 baud)")
            print("   2. Verify you see WOP:DATA:xxx,xxx,x,xxx every 2 seconds")
            print("      If YES → Arduino works, HM-11 is the issue")
            print("      If NO  → Arduino code issue")
            print()
            print("   3. If Arduino works, disconnect USB and power Arduino")
            print("      from external power, then run this script again.")
            print("      (Sometimes Serial and SoftwareSerial conflict on Arduino Uno)")
            print()
            print("   4. Try AT commands via Arduino Serial Monitor:")
            print("      Upload a sketch that does Serial↔SoftwareSerial passthrough,")
            print("      then send 'AT' to the HM-11 to check its mode.")
            print()
            print("   5. Check if the HM-11 TX→Arduino D2 wire is connected correctly")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ble_debug2.py <BLE_ADDRESS>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
