import config
import json
import mido
import mido.backends.rtmidi
import rtmidi
import time
from redis import Redis


redis = Redis(host="0.0.0.0", port=6379, db=0)


def main_loop():
    global in_port
    while True:
        msg = in_port.receive()
        if input_disconnected(msg):
            print("MIDI connection interrupted.")
            time.sleep(1)
            redis.publish("connection", "disconnect")
            in_port = connect_input_port()
            redis.publish("connection", "reconnect")
            print("MIDI connection reestablished.")
        else:
            redis.publish("midi", json.dumps(msg.dict()))


def detect_input_port():
    input_names = midi_in.get_ports()
    for name in input_names:
        if config.midi_input_port in name:
            return mido.open_input(name)
    return None


def connect_input_port():
    print("Attempting to connect to input port...")
    while True:
        in_port = detect_input_port()
        if in_port is not None:
            return in_port
        time.sleep(0.1)


def input_disconnected(msg):
    return msg.type == 'control_change' and msg.channel == 2 and msg.control == 121


midi_in = rtmidi.MidiIn()
in_port = connect_input_port()
print("MIDI connection established.")
main_loop()