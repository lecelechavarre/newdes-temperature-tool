import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import psutil
import winsound
from plyer import notification
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os

class StorageTemperatureReader:
    """Storage temperature reader specifically for storage devices using OpenHardwareMonitor"""
    def __init__(self):
        self.wmi_available = False
        self.ohm_available = True
        self.initialize_wmi()
    
    def initialize_wmi(self):
        """Initialize WMI connection and check OpenHardwareMonitor availability"""
        try:
            import wmi
            self.wmi_available = True
            print("✅ WMI support initialized")
            
            # Test if OpenHardwareMonitor is running
            try:
                w = wmi.WMI(namespace="root\\OpenHardwareMonitor")
                sensors = w.Sensor()
                self.ohm_available = True
                print("✅ OpenHardwareMonitor detected and accessible")
                print(f"📊 Found {len(sensors)} sensors")
                
                # Print ALL temperature sensors for debugging
                temp_sensors = [s for s in sensors if s.SensorType == "Temperature"]
                print("🌡️ All temperature sensors:")
                for sensor in temp_sensors:
                    print(f"  - {sensor.Name}: {sensor.Value}°C (Parent: {sensor.Parent})")
                    
            except Exception as e:
                print("❌ OpenHardwareMonitor not detected or not running")
                print("💡 Please run OpenHardwareMonitor as Administrator")
                self.ohm_available = False
                
        except ImportError:
            print("❌ WMI not available - install: pip install wmi")
            self.wmi_available = False
            self.ohm_available = False
    
    def _is_storage_sensor(self, sensor_name, parent_name):
        """Check if sensor belongs to a storage device"""
        storage_keywords = [
            'hdd', 'ssd', 'disk', 'drive', 'nvme', 'sata', 
            'hard disk', 'solid state', 'samsung', 'crucial',
            'western digital', 'seagate', 'kingston', 'adata',
            'sandisk', 'intel ssd', 'toshiba', 'hitachi'
        ]
        
        sensor_lower = sensor_name.lower()
        parent_lower = parent_name.lower() if parent_name else ""
        
        # Check if it's a temperature sensor under a storage device
        if "temperature" in sensor_lower:
            # Check if parent is a storage device
            if any(keyword in parent_lower for keyword in storage_keywords):
                return True
            
            # Check if sensor name itself indicates storage
            if any(keyword in sensor_lower for keyword in storage_keywords):
                return True
        
        return False
    
    def get_storage_temperatures(self):
        """Get temperatures for all storage devices from OpenHardwareMonitor"""
        storage_temps = {}
        
        if not self.ohm_available:
            print("❌ OpenHardwareMonitor not available - no temperature data")
            return None
        
        try:
            import wmi
            w = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            sensors = w.Sensor()
            
            # Look for ALL temperature sensors first
            all_temp_sensors = []
            for sensor in sensors:
                if (sensor.SensorType == "Temperature" and 
                    sensor.Value is not None):
                    
                    all_temp_sensors.append({
                        'name': sensor.Name,
                        'value': float(sensor.Value),
                        'parent': sensor.Parent if hasattr(sensor, 'Parent') else "Unknown"
                    })
            
            print(f"🔍 Found {len(all_temp_sensors)} temperature sensors total")
            
            # Filter for storage temperatures
            storage_sensors = []
            for sensor in all_temp_sensors:
                if self._is_storage_sensor(sensor['name'], sensor['parent']):
                    storage_sensors.append(sensor)
                else:
                    print(f"  Skipping non-storage: {sensor['name']} (Parent: {sensor['parent']})")
            
            print(f"💾 Found {len(storage_sensors)} storage temperature sensors")
            
            # Organize storage temperatures
            for sensor in storage_sensors:
                # Use parent name if available, otherwise use sensor name
                if sensor['parent'] and sensor['parent'] != "Unknown":
                    device_name = sensor['parent']
                else:
                    device_name = sensor['name']
                
                # Subtract 10°C from actual reading for room temperature uniformity
                raw_temp = sensor['value']
                adjusted_temp = raw_temp - 13
                storage_temps[device_name] = adjusted_temp
                
                print(f"  {device_name}: {raw_temp}°C")
            
            # If we found storage temperatures, return them
            if storage_temps:
                print("📊 Storage temperatures found:")
                for device, temp in storage_temps.items():
                    print(f"  {device}: {temp}°C")
                return storage_temps
            else:
                print("❌ No storage temperatures found in OpenHardwareMonitor")
                # Let's try an alternative approach - look for any temperature under storage devices
                return self._find_storage_temps_alternative(sensors)
            
        except Exception as e:
            print(f"❌ Error reading storage temperatures: {e}")
            self.ohm_available = False
            return None
    
    def _find_storage_temps_alternative(self, sensors):
        """Alternative method to find storage temperatures"""
        print("🔄 Trying alternative storage detection method...")
        storage_temps = {}
        
        # Get all hardware items to find storage devices
        try:
            import wmi
            w = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            hardware_items = w.Hardware()
            
            storage_devices = []
            for hardware in hardware_items:
                hw_name = hardware.Name if hardware.Name else ""
                hw_lower = hw_name.lower()
                
                # Check if this is a storage device
                storage_keywords = ['ssd', 'hdd', 'disk', 'drive', 'samsung', 'crucial', 'wd', 'seagate']
                if any(keyword in hw_lower for keyword in storage_keywords):
                    storage_devices.append(hw_name)
                    print(f"  Found storage device: {hw_name}")
            
            # Now look for temperature sensors under these storage devices
            for sensor in sensors:
                if (sensor.SensorType == "Temperature" and 
                    sensor.Value is not None and
                    hasattr(sensor, 'Parent') and
                    sensor.Parent in storage_devices):
                    
                    # Subtract 10°C from actual reading
                    raw_temp = float(sensor.Value)
                    adjusted_temp = raw_temp - 10
                    storage_temps[sensor.Parent] = adjusted_temp
                    print(f"  Found temperature for {sensor.Parent}: {raw_temp}°C -> {adjusted_temp}°C")
        
        except Exception as e:
            print(f"❌ Alternative method failed: {e}")
        
        return storage_temps if storage_temps else None
    
    def get_average_storage_temperature(self):
        """Get the average temperature across all storage devices"""
        storage_temps = self.get_storage_temperatures()
        if storage_temps:
            avg_temp = sum(storage_temps.values()) / len(storage_temps)
            print(f"📈 Average storage temperature: {avg_temp:.1f}°C")
            return avg_temp
        else:
            return None
    
    def get_max_storage_temperature(self):
        """Get the maximum temperature among all storage devices"""
        storage_temps = self.get_storage_temperatures()
        if storage_temps:
            max_temp = max(storage_temps.values())
            max_device = max(storage_temps, key=storage_temps.get)
            print(f"🔥 Hottest storage: {max_device} at {max_temp:.1f}°C")
            return max_temp
        else:
            return None
    
    def get_detailed_sensor_info(self):
        """Get detailed information about all available sensors"""
        if not self.wmi_available:
            return "WMI not available"
        
        try:
            import wmi
            info = []
            
            # OpenHardwareMonitor sensors
            if self.ohm_available:
                try:
                    w = wmi.WMI(namespace="root\\OpenHardwareMonitor")
                    sensors = w.Sensor()
                    info.append("=== OpenHardwareMonitor All Temperature Sensors ===")
                    
                    # Show all temperature sensors with their parent information
                    temp_sensors = [s for s in sensors if s.SensorType == "Temperature" and s.Value is not None]
                    
                    if temp_sensors:
                        for sensor in temp_sensors:
                            parent_info = sensor.Parent if hasattr(sensor, 'Parent') else "No parent"
                            raw_temp = float(sensor.Value)
                            adjusted_temp = raw_temp - 10
                            info.append(f"  {sensor.Name}: {raw_temp}°C -> {adjusted_temp}°C (Parent: {parent_info})")
                    else:
                        info.append("No temperature sensors found")
                        
                except Exception as e:
                    info.append(f"OpenHardwareMonitor error: {e}")
            
            return "\n".join(info) if info else "No sensor information available"
            
        except Exception as e:
            return f"Error getting sensor info: {e}"

class TemperatureMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Storage Temperature Monitor")
        
        # Condition 1: Set window to full screen mode (1200x800)
        self.root.geometry("1200x800")
        self.root.state('zoomed')  # Maximize window
        
        # Modern professional color palette
        self.colors = {
            'primary': '#2563eb',      # Professional Blue
            'secondary': '#3b82f6',    # Medium Blue
            'accent': '#60a5fa',       # Light Blue
            'background': '#f8fafc',   # Off-white background
            'surface': '#ffffff',      # White surface
            'card_bg': '#ffffff',      # Card background
            'text_primary': '#1f2937', # Dark text
            'text_secondary': '#6b7280', # Medium text
            'success': '#10b981',      # Green
            'warning': '#f59e0b',      # Amber
            'error': '#ef4444',        # Red
            'border': '#e5e7eb',       # Light border
            'hover': '#f3f4f6'         # Hover state
        }
        
        # Apply modern styling
        self.setup_modern_styles()
        
        # Temperature thresholds 
        self.critical_temp = 30  
        self.warning_temp = 27   
        
        # Monitoring state
        self.is_monitoring = True
        self.alert_monitoring_active = True
        self.monitor_thread = None
        self.email_thread = None
        
        # Alert tracking
        self.last_warning_time = 0
        self.warning_cooldown = 30
        self.last_email_time = 0
        self.email_interval = 3600  
        
        # Temperature history for graphing
        self.temp_history = deque(maxlen=50)
        self.time_history = deque(maxlen=50)
        
        # For email statistics
        self.min_temp = float('inf')
        self.max_temp = float('-inf')
        
        # Storage temperatures storage
        self.storage_temperatures = {}
        
        # Storage temperature reader
        self.temp_reader = StorageTemperatureReader()
        
        # Email configuration
        self.email_config = {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'sender_email': 'iantolentino0110@gmail.com',  # Your email
            'sender_password': 'kwor ngta azao fukw',  # You need to set this
            'receiver_email': 'supercompnxp@gmail.com, ian.tolentino.bp@j-display.com, ferrerasroyce@gmail.com'
        }
        
        self.load_settings()
        self.setup_ui()
        self.start_realtime_updates()
        self.start_email_scheduler()
        
    def setup_modern_styles(self):
        """Configure modern professional styling"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        self.root.configure(bg=self.colors['background'])
        
        # Configure modern styles
        style.configure('Modern.TFrame', background=self.colors['background'])
        style.configure('Card.TFrame', 
                       background=self.colors['card_bg'],
                       relief='flat', 
                       borderwidth=0,
                       border=0)
        
        style.configure('Card.TLabelframe', 
                       background=self.colors['card_bg'],
                       relief='flat',
                       borderwidth=1,
                       bordercolor=self.colors['border'])
        
        style.configure('Card.TLabelframe.Label',
                       background=self.colors['card_bg'],
                       foreground=self.colors['text_primary'],
                       font=('Segoe UI', 10, 'bold'))
        
        # Modern button styles
        style.configure('Primary.TButton',
                       background=self.colors['primary'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       font=('Segoe UI', 9, 'bold'),
                       padding=(15, 8))
        
        style.configure('Secondary.TButton',
                       background=self.colors['surface'],
                       foreground=self.colors['text_primary'],
                       borderwidth=1,
                       bordercolor=self.colors['border'],
                       focuscolor='none',
                       font=('Segoe UI', 9),
                       padding=(15, 8))
        
        style.map('Primary.TButton',
                 background=[('active', self.colors['secondary']),
                           ('pressed', self.colors['secondary'])])
        
        style.map('Secondary.TButton',
                 background=[('active', self.colors['hover']),
                           ('pressed', self.colors['hover'])])
    
    def load_settings(self):
        """Load settings from file"""
        try:
            if os.path.exists('temperature_monitor_settings.json'):
                with open('temperature_monitor_settings.json', 'r') as f:
                    settings = json.load(f)
                    self.critical_temp = settings.get('critical_temp', 30)
                    self.warning_temp = settings.get('warning_temp', 27)
        except Exception as e:
            print(f"Error loading settings: {e}")
    
    def save_settings(self):
        """Save settings to file"""
        try:
            settings = {
                'critical_temp': self.critical_temp,
                'warning_temp': self.warning_temp
            }
            with open('temperature_monitor_settings.json', 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")
        
    def setup_ui(self):
        # Main frame with modern styling
        main_frame = ttk.Frame(self.root, style='Modern.TFrame', padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header section - Compact and professional
        header_frame = ttk.Frame(main_frame, style='Modern.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Title with modern styling
        title_frame = ttk.Frame(header_frame, style='Modern.TFrame')
        title_frame.pack(fill=tk.X)
        
        title_label = ttk.Label(title_frame, text="Storage Temperature Monitor", 
                               background=self.colors['background'],
                               foreground=self.colors['primary'],
                               font=("Segoe UI", 18, "bold"))
        title_label.pack(side=tk.LEFT)
        
        # Note about temperature adjustment
        note_label = ttk.Label(header_frame, 
                              text="Note: Temperatures shown are adjusted for room temperature (not actual device readings)", 
                              background=self.colors['background'],
                              foreground=self.colors['text_secondary'],
                              font=("Segoe UI", 9))
        note_label.pack(anchor=tk.W, pady=(5, 0))
        
        # Compact metrics cards in a row
        metrics_frame = ttk.Frame(main_frame, style='Modern.TFrame')
        metrics_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Average temperature card
        avg_card = ttk.Frame(metrics_frame, style='Card.TFrame', padding="15")
        avg_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        
        ttk.Label(avg_card, text="AVERAGE TEMP", 
                 background=self.colors['card_bg'],
                 foreground=self.colors['text_secondary'],
                 font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        
        self.avg_temp_var = tk.StringVar(value="--°C")
        self.avg_temp_display = ttk.Label(avg_card, textvariable=self.avg_temp_var, 
                                         background=self.colors['card_bg'],
                                         foreground=self.colors['primary'],
                                         font=("Segoe UI", 20, "bold"))
        self.avg_temp_display.pack(anchor=tk.W, pady=(5, 0))
        
        # Max temperature card
        max_card = ttk.Frame(metrics_frame, style='Card.TFrame', padding="15")
        max_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 8))
        
        ttk.Label(max_card, text="MAX TEMP", 
                 background=self.colors['card_bg'],
                 foreground=self.colors['text_secondary'],
                 font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        
        self.max_temp_var = tk.StringVar(value="--°C")
        self.max_temp_display = ttk.Label(max_card, textvariable=self.max_temp_var, 
                                         background=self.colors['card_bg'],
                                         foreground=self.colors['primary'],
                                         font=("Segoe UI", 20, "bold"))
        self.max_temp_display.pack(anchor=tk.W, pady=(5, 0))
        
        # Sensor status card - UPDATED: Now includes system status (Condition 1)
        sensor_card = ttk.Frame(metrics_frame, style='Card.TFrame', padding="15")
        sensor_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))
        
        ttk.Label(sensor_card, text="SENSOR STATUS", 
                 background=self.colors['card_bg'],
                 foreground=self.colors['text_secondary'],
                 font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        
        # Sensor connection status
        self.sensor_status_var = tk.StringVar()
        sensor_status_label = ttk.Label(sensor_card, textvariable=self.sensor_status_var,
                                      background=self.colors['card_bg'],
                                      foreground=self.colors['text_primary'],
                                      font=("Segoe UI", 10))
        sensor_status_label.pack(anchor=tk.W, pady=(5, 0))
        
        # System status - MOVED to sensor status section (Condition 1)
        self.status_var = tk.StringVar(value="Initializing...")
        status_label = ttk.Label(sensor_card, textvariable=self.status_var,
                                background=self.colors['card_bg'],
                                foreground=self.colors['text_primary'],
                                font=("Segoe UI", 9))
        status_label.pack(anchor=tk.W, pady=(2, 0))
        
        self.update_sensor_status()
        
        # Main content area - Responsive layout
        content_frame = ttk.Frame(main_frame, style='Modern.TFrame')
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left column - Enhanced Temperature History
        left_column = ttk.Frame(content_frame, style='Modern.TFrame')
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Professional Temperature History Graph - UPDATED: Wider to show full title (Condition 2)
        history_frame = ttk.LabelFrame(left_column, text="TEMPERATURE HISTORY", 
                                      style='Card.TLabelframe', padding="12")
        history_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create professional matplotlib figure
        plt.rcParams['axes.facecolor'] = self.colors['card_bg']
        plt.rcParams['figure.facecolor'] = self.colors['card_bg']
        plt.rcParams['axes.edgecolor'] = self.colors['border']
        plt.rcParams['axes.labelcolor'] = self.colors['text_primary']
        plt.rcParams['text.color'] = self.colors['text_primary']
        plt.rcParams['xtick.color'] = self.colors['text_secondary']
        plt.rcParams['ytick.color'] = self.colors['text_secondary']
        plt.rcParams['font.size'] = 9
        plt.rcParams['axes.titlesize'] = 11
        plt.rcParams['axes.labelsize'] = 10
        
        self.fig, self.ax = plt.subplots(figsize=(10, 6))
        self.fig.tight_layout(pad=3.0)
        self.canvas = FigureCanvasTkAgg(self.fig, master=history_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Right column - Compact Controls
        right_column = ttk.Frame(content_frame, style='Modern.TFrame')
        right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=(10, 0))
        
        # Monitoring Controls - Compact
        controls_frame = ttk.LabelFrame(right_column, text="CONTROLS", 
                                       style='Card.TLabelframe', padding="12")
        controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Alert controls
        self.start_button = ttk.Button(controls_frame, text="▶ Start Alerts", 
                                      command=self.start_alert_monitoring, 
                                      style='Primary.TButton')
        self.start_button.pack(fill=tk.X, pady=(0, 5))
        
        self.stop_button = ttk.Button(controls_frame, text="⏹ Stop Alerts", 
                                     command=self.stop_alert_monitoring, 
                                     state="disabled", 
                                     style='Secondary.TButton')
        self.stop_button.pack(fill=tk.X, pady=(0, 10))
        
        # Refresh controls
        refresh_frame = ttk.Frame(controls_frame, style='Card.TFrame')
        refresh_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(refresh_frame, text="Update Interval:", 
                 background=self.colors['card_bg']).pack(anchor=tk.W)
        self.refresh_rate_var = tk.StringVar(value="2")
        refresh_combo = ttk.Combobox(refresh_frame, textvariable=self.refresh_rate_var,
                                    values=["1", "2", "5", "10"], 
                                    width=8, 
                                    state="readonly",
                                    height=4)
        refresh_combo.pack(fill=tk.X, pady=(5, 5))
        
        refresh_button = ttk.Button(refresh_frame, text="🔄 Refresh Now", 
                                  command=self.manual_refresh, 
                                  style='Secondary.TButton')
        refresh_button.pack(fill=tk.X, pady=(5, 5))
        
        # Utility buttons
        utils_frame = ttk.Frame(controls_frame, style='Card.TFrame')
        utils_frame.pack(fill=tk.X)
        
        sensor_button = ttk.Button(utils_frame, text="📊 Sensor Info", 
                                  command=self.show_sensor_info, 
                                  style='Secondary.TButton')
        sensor_button.pack(fill=tk.X, pady=(0, 5))
        
        email_button = ttk.Button(utils_frame, text="✉️ Test Email", 
                                 command=self.send_test_email, 
                                 style='Secondary.TButton')
        email_button.pack(fill=tk.X, pady=(0, 5))
        
        # Settings - Compact - UPDATED: Wider to show full button text (Condition 2)
        settings_frame = ttk.LabelFrame(right_column, text="SETTINGS", 
                                       style='Card.TLabelframe', padding="12")
        settings_frame.pack(fill=tk.X)
        
        # Warning temperature
        ttk.Label(settings_frame, text="Warning Temp (°C):", 
                 background=self.colors['card_bg']).pack(anchor=tk.W, pady=(0, 2))
        self.warning_var = tk.StringVar(value=str(self.warning_temp))
        warning_entry = ttk.Entry(settings_frame, textvariable=self.warning_var, 
                                 width=12, font=('Segoe UI', 9))
        warning_entry.pack(fill=tk.X, pady=(0, 8))
        
        # Critical temperature
        ttk.Label(settings_frame, text="Critical Temp (°C):", 
                 background=self.colors['card_bg']).pack(anchor=tk.W, pady=(0, 2))
        self.critical_var = tk.StringVar(value=str(self.critical_temp))
        critical_entry = ttk.Entry(settings_frame, textvariable=self.critical_var, 
                                  width=12, font=('Segoe UI', 9))
        critical_entry.pack(fill=tk.X, pady=(0, 8))
        
        # Update settings button - UPDATED: Wider to show full text (Condition 2)
        update_button = ttk.Button(settings_frame, text="💾 Save Settings", 
                                  command=self.update_settings, 
                                  style='Primary.TButton')
        update_button.pack(fill=tk.X, pady=(5, 0))
        
        # Footer with modern styling
        footer_frame = ttk.Frame(main_frame, style='Modern.TFrame')
        footer_frame.pack(fill=tk.X, pady=(15, 0))
        
        self.last_update_var = tk.StringVar(value="Last update: --")
        last_update_label = ttk.Label(footer_frame, textvariable=self.last_update_var,
                                     background=self.colors['background'],
                                     foreground=self.colors['text_secondary'],
                                     font=("Segoe UI", 8))
        last_update_label.pack(side=tk.LEFT)
        
        self.time_var = tk.StringVar(value="--:--:--")
        time_label = ttk.Label(footer_frame, textvariable=self.time_var,
                              background=self.colors['background'],
                              foreground=self.colors['text_secondary'],
                              font=("Segoe UI", 8))
        time_label.pack(side=tk.LEFT, padx=(20, 0))
        
        self.next_email_var = tk.StringVar(value="Next report: --")
        next_email_label = ttk.Label(footer_frame, textvariable=self.next_email_var,
                                    background=self.colors['background'],
                                    foreground=self.colors['text_secondary'],
                                    font=("Segoe UI", 8))
        next_email_label.pack(side=tk.RIGHT)
        
        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
    
    def update_sensor_status(self):
        """Update sensor status display"""
        if self.temp_reader.ohm_available:
            status = "✅ Connected"
            color = self.colors['success']
        else:
            status = "❌ Not Available"
            color = self.colors['error']
        
        self.sensor_status_var.set(status)
    
    def show_sensor_info(self):
        """Show detailed sensor information"""
        info = self.temp_reader.get_detailed_sensor_info()
        messagebox.showinfo("Storage Sensor Information", info)
    
    def start_realtime_updates(self):
        """Start real-time temperature updates immediately"""
        self.is_monitoring = True
        self.update_time_display()
        self.monitor_thread = threading.Thread(target=self.monitor_temperature, daemon=True)
        self.monitor_thread.start()
        
    def start_email_scheduler(self):
        """Start the email scheduler thread"""
        self.email_thread = threading.Thread(target=self.email_scheduler, daemon=True)
        self.email_thread.start()
        
    def update_time_display(self):
        """Update the current time display"""
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        self.time_var.set(f"Time: {current_time}")
        
        # Update next email report time
        next_email_time = self.last_email_time + self.email_interval
        time_until_next = next_email_time - time.time()
        if time_until_next > 0:
            minutes = int(time_until_next // 60)
            seconds = int(time_until_next % 60)
            self.next_email_var.set(f"Next report: {minutes:02d}:{seconds:02d}")
        else:
            self.next_email_var.set("Next report: Soon")
            
        self.root.after(1000, self.update_time_display)
        
    def get_system_info(self):
        """Get system usage info"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            return cpu_percent, memory_percent
        except:
            return None, None
    
    def update_status_indicator(self, temperature):
        """Update the status indicator color based on temperature"""
        # Status indicator is now removed from header and moved to sensor status section
        pass
    
    def send_desktop_notification(self, title, message, temp):
        """Send system desktop notification"""
        try:
            notification.notify(
                title=title,
                message=f"{message}\nHottest storage: {temp:.1f}°C",
                timeout=10,
                app_name="Storage Temperature Monitor"
            )
            print(f"Desktop notification sent: {title}")
        except Exception as e:
            print(f"Error sending desktop notification: {e}")
        
        # Play sound alert
        try:
            winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
        except:
            pass
    
    def send_email_report(self):
        """Send email report with temperature statistics"""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_config['sender_email']
            msg['To'] = self.email_config['receiver_email']
            msg['Subject'] = f"Storage Temperature Report - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Get current temperatures
            current_temps = self.storage_temperatures
            current_max = self.temp_reader.get_max_storage_temperature()
            
            # Prepare actions based on temperature
            actions = []
            if current_max is not None:
                if current_max >= self.critical_temp:
                    actions = [
                        "🚨 IMMEDIATE ACTION REQUIRED:",
                        "- Check cooling system immediately",
                        "- Consider reducing server load",
                        "- Ensure proper ventilation around storage devices",
                        "- Monitor temperatures closely",
                        "- Consider temporary shutdown if temperatures continue to rise"
                    ]
                elif current_max >= self.warning_temp:
                    actions = [
                        "⚠️ WARNING - Monitoring Required:",
                        "- Check ventilation around storage devices",
                        "- Monitor temperature trends",
                        "- Ensure cooling system is functioning properly",
                        "- Consider optimizing server load"
                    ]
                else:
                    actions = [
                        "✅ System operating normally:",
                        "- No immediate action required",
                        "- Continue regular monitoring"
                    ]
            
            # Build email body
            storage_details = "\n".join([f"  - {device}: {temp:.1f}°C" for device, temp in current_temps.items()]) if current_temps else "  No storage temperature data available"
            
            body = f"""
Temperature Monitoring Report
=====================================

Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This automated report provides an overview of the current room temperature status.

Temperature Statistics:
• Current Temperature: {current_max if current_max else 'N/A':.1f}°C
• Estimated IDRAC Temperature: {(current_max -2) if current_max else 'N/A':.1f}°C
• Minimum Temperature: {self.min_temp if self.min_temp != float('inf') else 'N/A':.1f}°C
• Maximum Temperature: {self.max_temp if self.max_temp != float('-inf') else 'N/A':.1f}°C

System Status Overview:
• Warning Threshold: {self.warning_temp}°C
• Critical Threshold: {self.critical_temp}°C
• Current Status: {'CRITICAL' if current_max and current_max >= self.critical_temp else 'WARNING' if current_max and current_max >= self.warning_temp else 'NORMAL'}

Recommended Actions:
{chr(10).join(actions)}

Monitoring Details:
• Device: {os.environ.get('COMPUTERNAME', 'Unknown Device')}
• Report Type: Automated Temperature Monitoring
• Monitoring Interval: 60 Minutes

This is an automated notification from the Temperature Monitoring System.
No response is required unless immediate action is indicated above.
"""
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect to server and send email
            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['sender_email'], self.email_config['sender_password'])
            server.send_message(msg)
            server.quit()
            
            print(f"✅ Email report sent successfully at {datetime.datetime.now().strftime('%H:%M:%S')}")
            return True
            
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            return False
    
    def send_test_email(self):
        """Send a test email"""
        try:
            success = self.send_email_report()
            if success:
                messagebox.showinfo("Success", "Test email sent successfully!")
            else:
                messagebox.showerror("Error", "Failed to send test email. Check your email configuration.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send test email: {str(e)}")
    
    def email_scheduler(self):
        """Email scheduler that sends reports every 5 minutes"""
        while self.is_monitoring:
            try:
                current_time = time.time()
                
                # Send email every 5 minutes
                if current_time - self.last_email_time >= self.email_interval:
                    if self.storage_temperatures:  # Only send if we have data
                        print("🕒 Sending scheduled email report...")
                        self.send_email_report()
                        self.last_email_time = current_time
                    
                    # Reset min/max for next period
                    self.min_temp = float('inf')
                    self.max_temp = float('-inf')
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                print(f"Email scheduler error: {e}")
                time.sleep(60)
    
    def update_storage_display(self):
        """Update the storage devices display"""
        # This method is kept for internal data management but UI elements are removed
        pass
    
    def update_graph(self):
        """Update the temperature history graph with professional design"""
        self.ax.clear()
        
        if len(self.temp_history) > 0:
            time_minutes = [t/60 for t in self.time_history]
            
            # Professional plot styling
            line = self.ax.plot(time_minutes, list(self.temp_history), 
                              color=self.colors['primary'], 
                              linewidth=2.5, 
                              label='Temperature',
                              marker='o',
                              markersize=3,
                              alpha=0.9)
            
            # Professional threshold lines
            self.ax.axhline(y=self.warning_temp, 
                          color=self.colors['warning'], 
                          linestyle='--', 
                          linewidth=1.5, 
                          alpha=0.7, 
                          label=f'Warning ({self.warning_temp}°C)')
            
            self.ax.axhline(y=self.critical_temp, 
                          color=self.colors['error'], 
                          linestyle='--', 
                          linewidth=1.5, 
                          alpha=0.7, 
                          label=f'Critical ({self.critical_temp}°C)')
            
            # Professional labels and title - UPDATED: Shorter title to fit (Condition 2)
            self.ax.set_ylabel('Temperature (°C)', fontsize=10, fontweight='bold')
            self.ax.set_xlabel('Time (minutes)', fontsize=10, fontweight='bold')
            self.ax.set_title('Temperature Trend',  # Shorter title to ensure it fits
                            fontsize=12, fontweight='bold', pad=15)
            
            # Professional legend
            self.ax.legend(loc='upper right', fontsize=9, framealpha=0.95)
            
            # Professional grid
            self.ax.grid(True, alpha=0.2, linestyle='-')
            
            # Set professional y-axis limits
            if self.temp_history:
                current_min = min(self.temp_history)
                current_max = max(self.temp_history)
                padding = max(2, (current_max - current_min) * 0.1)
                self.ax.set_ylim(max(0, current_min - padding), current_max + padding)
            
            # Professional spine styling
            for spine in self.ax.spines.values():
                spine.set_color(self.colors['border'])
                spine.set_linewidth(1)
        
        else:
            # Professional no-data message
            self.ax.text(0.5, 0.5, 'Collecting temperature data...', 
                        horizontalalignment='center', verticalalignment='center',
                        transform=self.ax.transAxes, fontsize=11,
                        bbox=dict(boxstyle="round,pad=0.3", facecolor=self.colors['hover']))
            self.ax.set_xlim(0, 1)
            self.ax.set_ylim(0, 1)
            self.ax.set_xticks([])
            self.ax.set_yticks([])
        
        self.canvas.draw()
    
    def monitor_temperature(self):
        """Main monitoring loop"""
        start_time = time.time()
        
        while self.is_monitoring:
            try:
                # Get all storage temperatures
                self.storage_temperatures = self.temp_reader.get_storage_temperatures()
                max_temp = self.temp_reader.get_max_storage_temperature()
                avg_temp = self.temp_reader.get_average_storage_temperature()
                cpu_percent, memory_percent = self.get_system_info()
                
                if max_temp is not None:
                    current_time = time.time() - start_time
                    
                    # Update min/max for email reports
                    if max_temp < self.min_temp:
                        self.min_temp = max_temp
                    if max_temp > self.max_temp:
                        self.max_temp = max_temp
                    
                    # Update display immediately
                    self.root.after(0, self.update_display, max_temp, avg_temp, cpu_percent, memory_percent, current_time)
                    
                    # Update history with max temperature
                    self.temp_history.append(max_temp)
                    self.time_history.append(current_time)
                    
                    # Check for alerts only if alert monitoring is active
                    if self.alert_monitoring_active:
                        current_absolute_time = time.time()
                        
                        if max_temp >= self.critical_temp:
                            # Send critical alerts (with cooldown)
                            if current_absolute_time - self.last_warning_time > self.warning_cooldown:
                                self.root.after(0, self.send_desktop_notification,
                                              "🔥 CRITICAL STORAGE TEMPERATURE ALERT!",
                                              "Storage temperature is critically high!",
                                              max_temp)
                                self.last_warning_time = current_absolute_time
                                
                        elif max_temp >= self.warning_temp:
                            # Send warning alerts (with cooldown)
                            if current_absolute_time - self.last_warning_time > self.warning_cooldown:
                                self.root.after(0, self.send_desktop_notification,
                                              "⚠️ HIGH STORAGE TEMPERATURE WARNING",
                                              "Storage temperature is above normal",
                                              max_temp)
                                self.last_warning_time = current_absolute_time
                else:
                    # No temperature data available
                    current_time = time.time() - start_time
                    self.root.after(0, self.update_display, None, None, None, None, current_time)
                
                # Get refresh rate from UI
                try:
                    refresh_delay = max(1, float(self.refresh_rate_var.get()))
                except:
                    refresh_delay = 2
                    
                time.sleep(refresh_delay)
                
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(5)
    
    def update_display(self, max_temp, avg_temp, cpu_percent, memory_percent, current_time):
        """Update the UI display with current readings"""
        # Update average and max temperatures
        if avg_temp is not None:
            self.avg_temp_var.set(f"{avg_temp:.1f}°C")
        else:
            self.avg_temp_var.set("--°C")
            
        if max_temp is not None:
            self.max_temp_var.set(f"{max_temp:.1f}°C")
        else:
            self.max_temp_var.set("--°C")
        
        # Update system status in sensor status section (Condition 1)
        if max_temp is None:
            status_text = "No sensor data"
            self.max_temp_display.config(foreground=self.colors['error'])
            self.avg_temp_display.config(foreground=self.colors['error'])
        elif max_temp >= self.critical_temp:
            status_text = f"CRITICAL {max_temp:.1f}°C"
            self.max_temp_display.config(foreground=self.colors['error'])
            self.avg_temp_display.config(foreground=self.colors['error'])
        elif max_temp >= self.warning_temp:
            status_text = f"WARNING {max_temp:.1f}°C"
            self.max_temp_display.config(foreground=self.colors['warning'])
            self.avg_temp_display.config(foreground=self.colors['warning'])
        else:
            status_text = f"Normal {max_temp:.1f}°C"
            self.max_temp_display.config(foreground=self.colors['success'])
            self.avg_temp_display.config(foreground=self.colors['success'])
        
        # Add alert status to display
        if self.alert_monitoring_active:
            status_text += " | Alerts ON"
        else:
            status_text += " | Alerts OFF"
            
        self.status_var.set(status_text)
        
        update_time = datetime.datetime.now().strftime("%H:%M:%S")
        self.last_update_var.set(f"Updated: {update_time}")
        
        self.update_graph()
    
    def start_alert_monitoring(self):
        """Start alert monitoring (notifications)"""
        self.alert_monitoring_active = True
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        messagebox.showinfo("Alerts Enabled", "Storage temperature alert monitoring is now active!\n\nYou will receive notifications when storage temperatures exceed thresholds.")
    
    def stop_alert_monitoring(self):
        """Stop alert monitoring (notifications)"""
        self.alert_monitoring_active = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        messagebox.showinfo("Alerts Disabled", "Storage temperature alert monitoring is now inactive.")
    
    def manual_refresh(self):
        """Force an immediate temperature refresh"""
        self.storage_temperatures = self.temp_reader.get_storage_temperatures()
        max_temp = self.temp_reader.get_max_storage_temperature()
        avg_temp = self.temp_reader.get_average_storage_temperature()
        cpu_percent, memory_percent = self.get_system_info()
        if max_temp is not None:
            self.update_display(max_temp, avg_temp, cpu_percent, memory_percent, 
                              len(self.time_history) * float(self.refresh_rate_var.get()))
    
    def update_settings(self):
        """Update temperature threshold settings"""
        try:
            new_warning = float(self.warning_var.get())
            new_critical = float(self.critical_var.get())
            
            if new_warning >= new_critical:
                messagebox.showerror("Error", "Warning temperature must be lower than critical temperature")
                return
            
            self.warning_temp = new_warning
            self.critical_temp = new_critical
            self.save_settings()
            
            messagebox.showinfo("Success", "Temperature settings updated successfully")
            
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers for temperature thresholds")
    
    def on_closing(self):
        """Clean up when closing the application"""
        self.is_monitoring = False
        self.save_settings()
        self.root.destroy()

def main():
    # Check dependencies
    try:
        import psutil
        from plyer import notification
        # Try to import WMI (required)
        try:
            import wmi
            print("✅ WMI support available")
        except ImportError:
            print("❌ WMI not available - install with: pip install wmi")
            messagebox.showerror("Missing Dependency", "WMI is required for this application.\n\nPlease install it with: pip install wmi")
            return
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Please install required packages:")
        print("pip install psutil plyer matplotlib wmi")
        messagebox.showerror("Missing Dependencies", f"Missing required packages:\n\nPlease install: pip install psutil plyer matplotlib wmi")
        return
    
    # Create and run the application
    root = tk.Tk()
    app = TemperatureMonitor(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    root.mainloop()

if __name__ == "__main__":
    main()
