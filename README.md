# EdgeNode Telemetry Reporter

Prototype implementation of an embedded Linux telemetry reporter written in Python.

## Features

- Reads telemetry from text file
- Validates sensor data
- Local queue
- MQTT publishing
- Automatic reconnect
- Graceful shutdown
- Logging
- Cython parser

## Project Structure

edgenode-telemetry-reporter/
- main.py → Entire application (configuration, parser, queue, MQTT, logging, shutdown).
- reporter.conf → Configuration values.
- telemetry_input.txt → Sample input file.
- requirements.txt → Python dependencies.
- README.md → Build and usage instructions.
- .gitignore → Ignore generated files.
## Requirements

- Python 3.11+

- Mosquitto Broker

- pip install -r requirements.txt

## Running

- chmod +x edgenode-telemetry-reporter.py

- ./edgenode-telemetry-reporter.py

## Monitoring MQTT Messages
To subscribe to all published telemetry messages:
* mosquitto_sub -h localhost -t "company/edgenode/#" -v