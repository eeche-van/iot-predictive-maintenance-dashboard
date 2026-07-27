"""
gui_dashboardHD.py

GUI Dashboard Client

functions:
- displays machine telemetry and maintenance status
- visualises temperature and vibration trends
- provides emergency stop and maintenance reset controls
- displays MQTT communication events and alerts
"""
# python code (extra functionality) for gui_dashboardHD.py
from http import client # for handling HTTP client functionality if needed for future extensions such as REST API integration
import json # for handling JSON data in MQTT messages
from collections import deque # for storing recent sensor data for graphing
from datetime import datetime # for timestamping log messages and graph data points
import tkinter as tk # for creating the GUI dashboard
from tkinter import messagebox # for popup alarms

import paho.mqtt.client as mqtt # for MQTT communication between publisher and subscriber

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg # for embedding Matplotlib graphs in Tkinter
from matplotlib.figure import Figure # for creating Matplotlib figures for live graphing

# MQTT broker configuration
broker = "localhost" # use 192.168.12.100 as local broker IP
port = 1883

# student_id and machine_id are used to construct MQTT topics for both publisher and subscriber
student_id = "102781776"
machine_id = "machine01"

# MQTT topics
sensor_topic = f"public/102781776/machine01/sensors"
prediction_topic = f"public/102781776/machine01/prediction"
command_topic = f"public/102781776/machine01/command"
ack_topic = f"public/102781776/machine01/ack"
reset_topic = f"public/102781776/machine01/reset"
publisher_status_topic = f"{student_id}/status/user1"
subscriber_status_topic = f"{student_id}/status/user2"

# GUI Colours
BG = "#0f172a"
PANEL = "#1e293b"
TEXT = "#e5e7eb"
MUTED = "#94a3b8"
GREEN = "#22c55e"
YELLOW = "#facc15"
RED = "#ef4444"
BLUE = "#38bdf8"
PURPLE = "#a855f7"

# Threshold values for machine state analysis (WARNING and CRITICAL states)
WARNING_TEMP = 75.0
CRITICAL_TEMP = 85.0
WARNING_VIBRATION = 4.5
CRITICAL_VIBRATION = 6.0
CRITICAL_LIMIT = 1

