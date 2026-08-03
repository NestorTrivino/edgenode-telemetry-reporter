# EdgeNode Telemetry Reporter

Prototype implementation of an embedded Linux telemetry reporter written in Python.

The application reads telemetry data from a text file, validates sensor values, buffers messages locally during network outages, and publishes telemetry data through MQTT.

## Features

- Reads telemetry data from a text file
- Validates sensor data format and required fields
- Local persistent message queue
- MQTT publishing
- Automatic MQTT reconnect handling
- Graceful shutdown handling
- Logging support
- Cython parser support (planned)

## Project Structure

```
edgenode-telemetry-reporter/
│
├── edgenode-telemetry-reporter.py   # Main application (configuration, parser, queue, MQTT, logging, shutdown)
├── reporter.conf                    # Configuration values
├── telemetry_input.txt              # Sample telemetry input file
├── requirements.txt                 # Python dependencies
├── README.md                        # Documentation
├── .gitignore                       # Ignored generated files
└── buffer.txt                       # Temporary persistent message queue storage
```

## Requirements

- Python 3.11+
- Mosquitto MQTT Broker

### Create Python Virtual Environment

```bash
python3 -m venv venv
```

### Activate Virtual Environment

Linux:

```bash
source venv/bin/activate
```

Windows:

```bash
venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Running the Application

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

The telemetry input file is:

```
telemetry_input.txt
```

A valid telemetry message should follow this format:

```
TEMP=23.6,HUM=61.1,VOLT=12.3
```

## Invalid Input Examples

### Invalid Numeric Format

Input:

```
TEMP=bad,HUM=60.9,VOLT=12.2
```

Expected result:

```
Invalid numeric value for TEMP: 'bad'
```

---

### Missing Required Field

Input:

```
TEMP=23.7,VOLT=12.1
```

Expected result:

```
Missing field: HUM
```

---

### Unknown Extra Fields

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

## Successful Telemetry Publishing

The application produces two outputs:

1. MQTT broker telemetry messages
2. Application console logs

## MQTT Broker Output

Example:

```bash
lostransper@Terminestor:/mnt/c/Users/lostr$ mosquitto_sub -h localhost -t "company/edgenode/#" -v
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
(venv) lostransper@Terminestor:~/Interview/edgenode-telemetry-reporter$ ./edgenode-telemetry-reporter.py

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

# Negative Test Scenarios

## Invalid Numeric Values

Input:

```
TEMP=bad,HUM=60.9,VOLT=12.2
```

Output:

```
Invalid numeric value for TEMP: 'bad'
```

---

## Missing Fields

Input:

```
TEMP=23.7,VOLT=12.1
```

Output:

```
Missing field: HUM
```

---

## Extra Unknown Fields

Input:

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

## Incorrect Format Lines

Input:

```
incorrectformatline
```

Output:

```
ERROR: incorrectformatline
Malformed telemetry line
```

---

# Network Outage Test

This test validates the local buffering mechanism when MQTT connectivity is unavailable.

## Stop MQTT Broker

If Mosquitto is running on the same machine:

```bash
sudo systemctl stop mosquitto
```

> Note: The password prompt may require time before the MQTT connection is completely stopped.

Alternatively, disconnect the network connection if the MQTT broker is running on another machine.

## Test Procedure

1. Add a large number of telemetry messages to:

```
telemetry_input.txt
```

2. Start the reporter:

```bash
./edgenode-telemetry-reporter.py
```

3. Stop the MQTT broker.

After several seconds, the application should detect the connection failure and start buffering messages.

Example:

```text
WARNING: Buffer full (10 messages). Dropping message 1168.

Waiting for connection to flush 10 buffered message(s)... (Ctrl+C to exit)
```

The application will:

- Continue running while MQTT is unavailable
- Store messages locally in the buffer
- Drop new messages when the buffer reaches the maximum size
- Resume publishing after MQTT connectivity is restored

## Restore MQTT Connection

Start Mosquitto again:

```bash
sudo systemctl start mosquitto
```

After reconnection, the application should flush buffered messages:

```text
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

Due to time constraints, the following features were not implemented:

- SQLite database storage
- External C library integration

The original plan was to implement a C-based parser function and expose it to Python using Cython to improve parsing performance.

---

# Known Limitations

Current limitations:

- The local buffer uses a text file instead of a database.
- The MQTT publishing flow reconnects and flushes messages sequentially.
- The Cython parser implementation is not included yet.
- No automated unit test framework is currently included.

Future improvements:

- Replace file-based buffering with SQLite.
- Add automated tests using `pytest`.
- Implement C parser integration using Cython.
- Add telemetry schema version management.