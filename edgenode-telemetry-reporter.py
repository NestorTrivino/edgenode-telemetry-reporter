#!/usr/bin/env python3

from datetime import datetime, timezone
import json
import os
import signal
import time
import paho.mqtt.client as mqtt

#I would normally expect this value to come from the sensor as part of the telemetry data, so I will hardcode DEVICE_ID here for now.
DEVICE_ID = "edgenode-test-001"
# MQTT broker configuration
MQTT_HOST = "localhost"
MQTT_PORT = 1883
# MQTT telemetry topic
TOPIC = f"company/edgenode/{DEVICE_ID}/telemetry"
# Local buffer (persistent queue) configuration
BUFFER_FILE = "buffer.txt"
QUEUE_MAX_SIZE = 10 # Maximum number of messages stored in the buffer. New messages are rejected when the buffer is full.

# Tracks whether the MQTT client currently has a live connection to the
# broker. Updated by the on_connect/on_disconnect callbacks, which run
# on paho's background network thread.
mqtt_connected = False

# Set by the SIGINT handler. Checked throughout the main loop so a
# Ctrl+C finishes the current step cleanly (closes files, disconnects
# the client) instead of dying mid-write.
shutdown_requested = False


def request_shutdown(signum, frame):
    # This function handles SIGINT (Ctrl+C)
    # First Ctrl+C asks the program to wind down after the current step
    # A second Ctrl+C forces an immediate exit, in case something is stuck
    global shutdown_requested

    if shutdown_requested:
        print("\nForced exit.")
        raise SystemExit(1)

    print("\nShutdown requested, finishing up...")
    shutdown_requested = True


def on_connect(client, userdata, flags, reason_code, properties=None):
    # This function runs whenever the client (re)connects to the broker
    # It flips the mqtt_connected flag so the main loop knows it can
    # attempt to flush the local buffer again
    global mqtt_connected

    if reason_code == 0:
        print("Connected to MQTT Broker")
        mqtt_connected = True
    else:
        print(f"Connection failed: {reason_code}")
        mqtt_connected = False


def on_disconnect(client, userdata, flags, reason_code, properties=None):
    # This function runs whenever the client loses its connection
    # It flips mqtt_connected off so the main loop stops trying to
    # publish and buffers messages locally instead
    global mqtt_connected

    print(f"Disconnected from MQTT Broker (reason: {reason_code})")
    mqtt_connected = False


