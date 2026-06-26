"""
BLE Diagnostic v2 - tries alternative connection patterns for HMSoft on Windows.
"""
import asyncio
import platform
import sys

if platform.system() == "Windows":
    try:
        from bleak.backends.winrt.util import uninitialize_sta
        uninitialize_sta()
    except ImportError:
        pass

from bleak import BleakClient, BleakScanner

DEVICE_NAME = "HMSoft"
HM11_CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
HM11_SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"


async def try_method(name, coro):
    """Try a connection method and report results."""
    print(f"\n--- {name} ---")
    try:
        await coro
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e!r}")


async def method_discover_then_connect():
    """Method 1: discover() -> filter -> BleakClient(device).connect()"""
    print("  Scanning with discover()...")
    devices = await BleakScanner.discover(timeout=8.0, return_adv=True)
    target = None
    for d, adv in devices.values():
        if d.name and DEVICE_NAME.lower() in d.name.lower():
            target = d
            print(f"  Found: {d.name} ({d.address}) rssi={adv.rssi}")
            print(f"  Service UUIDs in adv: {adv.service_uuids}")
            break
    if not target:
        print("  Device not found during scan")
        return

    print("  Connecting (no special params)...")
    client = BleakClient(target)
    await client.connect(timeout=15.0)
    print(f"  OK: Connected! is_connected={client.is_connected}")
    for svc in client.services:
        print(f"    Service: {svc.uuid}")
        for c in svc.characteristics:
            print(f"      Char: {c.uuid} [{', '.join(c.properties)}]")
    await client.disconnect()
    print("  Disconnected.")


async def method_async_with():
    """Method 2: discover() → async with BleakClient(device)"""
    print("  Scanning with discover()...")
    devices = await BleakScanner.discover(timeout=8.0, return_adv=True)
    target = None
    for d, adv in devices.values():
        if d.name and DEVICE_NAME.lower() in d.name.lower():
            target = d
            print(f"  Found: {d.name} ({d.address})")
            break
    if not target:
        print("  Device not found during scan")
        return

    print("  Connecting with async-with pattern...")
    async with BleakClient(target) as client:
        print(f"  OK: Connected! is_connected={client.is_connected}")
        for svc in client.services:
            print(f"    Service: {svc.uuid}")
            for c in svc.characteristics:
                print(f"      Char: {c.uuid} [{', '.join(c.properties)}]")
    print("  Disconnected.")


async def method_scanner_then_connect_by_address():
    """Method 3: Scan, then connect by raw address string"""
    print("  Scanning...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=8.0)
    if not device:
        print("  Device not found")
        return
    print(f"  Found: {device.name} ({device.address})")
    
    print(f"  Connecting by address string '{device.address}'...")
    client = BleakClient(device.address)
    await client.connect(timeout=15.0)
    print(f"  OK: Connected!")
    await client.disconnect()
    print("  Disconnected.")


async def method_service_uuid_scan():
    """Method 4: Scan specifically for FFE0 service UUID"""
    print("  Scanning for devices advertising FFE0 service...")
    devices = await BleakScanner.discover(
        timeout=8.0,
        return_adv=True,
        service_uuids=[HM11_SERVICE_UUID],
    )
    if not devices:
        print("  No devices found with FFE0 service UUID")
        # Try without service filter
        print("  Retrying without service UUID filter...")
        devices = await BleakScanner.discover(timeout=5.0, return_adv=True)

    target = None
    for d, adv in devices.values():
        if d.name and DEVICE_NAME.lower() in d.name.lower():
            target = d
            print(f"  Found: {d.name} ({d.address})")
            break

    if not target:
        print("  HMSoft not found")
        return

    print("  Connecting...")
    async with BleakClient(target) as client:
        print(f"  OK: Connected!")
        await client.disconnect()


async def method_retry_with_delay():
    """Method 5: Scan, wait 3 seconds, then connect (sometimes helps on Windows)"""
    print("  Scanning...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=8.0)
    if not device:
        print("  Device not found")
        return
    print(f"  Found: {device.name} ({device.address})")

    print("  Waiting 3 seconds before connecting...")
    await asyncio.sleep(3.0)

    print("  Connecting...")
    async with BleakClient(device) as client:
        print(f"  OK: Connected!")
        for svc in client.services:
            print(f"    Service: {svc.uuid}")
            for c in svc.characteristics:
                print(f"      Char: {c.uuid} [{', '.join(c.properties)}]")
    print("  Disconnected.")


async def main():
    print(f"=== BLE Diagnostic v2 ===")
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version.split()[0]}")
    print()
    print("Make sure HMSoft is NOT paired in Windows Bluetooth Settings.")
    print("Make sure no other app is connected to HMSoft.")
    print()

    await try_method("Method 1: discover() + connect()", method_discover_then_connect())
    await try_method("Method 2: discover() + async-with", method_async_with())
    await try_method("Method 3: find_by_name + connect by address", method_scanner_then_connect_by_address())
    await try_method("Method 4: Service UUID scan", method_service_uuid_scan())
    await try_method("Method 5: Scan + 3s delay + connect", method_retry_with_delay())

    print("\n" + "=" * 60)
    print("If ALL methods failed, the issue is with Windows BLE stack.")
    print("Try: restart Bluetooth adapter, restart PC, or update BT drivers.")


if __name__ == "__main__":
    asyncio.run(main())
