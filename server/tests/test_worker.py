import queue
import time

import worker


def test_worker():
    product_queue = queue.Queue()

    def multiply(a, b, q):
        return q.put(a * b)

    period = 1.0
    w = worker.Worker(period, fcn=multiply, args=(2, 3, product_queue))
    # Sleep 1/3 of the period and stop the worker before the subsequent
    # period
    time.sleep(period / 3)
    w.stop()
    product = product_queue.get()
    product_queue.task_done()
    assert (product == (2 * 3))
    assert (product_queue.empty())
