import os
import shutil
import signal
from pathlib import Path
from tempfile import TemporaryDirectory

class DisableKeyboardInterrupt:
    def __enter__(self):
        def handler(sig, frame):
            print("Please wait, still cleaning up!")

        self.old_handler = signal.signal(signal.SIGINT, handler)

    def __exit__(self, type, value, traceback):
        signal.signal(signal.SIGINT, self.old_handler)

class Workdir:
    def __init__(self):
        self.directory = TemporaryDirectory().name
        self.directory.mkdir()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        with DisableKeyboardInterrupt():
            shutil.rmtree(self.directory)
