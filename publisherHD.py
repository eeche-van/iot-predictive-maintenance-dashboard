"""
publisherHD.py

User 1 - Machine Telemetry Publisher

functions:
- generates simulated machine telemetry data
- publishes telemetry to private and public MQTT topics
- subscribes to prediction and command topics
- responds to maintenance lockout and reset events
"""

# python code for publisherHD.py (basic HD requirements in between lines 202 - 247 for User 1)
import json # for handling JSON data in MQTT messages
import random # for simulating sensor data with random variations
import time # for adding delays in the main loop to simulate real-time data publishing
import paho.mqtt.client as mqtt # for MQTT communication between publisher and subscriber

# MQTT broker configuration
broker = "localhost" # use 192.168.12.100 as local broker IP
port = 1883
# student_id and machine_id are used to construct MQTT topics for both publisher and subscriber
student_id = "102781776"
machine_id = "machine01"

# MQTT topics
private_topic = f"102781776/machine01/internal"
public_topic1 = f"public/102781776/machine01/sensors"
public_topic2 = f"public/102781776/machine01/prediction"
command_topic = f"public/102781776/machine01/command"
reset_topic = f"public/102781776/machine01/reset"
status_topic = f"102781776/status/user1" # for debugging purpose

# initial machine state variables
machine_running = True
maintenance_required = False
temperature = 65.0
vibration = 2.5

# on_connect callback function to handle connection events
# client: MQTT client instance
# userdata: user-defined data
# flags: contains response flags from the broker
# rc: connection result code
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("User 1 connected to MQTT broker")
        # OBJ 3: Subscribe to Topic 2 in the public channel and display generated messages
        # User 1 also subscribes to the command topic to receive any commands sent by User 2 based on the predictions.
        client.subscribe(public_topic2)
        client.subscribe(command_topic)
        client.subscribe(reset_topic)

        print("Subscribed to:", public_topic2)
        print("Subscribed to:", command_topic)
        print("Subscribed to:", reset_topic)

        client.publish(
            status_topic,
            json.dumps(
                {
                    "user": "User 1",
                    "status": "online",
                    "machine_running": machine_running
                },
                indent=4
            ),
            retain=True
        )
    else:
        print("Connection failed with code:", rc)

# on_message callback function to handle incoming messages
def on_message(client, userdata, message):
    # global variables used to modify machine state based on commands
    global machine_running
    global maintenance_required
    # decodes the incoming message payload from bytes to string
    payload_text = message.payload.decode()

    print("\nUser 1 received message")
    print("Topic:", message.topic)
    print("Payload:")
    print(payload_text)

    try:
        payload = json.loads(payload_text)
    except:
        print("Invalid JSON received")
        return
    # extra functionality: Automated command processing and machine state management
    # User 1 processes messages based on the topic they were received on and send payload responses accordingly
    if message.topic == command_topic:
        command = payload.get("command", "")
        # processes stop command to stop machine state and publish readings
        if command == "STOP_MACHINE_AND_INSPECT":
            machine_running = False
            print("\nEMERGENCY STOP command received.")
            print("Machine has stopped publishing sensor readings.")

            client.publish(
                status_topic,
                json.dumps(
                    {
                        "user": "User 1",
                        "status": "stopped",
                        "machine_running": machine_running
                    },
                    indent=4
                ),
                retain=True
            )
        # machine remains stopped until reset command received
        elif command == "MAINTENANCE_REQUIRED":
            machine_running = False
            maintenance_required = True
            print("\nMAINTENANCE REQUIRED command received.")
            print("Machine locked until maintenance reset.")

            client.publish(
                status_topic,
                json.dumps(
                    {
                        "user": "User 1",
                        "status": "maintenance_required",
                        "machine_running": machine_running
                    },
                    indent=4
                ),
                retain=True
            )
        # cooling is enabled automatically when WARNING threshold is reached
        elif command == "ENABLE_COOLING_AND_SCHEDULE_MAINTENANCE":
            print("\nCooling command received.")
            print("Cooling action performed automatically.")

            client.publish(
                status_topic,
                json.dumps(
                    {
                        "user": "User 1",
                        "status": "cooling_enabled",
                        "machine_running": machine_running
                    },
                    indent=4
                ),
                retain=True
            )
    # processes reset command to update machine state and publish status updates with json
    elif message.topic == reset_topic:
        reset_state = payload.get("reset_maintenance_state", False)

        if reset_state is True:
            machine_running = True
            maintenance_required = False

            print("\nRESET command received.")
            print("Machine operation resumed.")

            client.publish(
                status_topic,
                json.dumps(
                    {
                        "user": "User 1",
                        "status": "running_after_reset",
                        "machine_running": machine_running
                    },
                    indent=4
                ),
                retain=True
            )