# main dashboard class for Machine Predictive Maintenance Dashboard
class PredictiveMaintenanceDashboard:
    # initializes GUI window, variables, widgets and MQTT connection
    def __init__(self, root):
        self.root = root
        self.root.title("Predictive Maintenance MQTT Dashboard - HD")
        self.root.geometry("1250x780")
        self.root.configure(bg=BG)

        self.temperature_data = deque(maxlen=30)
        self.vibration_data = deque(maxlen=30)
        self.time_data = deque(maxlen=30)

        self.current_temperature = 0.0
        self.current_vibration = 0.0
        self.machine_state = "WAITING"
        self.cooling_state = "OFF"
        self.maintenance_counter = 0
        self.maintenance_required = False
        self.alarm_acknowledged = False
        self.last_popup_state = None

        self.create_widgets()
        self.setup_mqtt()

    # GUI Layout and Widget Creation with self as an argument to allow access to instance variables and 
    # methods for updating the dashboard based on MQTT messages and user interactionss
    def create_widgets(self):
        title = tk.Label(
            self.root,
            text="Machine Predictive Maintenance Dashboard",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 20, "bold")
        )
        title.pack(pady=10)
        # top frame for displaying current sensor values, machine state, cooling status, and critical maintenance counter
        top_frame = tk.Frame(self.root, bg=BG)
        top_frame.pack(fill="x", padx=15)
        # creates individual cards for temperature, vibration, machine state, auto-cooling status, 
        # and critical maintenance count with appropriate labels and styling
        self.temp_card = self.create_card(top_frame, "Temperature", "--- °C", 0)
        self.vib_card = self.create_card(top_frame, "Vibration", "--- mm/s", 1)
        self.state_card = self.create_card(top_frame, "Machine State", "WAITING", 2)
        self.cooling_card = self.create_card(top_frame, "Auto-Cooling", "OFF", 3)
        self.counter_card = self.create_card(top_frame, "Critical Maintenance Count", "0 / 1", 4)

        # middle frame for displaying live graphs of temperature and vibration data over time
        graph_frame = tk.Frame(self.root, bg=BG)
        graph_frame.pack(fill="both", expand=True, padx=15, pady=10)
        self.create_temperature_graph(graph_frame)
        self.create_vibration_graph(graph_frame)

        # bottom frame for CLI/event log and quick action buttons for emergency stop and maintenance reset
        # allowing the technician to interact with the machine and monitor events in real-time
        bottom_frame = tk.Frame(self.root, bg=BG)
        bottom_frame.pack(fill="both", expand=True, padx=15, pady=5)
        log_panel = tk.Frame(bottom_frame, bg=PANEL)
        log_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # CLI / Event log text label
        tk.Label(
            log_panel,
            text="CLI / Event Log",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", padx=10, pady=5)

        # text box for logging events with different colors for normal updates, warnings, critical alerts, 
        # maintenance notices, and informational messages
        self.log_box = tk.Text(
            log_panel,
            bg="#020617",
            fg=GREEN,
            insertbackground=TEXT,
            font=("Consolas", 10),
            height=10
        )
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)

        # button panel on the right side of the bottom frame for quick actions
        button_panel = tk.Frame(bottom_frame, bg=PANEL, width=280)
        button_panel.pack(side="right", fill="y")
        tk.Label(
            button_panel,
            text="Quick Actions",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 12, "bold")
        ).pack(pady=10)

        # emergency stop button layout
        emergency_button = tk.Button(
            button_panel,
            text="EMERGENCY STOP",
            bg=RED,
            fg="white",
            font=("Segoe UI", 12, "bold"),
            height=2,
            command=self.emergency_stop
        )
        emergency_button.pack(fill="x", padx=15, pady=10)

        # maintenance reset button layout
        reset_button = tk.Button(
            button_panel,
            text="RESET MAINTENANCE STATE",
            bg=BLUE,
            fg="white",
            font=("Segoe UI", 12, "bold"),
            height=2,
            command=self.reset_maintenance_state
        )
        reset_button.pack(fill="x", padx=15, pady=10)

    # creates a reusable dashboard card for displaying live values
    def create_card(self, parent, title, value, column):
        frame = tk.Frame(parent, bg=PANEL, padx=15, pady=10)
        frame.grid(row=0, column=column, padx=6, sticky="nsew")
        parent.grid_columnconfigure(column, weight=1)

        label = tk.Label(
            frame,
            text=title,
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 10)
        )
        label.pack(anchor="w")

        value_label = tk.Label(
            frame,
            text=value,
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 16, "bold")
        )
        value_label.pack(anchor="w", pady=8)

        return value_label

    # creates the live temperature graph using Matplotlib embedded in Tkinter
    def create_temperature_graph(self, parent):
        frame = tk.Frame(parent, bg=PANEL)
        frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        tk.Label(
            frame,
            text="Live Temperature Graph",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", padx=10, pady=5)

        self.temp_fig = Figure(figsize=(5.5, 3), dpi=100)
        self.temp_fig.patch.set_facecolor(PANEL)

        self.temp_ax = self.temp_fig.add_subplot(111)
        self.temp_ax.set_facecolor(BG)

        self.temp_ax.set_title("Temperature", color=TEXT)
        self.temp_ax.set_xlabel("Time", color=TEXT)
        self.temp_ax.set_ylabel("°C", color=TEXT)
        self.temp_ax.tick_params(colors=TEXT)

        self.temp_canvas = FigureCanvasTkAgg(self.temp_fig, master=frame)
        self.temp_canvas.get_tk_widget().pack(fill="both", expand=True)

    # creates the live vibration graph using Matplotlib embedded in Tkinter
    def create_vibration_graph(self, parent):
        frame = tk.Frame(parent, bg=PANEL)
        frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

        tk.Label(
            frame,
            text="Live Vibration Graph",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", padx=10, pady=5)

        self.vib_fig = Figure(figsize=(5.5, 3), dpi=100)
        self.vib_fig.patch.set_facecolor(PANEL)

        self.vib_ax = self.vib_fig.add_subplot(111)
        self.vib_ax.set_facecolor(BG)

        self.vib_ax.set_title("Vibration", color=TEXT)
        self.vib_ax.set_xlabel("Time", color=TEXT)
        self.vib_ax.set_ylabel("mm/s", color=TEXT)
        self.vib_ax.tick_params(colors=TEXT)

        self.vib_canvas = FigureCanvasTkAgg(self.vib_fig, master=frame)
        self.vib_canvas.get_tk_widget().pack(fill="both", expand=True)

    # sets up MQTT client, starts MQTT background loop,
    # defines callback functions for connection and message handling
    def setup_mqtt(self):
        self.client = mqtt.Client()

        username = "102781776"
        password = "102781776"

        self.client.username_pw_set(username, password)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.client.connect(broker, port, 60)
        self.client.loop_start()

    # runs when GUI successfully connects to the MQTT broker
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.log("Connected to broker at localhost:1883")

            client.subscribe(sensor_topic)
            client.subscribe(prediction_topic)
            client.subscribe(command_topic)
            client.subscribe(publisher_status_topic)
            client.subscribe(subscriber_status_topic)

            self.log(f"Subscribed to {sensor_topic}")
            self.log(f"Subscribed to {prediction_topic}")
            self.log(f"Subscribed to {command_topic}")
            self.log(f"Subscribed to {publisher_status_topic}")
            self.log(f"Subscribed to {subscriber_status_topic}")

        else:
            self.log(f"MQTT connection failed. Code: {rc}")

    # processes incoming MQTT messages and routes them to appropriate handlers based on the topic
    def on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode())
        except Exception:
            self.log(f"Invalid JSON received on {message.topic}")
            return
        
        if message.topic == sensor_topic:
            self.handle_sensor_data(payload)

        elif message.topic == prediction_topic:
            self.handle_prediction(payload)

        elif message.topic == command_topic:
            self.handle_command(payload)

        elif message.topic in [publisher_status_topic, subscriber_status_topic]:
            self.log(f"Status update: {payload}")

    # processes incoming sensor readings and updates the dashboard values, graphs, 
    # and logs accordingly while also checking machine state to prevent updates when stopped or maintenance required
    def handle_sensor_data(self, payload):
        if self.machine_state in ["STOPPED", "MAINTENANCE_REQUIRED"]:
            return
        temperature = float(payload.get("temperature_c", 0))
        vibration = float(payload.get("vibration_mm_s", 0))

        self.current_temperature = temperature
        self.current_vibration = vibration

        self.temperature_data.append(temperature)
        self.vibration_data.append(vibration)
        self.time_data.append(datetime.now().strftime("%H:%M:%S"))

        self.temp_card.config(text=f"{temperature:.2f} °C")
        self.vib_card.config(text=f"{vibration:.2f} mm/s")

        self.update_graphs()
        self.log(f"Sensor update: temperature={temperature:.2f}C vibration={vibration:.2f}mm/s")

    # processes prediction results and updates the machine state, cooling status, maintenance counter, graphs
    # logs accordingly while also checking machine state to prevent updates when stopped or maintenance required
    def handle_prediction(self, payload):
        if self.machine_state in ["STOPPED", "MAINTENANCE_REQUIRED"]:
            return

        condition = payload.get("condition", "UNKNOWN")
        action = payload.get("recommended_action", "NONE")
        reason = payload.get("reason", "No reason provided")

        self.machine_state = condition
        self.state_card.config(text=condition)

        if condition == "NORMAL":
            self.state_card.config(fg=GREEN)
            self.log(f"Prediction: NORMAL action={action}", "normal")

        elif condition == "WARNING":
            self.state_card.config(text="WARNING", fg=YELLOW)

            self.cooling_state = "ON"
            self.cooling_card.config(text="ON", fg=BLUE)

            self.log(f"Prediction: WARNING action={action}", "warning")
            self.raise_alarm("WARNING", reason)

        elif condition == "CRITICAL":
            self.state_card.config(text="CRITICAL", fg=RED)

            self.cooling_state = "ON"
            self.cooling_card.config(text="ON", fg=BLUE)

            self.log(f"Prediction: CRITICAL action={action}", "critical")
            self.raise_alarm("CRITICAL", reason)

    # processes incoming commands such as emergency stop and maintenance required
    def handle_command(self, payload):
        command = payload.get("command", "UNKNOWN_COMMAND")
        reason = payload.get("reason", "")

        self.log(f"Command received: {command} reason= {reason}")
        

        if command == "ENABLE_COOLING_AND_SCHEDULE_MAINTENANCE":
            self.cooling_state = "ON"
            self.cooling_card.config(text="ON", fg=BLUE)

        elif command == "STOP_MACHINE_AND_INSPECT":
            self.machine_state = "STOPPED"
            self.cooling_state = "OFF"

            self.state_card.config(text="STOPPED", fg=RED)
            self.cooling_card.config(text="OFF", fg=TEXT)
            self.raise_alarm("CRITICAL", "Emergency stop command received")

        elif command == "MAINTENANCE_REQUIRED":
            self.maintenance_required = True
            self.machine_state = "MAINTENANCE_REQUIRED"
            self.state_card.config(text="MAINTENANCE REQUIRED", fg=PURPLE)
            self.raise_alarm("MAINTENANCE_REQUIRED", "Maintenance required after repeated warnings")

    # handles warning reminders, critical alerts, maintenance counting and popup alarms
    def raise_alarm(self, alarm_type, reason):
        if self.machine_state in ["STOPPED", "MAINTENANCE_REQUIRED"]:
            return

        if alarm_type == "WARNING":
            self.log(
                f"WARNING reminder: {reason}. Maintenance may be needed soon.",
                "warning"
            )
            return

        if alarm_type == "CRITICAL":
            self.maintenance_counter += 1
            self.counter_card.config(text=f"{self.maintenance_counter} / {CRITICAL_LIMIT}")

            self.log(
                f"CRITICAL threshold exceeded. Counter={self.maintenance_counter}",
                "critical"
            )

            if self.maintenance_counter >= CRITICAL_LIMIT:
                self.maintenance_required = True
                self.machine_state = "MAINTENANCE_REQUIRED"

                self.state_card.config(text="MAINTENANCE REQUIRED", fg=PURPLE)

                self.publish_command(
                    "MAINTENANCE_REQUIRED",
                    "Critical threshold exceeded"
                )

                messagebox.showwarning(
                    "MAINTENANCE REQUIRED",
                    "Critical machine condition detected.\n\nImmediate maintenance is now required."
                )
    # emergency stop button stops the machine and publishes stop command
    def emergency_stop(self):
        self.machine_state = "STOPPED"
        self.cooling_state = "OFF"

        self.state_card.config(text="STOPPED", fg=RED)
        self.cooling_card.config(text="OFF", fg=TEXT)

        # Force Tkinter to redraw immediately
        self.root.update_idletasks()

        self.publish_command(
            "STOP_MACHINE_AND_INSPECT",
            "Emergency stop button pressed by technician1"
        )

        self.log("Emergency stop pressed by technician1", "critical")

    # resets maintenance state and resumes machine operation
    def reset_maintenance_state(self):
        self.maintenance_counter = 0
        self.maintenance_required = False
        self.alarm_acknowledged = True
        self.last_popup_state = None

        self.machine_state = "NORMAL"
        self.cooling_state = "OFF"

        self.counter_card.config(text="0 / 1")
        self.state_card.config(text="NORMAL", fg=GREEN)
        self.cooling_card.config(text="OFF", fg=TEXT)

        reset_payload = {
            "machine_id": machine_id,
            "reset_maintenance_state": True,
            "operator": "technician1"
        }

        ack_payload = {
            "machine_id": machine_id,
            "alarm_acknowledged": True,
            "operator": "technician1"
        }

        self.client.publish(reset_topic, json.dumps(reset_payload, indent=4))
        self.client.publish(ack_topic, json.dumps(ack_payload, indent=4))

        self.log("Maintenance state reset by technician1")
        self.log("Alarm Acknowledged by technician1")

        messagebox.showinfo(
            "Reset Complete",
            "Maintenance state has been reset.\nAlarm acknowledged by technician1."
        )

    # publishes MQTT commands to the command topic
    def publish_command(self, command, reason):
        payload = {
            "machine_id": machine_id,
            "command": command,
            "issued_by": "gui_dashboardHD",
            "reason": reason
        }

        self.client.publish(command_topic, json.dumps(payload, indent=4))
        self.log(f"Published command: {command}")

    # updates live temperature and vibration graphs with real-time sensor data
    def update_graphs(self):
        x_values = list(range(len(self.time_data)))
        time_labels = list(self.time_data)

        self.temp_ax.clear()
        self.temp_ax.plot(x_values, list(self.temperature_data), marker="o")
        self.temp_ax.axhline(WARNING_TEMP, linestyle="--", color=YELLOW)
        self.temp_ax.axhline(CRITICAL_TEMP, linestyle="--", color=RED)

        self.temp_ax.set_xlim(-1, len(x_values))
        self.temp_ax.set_xticks(x_values[::5])
        self.temp_ax.set_xticklabels(time_labels[::5], rotation=30, ha="right")

        self.temp_ax.set_title("Temperature", color=TEXT)
        self.temp_ax.set_xlabel("Time", color=TEXT)
        self.temp_ax.set_ylabel("°C", color=TEXT)
        # self.temp_ax.tick_params(colors=TEXT)
        # self.temp_ax.set_facecolor(BG)
        self.temp_fig.subplots_adjust(bottom=0.30)
        self.temp_canvas.draw()

        self.vib_ax.clear()
        self.vib_ax.plot(x_values, list(self.vibration_data), marker="o")
        self.vib_ax.axhline(WARNING_VIBRATION, linestyle="--", color=YELLOW)
        self.vib_ax.axhline(CRITICAL_VIBRATION, linestyle="--", color=RED)

        self.vib_ax.set_xlim(-1, len(x_values))
        self.vib_ax.set_xticks(x_values[::5])
        self.vib_ax.set_xticklabels(list(self.time_data)[::5], rotation=30, ha="right")
        
        self.vib_ax.set_title("Vibration", color=TEXT)
        self.vib_ax.set_xlabel("Time", color=TEXT)
        self.vib_ax.set_ylabel("mm/s", color=TEXT)
        self.vib_fig.subplots_adjust(bottom=0.30)
        self.vib_canvas.draw()

    # displays colour-coded messages in CLI/event log
    def log(self, message, level="normal"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        self.log_box.tag_config("normal", foreground=GREEN)
        self.log_box.tag_config("warning", foreground=YELLOW)
        self.log_box.tag_config("critical", foreground=RED)
        self.log_box.tag_config("maintenance", foreground=PURPLE)
        self.log_box.tag_config("info", foreground=BLUE)

        self.log_box.insert(tk.END, log_message, level)
        self.log_box.see(tk.END)

        print(log_message, end="")

# starts the Tkinter GUI dashboard application
if __name__ == "__main__":
    root = tk.Tk()
    app = PredictiveMaintenanceDashboard(root)
    root.mainloop()