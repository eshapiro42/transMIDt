import config
import itertools
import json
import mido
import mido.backends.rtmidi
import psutil
import rtmidi
import time
import volume
from redis import Redis
from threading import Event, Thread
from queue import Queue


class Listener(Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started = False
        self.worker_cycle = None
        self.redis = Redis(host="192.168.1.101", port=6379, db=0)
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe("connection")
        self.pubsub.subscribe("midi")
        self.volume_manager = VolumeManager()
        self.worker_threads = []

    def register_worker(self, thread):
        if not self.started:
            self.worker_threads.append(thread)
        else:
            raise Exception('Cannot add more workers once listener has started.')

    def dispatch(self, message):
        if not self.started:
            raise Exception('Cannot dispatch messages until listener has started.')
        else:
            worker = next(self.worker_cycle)
            worker.queue.put(message)

    def run(self):
        self.started = True
        self.volume_manager.daemon = True
        self.volume_manager.start()
        for worker in self.worker_threads:
            worker.daemon = True
            worker.start()
        self.worker_cycle = itertools.cycle(self.worker_threads)
        for message in self.pubsub.listen():
            self.dispatch(message)


class Worker(Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = Queue()

    def run(self):
        while True:
            message = self.queue.get()
            channel = message['channel'].decode()
            try:
                data = message['data'].decode()
            except AttributeError:
                continue
            if channel == 'midi':
                data = json.loads(data)
                midi(data)
            elif channel == 'connection':
                if data == 'reconnect':
                    reconnect()
                elif data == 'disconnect':
                    disconnect()


class VolumeManager(Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.volume_start = Event()
        self.volume_stop = Event()

    def run(self):
        while True:
            self.volume_start.wait()
            start = time.time()
            self.volume_stop.wait()
            stop = time.time()
            # A short press means volume up
            if stop - start < 0.5:
                volume.volume_up()
            # A long press means volume down
            else:
                volume.volume_down()
            self.volume_start.clear()
            self.volume_stop.clear()


def midi(data):
    try:
        msg = mido.Message.from_dict(data)
        out_port.send(msg)
        if msg.type == 'control_change' and msg.control == 66 and msg.channel == 2:
            if msg.value == 127:
                listener.volume_manager.volume_start.set()
            elif msg.value == 0:
                listener.volume_manager.volume_stop.set()
    except TypeError:
        pass


def disconnect():
    print("MIDI connection interrupted.")
    if proc is not None:
        proc.suspend()


def reconnect():
    print("MIDI connection established.")
    if proc is not None:
        proc.resume()


def detect_output_port():
    output_names = midi_out.get_ports()
    for name in output_names:
        if config.midi_output_port in name:
            return mido.open_output(name)
    return None


def connect_output_port():
    print("Attempting to connect to output port...")
    while True:
        try:
            return detect_output_port()
        except:
            pass
        time.sleep(0.1)


def find_process():
    process_name = config.process
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"] == process_name:
            return proc
    print(f"Could not find a running process called {process_name}.")
    return None


if __name__ == "__main__":
    midi_out = rtmidi.MidiOut()
    out_port = connect_output_port()
    print("MIDI connection established.")
    proc = find_process()
    listener = Listener(name="listener")
    for idx in range(config.workers):
        worker = Worker(name=f"worker-{idx}")
        listener.register_worker(worker)
    listener.start()