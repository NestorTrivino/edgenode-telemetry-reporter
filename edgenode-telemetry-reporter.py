#!/usr/bin/env python3

from datetime import datetime, timezone
import json
import paho.mqtt.client as mqtt


DEVICE_ID = "edgenode-test-001"
# MQTT broker configuration
MQTT_HOST = "localhost"
MQTT_PORT = 1883
# MQTT telemetry topic
TOPIC = f"company/edgenode/{DEVICE_ID}/telemetry"


def connect_mqtt():
    # This function connects to the MQTT broker
    # It starts the MQTT loop in the background
    # It returns the client instance if successful
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()
        print("Connected to MQTT Broker")
        return client

    except Exception as e:
        print(f"Could not connect to MQTT Broker: {e}")
        return None


def publish_message(client, message):
    # This function publishes telemetry data to the MQTT topic
    # It converts the message dictionary into JSON format
    # It checks if the message was successfully published
    payload = json.dumps(message)

    result = client.publish(TOPIC, payload)

    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print(f"Published message {message['seq']}")
    else:
        print("Publish failed")


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

    client = connect_mqtt()

    seq = 1

    # Open telemetry input file
    with open("telemetry_input.txt") as file:

        for line in file:

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

            # Publish telemetry if MQTT connection is available
            if client:
                publish_message(client, message)

            # Increment message sequence number
            seq += 1

    # Stop MQTT loop and close connection
    if client:
        client.loop_stop()
        client.disconnect()


# Execute main function when script is started
if __name__ == "__main__":
    main()