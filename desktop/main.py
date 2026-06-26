"""
WOP - Water Our Plants | Desktop App
Simple tkinter GUI for Arduino monitoring via USB Serial or BLE.
"""

import tkinter as tk
from tkinter import ttk
import threading
import sys
from serial_manager import SerialManager, SensorData
from ble_manager import BLEManager


class WOPApp:
    def __init__(self):
        self.serial = SerialManager()
        self.ble = BLEManager()
        self._active_manager = None  # Whichever manager is currently connected
        
        self.root = tk.Tk()
        self.root.title("WOP - Water Our Plants")
        self.root.geometry("600x550")
        self.root.minsize(500, 450)
        self.root.configure(bg="#1e1e2e")
        
        # Style
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#1e1e2e")
        self.style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4", font=("Consolas", 11))
        self.style.configure("Title.TLabel", font=("Consolas", 16, "bold"), foreground="#89b4fa")
        self.style.configure("Status.TLabel", font=("Consolas", 10))
        self.style.configure("Value.TLabel", font=("Consolas", 14, "bold"), foreground="#a6e3a1")
        self.style.configure("TButton", font=("Consolas", 10))
        self.style.configure("BLE.TButton", font=("Consolas", 10))
        
        self._build_ui()
        self._setup_callbacks()
        
    def _build_ui(self):
        # Main container
        main = ttk.Frame(self.root, padding=20)
        main.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main, text="🌱 WOP - Water Our Plants", style="Title.TLabel").pack(pady=(0, 10))
        
        # Connection frame
        conn_frame = ttk.Frame(main)
        conn_frame.pack(fill=tk.X, pady=5)
        
        self.status_label = ttk.Label(conn_frame, text="⚪ Disconnected", style="Status.TLabel")
        self.status_label.pack(side=tk.LEFT)
        
        self.btn_disconnect = ttk.Button(conn_frame, text="Disconnect", command=self._disconnect, state=tk.DISABLED)
        self.btn_disconnect.pack(side=tk.RIGHT, padx=5)
        
        self.btn_connect = ttk.Button(conn_frame, text="Auto-Detect & Connect", command=self._start_connect)
        self.btn_connect.pack(side=tk.RIGHT)
        
        # Port selection (USB Serial)
        port_frame = ttk.Frame(main)
        port_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(port_frame, text="USB:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(port_frame, textvariable=self.port_var, width=12, state="readonly")
        self.port_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(port_frame, text="Refresh", command=self._refresh_ports).pack(side=tk.LEFT)
        ttk.Button(port_frame, text="Connect USB", command=self._connect_manual).pack(side=tk.LEFT, padx=5)
        
        # BLE connection
        ble_frame = ttk.Frame(main)
        ble_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(ble_frame, text="BLE:").pack(side=tk.LEFT)
        self.btn_ble_connect = ttk.Button(ble_frame, text="📡 Connect via Bluetooth", command=self._start_ble_connect)
        self.btn_ble_connect.pack(side=tk.LEFT, padx=5)
        
        self.ble_status_hint = ttk.Label(ble_frame, text="(wireless — no cable needed)", style="Status.TLabel",
                                          foreground="#6c7086")
        self.ble_status_hint.pack(side=tk.LEFT, padx=5)
        
        # Separator
        ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Sensor data display
        data_frame = ttk.Frame(main)
        data_frame.pack(fill=tk.X, pady=5)
        
        # Soil Moisture
        row1 = ttk.Frame(data_frame)
        row1.pack(fill=tk.X, pady=3)
        ttk.Label(row1, text="💧 Soil Moisture:").pack(side=tk.LEFT)
        self.soil_label = ttk.Label(row1, text="--", style="Value.TLabel")
        self.soil_label.pack(side=tk.RIGHT)
        
        # Water Depth
        row2 = ttk.Frame(data_frame)
        row2.pack(fill=tk.X, pady=3)
        ttk.Label(row2, text="🌊 Water Depth:").pack(side=tk.LEFT)
        self.depth_label = ttk.Label(row2, text="--", style="Value.TLabel")
        self.depth_label.pack(side=tk.RIGHT)
        
        # Pump
        row3 = ttk.Frame(data_frame)
        row3.pack(fill=tk.X, pady=3)
        ttk.Label(row3, text="⚙️  Pump:").pack(side=tk.LEFT)
        self.pump_label = ttk.Label(row3, text="--", style="Value.TLabel")
        self.pump_label.pack(side=tk.RIGHT)
        
        # Uptime
        row4 = ttk.Frame(data_frame)
        row4.pack(fill=tk.X, pady=3)
        ttk.Label(row4, text="⏱️  Uptime:").pack(side=tk.LEFT)
        self.uptime_label = ttk.Label(row4, text="--", style="Value.TLabel")
        self.uptime_label.pack(side=tk.RIGHT)
        
        # Pump controls
        ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        pump_frame = ttk.Frame(main)
        pump_frame.pack(fill=tk.X, pady=5)
        ttk.Label(pump_frame, text="Pump Control:").pack(side=tk.LEFT)
        self.btn_pump_on = ttk.Button(pump_frame, text="Pump ON", command=lambda: self._send_pump("PUMP_ON"), state=tk.DISABLED)
        self.btn_pump_on.pack(side=tk.LEFT, padx=5)
        self.btn_pump_off = ttk.Button(pump_frame, text="Pump OFF", command=lambda: self._send_pump("PUMP_OFF"), state=tk.DISABLED)
        self.btn_pump_off.pack(side=tk.LEFT, padx=5)
        
        # Raw log
        ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(main, text="Log:").pack(anchor=tk.W)
        
        self.log_text = tk.Text(main, height=8, bg="#181825", fg="#a6adc8", font=("Consolas", 9),
                                insertbackground="#cdd6f4", relief=tk.FLAT, bd=0)
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Command entry
        cmd_frame = ttk.Frame(main)
        cmd_frame.pack(fill=tk.X)
        self.cmd_entry = tk.Entry(cmd_frame, bg="#313244", fg="#cdd6f4", font=("Consolas", 10),
                                  insertbackground="#cdd6f4", relief=tk.FLAT)
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.cmd_entry.bind("<Return>", self._send_custom)
        ttk.Button(cmd_frame, text="Send", command=self._send_custom).pack(side=tk.RIGHT, padx=(5, 0))
        
        self._refresh_ports()
    
    def _setup_callbacks(self):
        """Register the same callbacks on both Serial and BLE managers."""
        for manager in (self.serial, self.ble):
            manager.on_data(self._on_data)
            manager.on_connect(self._on_connect)
            manager.on_disconnect(self._on_disconnect)
            manager.on_raw_message(self._on_raw)
    
    def _refresh_ports(self):
        ports = SerialManager.list_ports()
        port_names = [p["device"] for p in ports]
        self.port_combo["values"] = port_names
        if port_names:
            self.port_combo.current(0)
        self._log(f"Found {len(port_names)} USB port(s): {', '.join(port_names) if port_names else 'none'}")
    
    # --- USB Serial connection ---
    
    def _start_connect(self):
        self.status_label.config(text="🟡 Scanning USB...", foreground="#f9e2af")
        self.btn_connect.config(state=tk.DISABLED)
        self._log("Auto-detecting WOP Arduino on USB...")
        threading.Thread(target=self._auto_connect_thread, daemon=True).start()
    
    def _auto_connect_thread(self):
        port = self.serial.auto_detect()
        if port:
            self._active_manager = self.serial
            self.serial.connect(port)
        else:
            self.root.after(0, lambda: self.status_label.config(text="🔴 Not found", foreground="#f38ba8"))
            self.root.after(0, lambda: self.btn_connect.config(state=tk.NORMAL))
            self.root.after(0, lambda: self._log("No WOP device found on USB. Try BLE or manual connect."))
    
    def _connect_manual(self):
        port = self.port_var.get()
        if port:
            self._log(f"Connecting to {port}...")
            self._active_manager = self.serial
            threading.Thread(target=lambda: self.serial.connect(port), daemon=True).start()
    
    # --- BLE connection ---
    
    def _start_ble_connect(self):
        self.status_label.config(text="🟡 Scanning BLE...", foreground="#f9e2af")
        self.btn_ble_connect.config(state=tk.DISABLED)
        self.btn_connect.config(state=tk.DISABLED)
        self._log("Scanning for WOP Bluetooth device...")
        self._active_manager = self.ble
        # BLEManager.connect() runs its own background thread
        self.ble.connect()
    
    # --- Disconnect ---
    
    def _disconnect(self):
        if self._active_manager:
            self._active_manager.disconnect()
            self._active_manager = None
    
    # --- Send commands via whichever manager is active ---
    
    def _send_pump(self, cmd: str):
        if self._active_manager:
            self._active_manager.send_command(cmd)
    
    def _send_custom(self, event=None):
        cmd = self.cmd_entry.get().strip()
        if cmd and self._active_manager and self._active_manager.connected:
            self._active_manager.send_command(cmd)
            self._log(f">>> {cmd}")
            self.cmd_entry.delete(0, tk.END)
    
    # --- Callbacks (called from serial/BLE thread, schedule on main thread) ---
    
    def _on_data(self, data):
        self.root.after(0, lambda: self._update_display(data))
    
    def _on_connect(self, port: str):
        def _update():
            is_ble = port.startswith("BLE:")
            icon = "📡" if is_ble else "🟢"
            self.status_label.config(text=f"{icon} Connected ({port})", foreground="#a6e3a1")
            self.btn_connect.config(state=tk.DISABLED)
            self.btn_ble_connect.config(state=tk.DISABLED)
            self.btn_disconnect.config(state=tk.NORMAL)
            self.btn_pump_on.config(state=tk.NORMAL)
            self.btn_pump_off.config(state=tk.NORMAL)
            self._log(f"Connected to {port}")
        self.root.after(0, _update)
    
    def _on_disconnect(self):
        def _update():
            self.status_label.config(text="⚪ Disconnected", foreground="#cdd6f4")
            self.btn_connect.config(state=tk.NORMAL)
            self.btn_ble_connect.config(state=tk.NORMAL)
            self.btn_disconnect.config(state=tk.DISABLED)
            self.btn_pump_on.config(state=tk.DISABLED)
            self.btn_pump_off.config(state=tk.DISABLED)
            self.soil_label.config(text="--")
            self.depth_label.config(text="--")
            self.pump_label.config(text="--")
            self.uptime_label.config(text="--")
            self._active_manager = None
            self._log("Disconnected")
        self.root.after(0, _update)
    
    def _on_raw(self, line: str):
        self.root.after(0, lambda: self._log(line))
    
    def _update_display(self, data):
        self.soil_label.config(text=f"{data.soil_moisture_pct}%  (raw: {data.soil_moisture})")
        self.depth_label.config(text=f"{data.water_depth_pct}%  (raw: {data.water_depth})")
        self.pump_label.config(
            text="🟢 ON" if data.pump_active else "⚪ OFF",
            foreground="#a6e3a1" if data.pump_active else "#cdd6f4"
        )
        mins, secs = divmod(data.uptime_seconds, 60)
        hours, mins = divmod(mins, 60)
        self.uptime_label.config(text=f"{hours:02d}:{mins:02d}:{secs:02d}")
    
    def _log(self, msg: str):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        # Keep log at reasonable size
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 200:
            self.log_text.delete("1.0", "50.0")
    
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()
    
    def _on_close(self):
        if self._active_manager and self._active_manager.connected:
            self._active_manager.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    app = WOPApp()
    app.run()
