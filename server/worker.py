import logging
import threading
import time


class Worker:
    """Worker Class

    A class to execute periodic background tasks.

    Args:
        period : Worker period in seconds.
        fcn : Function to execute every period.
        args : Tuple with arguments for the given function.
        name : Optional worker name.

    """
    def __init__(self, period, fcn, args, name=""):
        assert (isinstance(args, tuple))
        self.period = period
        self.fcn = fcn
        self.args = args
        self.name = name
        self.enable = True
        logging.info(f"Starting worker: {self.name}")
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def loop(self):
        next_call = time.time()
        while (self.enable):
            self.fcn(*self.args)
            next_call += self.period
            sleep = next_call - time.time()
            if (sleep > 0):
                time.sleep(sleep)

    def stop(self):
        logging.info(f"Stopping worker: {self.name}")
        self.enable = False
