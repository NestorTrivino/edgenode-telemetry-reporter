# EdgeNode Telemetry Reporter

Prototype implementation of an embedded Linux telemetry reporter written in Python.

## Features

- Reads telemetry data from a text file
- Validates sensor data
- Local persistent queue buffer
- MQTT publishing
- Automatic MQTT reconnect
- Graceful shutdown handling
- Logging
- Cython parser (planned)

---

## Project Structure

```
edgenode-telemetry-reporter/
├── main.py                    # Entire application (configuration, parser, queue, MQTT, logging, shutdown)
├── reporter.conf              # Configuration values
├── telemetry_input.txt        # Sample telemetry input file
├── requirements.txt           # Python dependencies
├── README.md                  # Build and usage instructions
├── .gitignore                 # Ignore generated files
└── buffer.txt                 # Temporary persistent queue storage
```

---

## Requirements

- Python 3.11+
- Mosquitto MQTT Broker

### Create Python virtual environment

```bash
python3 -m venv venv
```

### Activate virtual environment

Linux:

```bash
source venv/bin/activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

---

# Running the Application

Make the script executable:

```bash
chmod +x edgenode-telemetry-reporter.py
```

Run the application:

```bash
./edgenode-telemetry-reporter.py
```

---

# Monitoring MQTT Messages

To subscribe to all published telemetry messages:

```bash
mosquitto_sub -h localhost -t "company/edgenode/#" -v
```

---

# Input Example

The telemetry input source is the `telemetry_input.txt` file.

A valid telemetry message should have the following format:

```
TEMP=23.6,HUM=61.1,VOLT=12.3
```

## Invalid Input Examples

### Invalid numeric value

Input:

```
TEMP=bad,HUM=60.9,VOLT=12.2
```

Expected result:

```
Invalid numeric value for TEMP: 'bad'
```

---

### Missing required field

Input:

```
TEMP=23.7,VOLT=12.1
```

Expected result:

```
Missing field: HUM
```

---

### Unknown fields

Input:

```
TEMP=23.7,VOLT=12.1,TEST=XX,VOX=12.X
```

Expected result:

```
WARNING: Unknown field 'TEST' ignored in line: TEMP=23.7,VOLT=12.1,TEST=XX,VOX=12.X
WARNING: Unknown field 'VOX' ignored in line: TEMP=23.7,VOLT=12.1,TEST=XX,VOX=12.X
```

---

# Output Examples

## Positive Scenario

The application generates two outputs:

1. MQTT broker messages
2. Application console logs

---

## MQTT Broker Output

Example:

```bash
mosquitto_sub -h localhost -t "company/edgenode/#" -v
```

Output:

```json
company/edgenode/edgenode-test-001/telemetry {
    "deviceId": "edgenode-test-001",
    "timestamp": "2026-08-03T22:35:42.592572+00:00",
    "seq": 1,
    "schema": "telemetry.v1",
    "data": {
        "temperature": 23.5,
        "humidity": 61.2,
        "voltage": 12.4
    }
}
```

---

## Application Console Output

Example:

```text
{
    "deviceId": "edgenode-test-001",
    "timestamp": "2026-08-03T22:35:42.592572+00:00",
    "seq": 1,
    "schema": "telemetry.v1",
    "data": {
        "temperature": 23.5,
        "humidity": 61.2,
        "voltage": 12.4
    }
}

Buffered message 1 (1/10)

Waiting for connection to flush 1 buffered message(s)... (Ctrl+C to exit)

Connected to MQTT Broker

Flushing 1 buffered message(s)...

Published message 1

Disconnecting from MQTT Broker...

Disconnected from MQTT Broker (reason: Normal disconnection)

Shutdown complete.
```

---

# Negative Scenarios

## Invalid Numeric Values

Example:

```
TEMP=bad,HUM=60.9,VOLT=12.2
```

Output:

```
Invalid numeric value for TEMP: 'bad'
```

---

## Missing Fields

Example:

```
TEMP=23.7,VOLT=12.1
```

Output:

```
Missing field: HUM
```

---

## Extra Unknown Fields

Example:

```
TEMP=23.7,VOLT=12.1,TEST=XX,VOX=12.X
```

Output:

```
WARNING: Unknown field 'TEST' ignored in line: TEMP=23.7,VOLT=12.1,TEST=XX,VOX=12.X
WARNING: Unknown field 'VOX' ignored in line: TEMP=23.7,VOLT=12.1,TEST=XX,VOX=12.X
```

---

## Empty Lines

Empty lines are ignored.

---

## Incorrect Format

Example:

```
incorrectformatline
```

Output:

```
ERROR: incorrectformatline
Malformed input line
```

---

# Testing Network Outage Behavior

The application can be tested during MQTT broker outages.

If Mosquitto is running on the same machine, stop the service:

```bash
sudo systemctl stop mosquitto
```

> Note: You need enough time to enter your password before the application continues sending messages.

Alternatively, disconnect the network cable if the MQTT broker is running on another machine.

---

## Test Procedure

1. Add a large number of telemetry messages to:

```
telemetry_input.txt
```

2. Start the application:

```bash
./edgenode-telemetry-reporter.py
```

3. Stop the MQTT broker.

After the buffer reaches its maximum size, the application should display:

```
WARNING: Buffer full (10 messages). Dropping message 1168.

Waiting for connection to flush 10 buffered message(s)... (Ctrl+C to exit)
```

The application will continue waiting until the MQTT connection is restored.

Incoming telemetry messages are ignored while the connection is unavailable if the buffer is already full.

---

## MQTT Recovery Example

After restarting Mosquitto:

```bash
sudo systemctl start mosquitto
```

The application reconnects and flushes buffered messages:

```
Connected to MQTT Broker

Flushing 10 buffered message(s)...

Published message 1
Published message 2
Published message 3
Published message 4
Published message 5
Published message 6
Published message 7
Published message 8
Published message 9
Published message 10

Disconnecting from MQTT Broker...

Disconnected from MQTT Broker (reason: Normal disconnection)

Shutdown complete.
```

---

# Design Decisions and Trade-offs

Due to limited implementation time, the following features were not completed:

- SQLite-based persistent storage
- Additional C library integration

The original plan was to use Cython to integrate a small C-based parser function for performance optimization.

---

# Known Limitations

- The current queue implementation uses a text file (`buffer.txt`) instead of a database.
- The Cython parser integration is not implemented yet.
- MQTT authentication is not currently configured.
- The application is a prototype and requires additional hardening before production deployment.