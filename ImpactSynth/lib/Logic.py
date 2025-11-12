import os
import re
import shutil
from abc import ABC, abstractmethod

from qt import QEventLoop, QTimer


class Logic(ABC):

    def __init__(self, log_callback, progress_callback):
        self.proc = None

        self._parameterNode = None
        self.workdir = None
        self.log_callback = log_callback
        self.progress_callback = progress_callback

    def on_open_tab(self):
        pass

    def stop(self):
        if self.proc:
            self.proc.kill()
            self.proc.wait()
            self.proc = None
            self.remove_work_dir()

    def remove_work_dir(self):
        if self.workdir and os.path.exists(self.workdir):
            shutil.rmtree(self.workdir)

    def get_workdir(self):
        return self.workdir

    def wait(self):
        loop = QEventLoop()
        timer = QTimer()
        timer.setInterval(100)

        def tick():
            if self.proc is None:
                timer.stop()
                loop.quit()
                return
            line = self.proc.stdout.readline().rstrip()
            if line:
                self.log_callback(line)
                m = re.search(r"\b(\d{1,3})%(?=\s+\d+/\d+)", line)
                speed = re.search(r"([\d.]+)\s*(it/s|s/it)", line)
                if m:
                    pct = int(m.group(1))
                if speed:
                    self.progress_callback(pct, speed.group(1) + " " + speed.group(2))

            if self.proc.poll() is not None:
                timer.stop()
                loop.quit()

        timer.timeout.connect(tick)
        timer.start()
        loop.exec_()

    @abstractmethod
    def process(self, device: str) -> None:
        pass