def connect_mqtt():
    # This function creates the MQTT client and starts connecting
    # It uses connect_async + loop_start so the program never blocks
    # waiting for the broker to be reachable
    # The background loop thread automatically retries with backoff
    # (per reconnect_delay_set), both for the initial connection and
    # for any later disconnect - this is what lets buffered messages
    # get flushed once the broker comes back
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    try:
        client.connect_async(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()
        return client

    except Exception as e:
        print(f"Could not start MQTT client: {e}")
        return None


def load_buffer():
    # This function reads buffer.txt and returns its lines
    # Each line is a raw JSON string representing one queued message
    # An empty list is returned if the buffer file does not exist yet
    if not os.path.exists(BUFFER_FILE):
        return []

    with open(BUFFER_FILE) as file:
        return [line.strip() for line in file if line.strip()]


def enqueue_message(message):
    # This function appends a message to buffer.txt
    # The buffer holds at most QUEUE_MAX_SIZE messages
    # When the buffer is full, the new message is dropped and not stored
    lines = load_buffer()

    if len(lines) >= QUEUE_MAX_SIZE:
        print(f"WARNING: Buffer full ({QUEUE_MAX_SIZE} messages). Dropping message {message['seq']}.")
        return False

    with open(BUFFER_FILE, "a") as file:
        file.write(json.dumps(message) + "\n")

    print(f"Buffered message {message['seq']} ({len(lines) + 1}/{QUEUE_MAX_SIZE})")
    return True


def dequeue_message(message):
    # This function removes one message from buffer.txt
    # It is called after the message has been successfully published
    # Messages are matched by their sequence number
    lines = load_buffer()

    remaining = [line for line in lines if json.loads(line)["seq"] != message["seq"]]

    with open(BUFFER_FILE, "w") as file:
        for line in remaining:
            file.write(line + "\n")


def publish_message(client, message):
    # This function publishes telemetry data to the MQTT topic
    # It converts the message dictionary into JSON format
    # It checks if the message was successfully published
    payload = json.dumps(message)

    result = client.publish(TOPIC, payload)

    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print(f"Published message {message['seq']}")
        return True
    else:
        print("Publish failed")
        return False


def flush_buffer(client):
    # This function attempts to publish everything currently sitting in
    # the local buffer, oldest first, so message order is preserved
    # It stops at the first failed publish (e.g. the connection dropped
    # again mid-flush) and leaves the rest queued for the next attempt
    lines = load_buffer()

    if not lines:
        return

    print(f"Flushing {len(lines)} buffered message(s)...")

    for line in lines:
        if shutdown_requested or not mqtt_connected:
            break

        message = json.loads(line)

        if publish_message(client, message):
            dequeue_message(message)
        else:
            break


def parse_line(line):

    # This function parses a telemetry input line
    # It separates the sensor values into key-value pairs
    # It validates required fields and converts values to float format

    data = {}

    # Required telemetry fields
    required = ["TEMP", "HUM", "VOLT"]
    known_fields = set(required)

    try:
        parts = line.split(",")

        # Extract key-value pairs from input data
        for part in parts:
            part = part.strip()

            # Tolerate stray/empty segments (e.g. trailing commas)
            if not part:
                continue

            # Reject segments that aren't in key=value format
            if "=" not in part:
                raise ValueError(f"Malformed field (expected key=value): '{part}'")

            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip()

            if not key:
                raise ValueError(f"Malformed field (missing key): '{part}'")

            # Ignore extra/unknown fields instead of failing the whole line
            if key not in known_fields:
                print(f"WARNING: Unknown field '{key}' ignored in line: {line}")
                continue

            data[key] = value

        # Verify all required fields are present
        for field in required:
            if field not in data:
                raise ValueError(f"Missing field: {field}")

        # Convert sensor values from string to float, one at a time so
        # we can report exactly which field has an invalid numeric value
        for field in required:
            try:
                data[field] = float(data[field])
            except ValueError:
                raise ValueError(f"Invalid numeric value for {field}: '{data[field]}'")

        return data

    except Exception as e:
        print(f"ERROR: {line}")
        print(e)

        return None


def create_telemetry_message(data, seq):

    # This function creates the telemetry message structure
    # It adds device information, timestamp, and sequence number
    # It formats sensor data according to the telemetry schema

    return {
        "deviceId": DEVICE_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "seq": seq,
        "schema": "telemetry.v1",
        "data": {
            "temperature": data["TEMP"],
            "humidity": data["HUM"],
            "voltage": data["VOLT"]
        }
    }


def main():

    # This function runs the telemetry reporter workflow
    # It reads telemetry data from the input file
    # It validates, creates, and publishes telemetry messages
    # It flushes any buffered messages once the connection is back
    # It shuts down cleanly on Ctrl+C

    global shutdown_requested

    signal.signal(signal.SIGINT, request_shutdown)

    client = connect_mqtt()

    seq = 1

    try:
        # Open telemetry input file
        with open("telemetry_input.txt") as file:

            for line in file:

                if shutdown_requested:
                    print("Stopping before next line (shutdown requested).")
                    break

                # Remove spaces and newline characters
                line = line.strip()

                # Ignore empty lines
                if not line:
                    continue

                telemetry = parse_line(line)

                # Skip invalid telemetry data
                if telemetry is None:
                    continue

                message = create_telemetry_message(telemetry, seq)

                # Print generated telemetry message
                print(json.dumps(message, indent=4))

                # If the connection is back, drain anything still waiting
                # in the buffer before dealing with this new message, so
                # older messages go out first and order is preserved
                if client and mqtt_connected:
                    flush_buffer(client)

                # Store the message in the local buffer before attempting to publish
                buffered = enqueue_message(message)

                # Publish telemetry if the MQTT connection is currently up
                if buffered and client and mqtt_connected:
                    published = publish_message(client, message)

                    # Remove the message from the buffer only once it has
                    # been successfully published to the broker
                    if published:
                        dequeue_message(message)

                # Increment message sequence number
                seq += 1

        # The input file is exhausted. If messages are still sitting in
        # the buffer, keep watching the connection and flush them as
        # soon as it comes back, until the buffer is empty or the user
        # interrupts with Ctrl+C.
        while client and not shutdown_requested:
            remaining = load_buffer()

            if not remaining:
                break

            if mqtt_connected:
                flush_buffer(client)
                continue

            print(f"Waiting for connection to flush {len(remaining)} buffered message(s)... (Ctrl+C to exit)")
            time.sleep(2)

    except FileNotFoundError:
        print("telemetry_input.txt not found.")

    finally:
        # Always stop the MQTT loop and disconnect cleanly, whether we
        # got here normally, via Ctrl+C, or via an unexpected error
        if client:
            print("Disconnecting from MQTT Broker...")
            client.loop_stop()
            client.disconnect()

        print("Shutdown complete.")


# Execute main function when script is started
if __name__ == "__main__":
    main()