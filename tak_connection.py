""" connection to a TAK server  """

import asyncio
from configparser import ConfigParser
import threading
from timeit import default_timer as timer
from queue import Queue
from datetime import datetime

import pytak

from tak_chat_formatter import TakChatFormatter

# pylint: disable=invalid-name

RESET_TAK_CONNECTION_EVERY_N_SECONDS = 60*60
HEARTBEAT_TAK_EVERY_N_SECONDS = 30*60

thread = None  # thread for running asyncio event loop
lock = threading.Lock()  # synchronization for globals
clitool = None  # instance from pytak
# flag denoting clitool loop has exited (it can't be restarted, it must be completely reinitialized)
clitool_done = False
send_queue = Queue()  # queue for sending to TAK
receive_queue = Queue()  # queue for receiving from TAK


def __build_pytak_config(crows_nest_config: dict):
    pytak_config = ConfigParser()
    pytak_config["tak_server_config"] = crows_nest_config["tak_server_config"]
    pytak_config = pytak_config["tak_server_config"]
    return pytak_config


async def __clitool_setup_async(crows_nest_config: dict):
    """ CLITOOL "main" loop """
    global clitool
    # build a pytak config from the input config
    pytak_config = __build_pytak_config(crows_nest_config)

    clitool = pytak.CLITool(pytak_config)
    # clitool = MyCLITool(pytak_config)
    await clitool.setup()

    clitool.add_task(TakSender(clitool.tx_queue,
                     pytak_config, crows_nest_config))


class TakReceiver(pytak.QueueWorker):
    """Defines how you will handle events from RX Queue."""

    async def handle_data(self, data):
        """Handle data from the receive queue."""
        print(f"Received:\n{data.decode()}\n")
        receive_queue.put(data)

    async def run(self):  # pylint: disable=arguments-differ
        """Read from the receive queue, put data onto handler."""
        while 1:
            data = (
                await self.queue.get()
            )  # this is how we get the received CoT from rx_queue
            await self.handle_data(data)


class TakSender(pytak.QueueWorker):
    """
    Defines how you process or generate your Cursor-On-Target Events.
    From there it adds the COT Events to a queue for TX to a COT_URL.
    """

    def __init__(self, out_queue: Queue, pytak_config: dict, crows_nest_config: dict):
        super().__init__(out_queue, pytak_config)
        self.in_queue = send_queue
        self.crows_nest_config = crows_nest_config

    def send(self, msg: str):
        """Synchronous function to send a message"""
        self.in_queue.put(msg)

    async def __handle_data(self, data):
        """Puts event into output queue (maybe making a function for this isn't necessary?)"""
        event = data
        await self.put_queue(event)

    async def run(self, number_of_iterations=-1):
        """Run the loop for processing or generating pre-CoT data."""
        print("TakSender.run() started")
        bh_formatter = TakChatFormatter(self.crows_nest_config)
        start = timer()
        beat = start
        while timer()-start < RESET_TAK_CONNECTION_EVERY_N_SECONDS:
            if not self.in_queue.empty():
                data = self.in_queue.get()
                # self._logger.info("Sending:\n%s\n", data.decode())
                await self.__handle_data(data)
            else:
                await asyncio.sleep(5)
                now = timer()
                if (beat == start and now - start > 30) or (timer() - beat > HEARTBEAT_TAK_EVERY_N_SECONDS):
                    beat = timer()
                    await self.__handle_data(bh_formatter.format_chat_msg(f"Crows Nest Heartbeat: {datetime.now()}").encode("utf-8"))

        clitool.add_task(TakReset())
        print("TakSender.run() finished")


class TakReset():
    """ Pytak task that causes the connection and asyncio  """

    async def run(self, _=-1):
        """ a 'run' task that exist immediately - this causes the pytak loop to exit """
        print("TakReset.run()")


async def __setup_and_run_clitool_async(crows_nest_config: dict):
    await __clitool_setup_async(crows_nest_config)
    await clitool.run()


def __sync_clitool_run(crows_nest_config: dict):
    global clitool_done
    while True:
        print("CLITOOL STARTED")
        # asyncio.run(clitool.run())
        asyncio.run(__setup_and_run_clitool_async(crows_nest_config))
        print("CLITOOL DONE")
    lock.acquire()
    clitool_done = True
    lock.release()


def create_tak_connection(crows_nest_config: dict):  # -> TakSender:
    """ Create asynchronous TakSender class """
    global thread
    lock.acquire()

    if thread is None or not thread.is_alive():
        thread = threading.Thread(
            target=__sync_clitool_run, args=(crows_nest_config,))
        thread.start()
    lock.release()


def __check_clitool():
    throw_error = False
    lock.acquire()
    throw_error = clitool_done
    lock.release()

    if throw_error:
        raise ConnectionError("TAK Server Connection lost")


def send_to_tak(msg: bytes):
    """ Queues a message to send to TAK server """
    __check_clitool()
    send_queue.put(msg)


def receive_from_tak() -> bytes:
    """ Fetches a queued message received from the TAK server """
    if receive_queue.empty():
        __check_clitool()
        return None
    return receive_queue.get_nowait()