# mqtt.Client instance is created to connect to the broker and handle MQTT communication
client = mqtt.Client()
username = "102781776"
password = "102781776"

client.username_pw_set(username, password)
# will_set is used to define a last will message that will be published if the client disconnects unexpectedly
client.will_set(
    status_topic,
    json.dumps(
        {
            "user": "User 1",
            "status": "offline unexpectedly",
            "machine_running": False
        },
        indent=4
    ),
    retain=True
)

# the on_connect and on_message callback functions are assigned to the client to handle connection and message events
client.on_connect = on_connect
client.on_message = on_message

# the 60 in connect is the keepalive interval in seconds
# defines how often the client will send a ping to the broker to keep the connection alive
client.connect(broker, port, 60)
client.loop_start()

# main loop to simulate sensor data publishing and handle incoming commands
try:
    while True:
        if not machine_running:
            print("Machine stopped or maintenance required. Waiting for reset command...")
            time.sleep(3)
            continue

        temperature += random.uniform(-1.5, 1.5)
        vibration += random.uniform(-0.3, 0.3)

        temperature = max(50, min(90, temperature))
        vibration = max(1, min(7, vibration))

        temperature = round(temperature, 2)
        vibration = round(vibration, 2)
    # OBJ 1: User 1 automatically generate and post messages to a topic in the private channel.
    # creates simulated internal machine diagnostics data
    # The payload produced here is later published to: 102781776/machine01/internal
        private_payload = {
            "student_id": student_id,
            "machine_id": machine_id,
            "motor_rpm": random.randint(1300, 1600),
            "bearing_temperature_c": temperature,
            "vibration_x_mm_s": vibration,
            "oil_level_percent": random.randint(40, 100),
            "runtime_hours": random.randint(800, 2500),
            "machine_running": machine_running,
            "maintenance_required": maintenance_required
        }
    # OBJ 2: User 1 automatically generate and post messages to <Topic 1> in a public channel.
    # extracts the public temperature and vibration data from the private machine payload.
    # This public payload is later published to: public/102781776/machine01/sensors
        public_payload = {
            "student_id": student_id,
            "machine_id": machine_id,
            "temperature_c": temperature,
            "vibration_mm_s": vibration,
            "machine_running": machine_running
        }

        client.publish(
            private_topic,
            json.dumps(private_payload, indent=4)
        )

        client.publish(
            public_topic1,
            json.dumps(public_payload, indent=4)
        )

        print("\nUser 1 published private data to:")
        print(private_topic)
        print(json.dumps(private_payload, indent=4))

        print("\nUser 1 published public sensor data to:")
        print(public_topic1)
        print(json.dumps(public_payload, indent=4))

        print("-" * 60)

        time.sleep(5)

# press ctrl +c to stop the publisher and publish an offline status update with json
except KeyboardInterrupt:
    print("\nUser 1 disconnecting...")
# User 1 publishes an offline status update to the status topic with a JSON payload indicating the machine is no longer running
    client.publish(
        status_topic,
        json.dumps(
            {
                "user": "User 1",
                "status": "offline",
                "machine_running": False
            },
            indent=4
        ),
        retain=True
    )
# stop the MQTT client loop and disconnect from the broker
    client.loop_stop()
    client.disconnect()