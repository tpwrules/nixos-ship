import os
import shutil
import signal
import pathlib
import tempfile

from . import git_utils

class DisableKeyboardInterrupt:
    def __enter__(self):
        def handler(sig, frame):
            print("Please wait, still cleaning up!")

        self.old_handler = signal.signal(signal.SIGINT, handler)

    def __exit__(self, type, value, traceback):
        signal.signal(signal.SIGINT, self.old_handler)

class Workdir:
    def __init__(self, autoprune=False):
        self.autoprune = autoprune
        self.path = pathlib.Path(tempfile.TemporaryDirectory().name)
        self.path.mkdir()

    def __enter__(self):
        return self.path

    def __exit__(self, exc_type, exc_value, traceback):
        with DisableKeyboardInterrupt():
            shutil.rmtree(self.path)
            if self.autoprune:
                git_utils.prune_worktrees()
