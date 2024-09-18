import asyncio
from configparser import ConfigParser
import threading
import time
from queue import Queue


import multiprocessing as mp
import logging
from typing import Set, Union

import pytak

thread=None                     #thread for running asyncio event loop
lock=threading.Lock()           #synchronization for globals
clitool=None                    #instance from pytak
clitool_done=False              #flag denoting clitool loop has exited (it can't be restarted, it must be completely reinitialized)
send_queue=Queue()              #queue for sending to TAK
receive_queue=Queue()           #queue for receiving from TAK

def __build_pytak_config(crows_nest_config:dict):
    pytak_config=ConfigParser()
    pytak_config["tak_server_config"]=crows_nest_config["tak_server_config"]
    pytak_config=pytak_config["tak_server_config"]
    return pytak_config

async def __clitool_setup_async(crows_nest_config:dict):
    """ CLITOOL "main" loop """
    global clitool
    #build a pytak config from the input config
    pytak_config = __build_pytak_config(crows_nest_config)

    clitool = pytak.CLITool(pytak_config)
    #clitool = MyCLITool(pytak_config)
    await clitool.setup()

    clitool.add_task(TakSender(clitool.tx_queue, pytak_config))

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

    def __init__(self, out_queue:Queue, config:dict):
        super().__init__(out_queue, config)
        self.in_queue = send_queue

    def send(self, msg: str):
        """Synchronous function to send a message"""
        self.in_queue.put(msg)

    async def __handle_data(self, data):
        """Puts event into output queue (maybe making a function for this isn't necessary?)"""
        event = data
        await self.put_queue(event)

    async def run(self, number_of_iterations=-1):
        """Run the loop for processing or generating pre-CoT data."""
        while 1:
            if not self.in_queue.empty():
                data = self.in_queue.get()
                #self._logger.info("Sending:\n%s\n", data.decode())
                await self.__handle_data(data)
            else:
                await asyncio.sleep(0.05)

async def __setup_and_run_clitool_async(crows_nest_config:dict):
    await __clitool_setup_async(crows_nest_config)
    await clitool.run()

def __sync_clitool_run(crows_nest_config:dict):
    global clitool_done
    print("CLITOOL STARTED")
    #asyncio.run(clitool.run())
    asyncio.run(__setup_and_run_clitool_async(crows_nest_config))
    print("CLITOOL DONE")
    lock.acquire()
    clitool_done = True
    lock.release()

def create_tak_connection(crows_nest_config:dict):# -> TakSender:
    """ Create asynchronous TakSender class """
    global thread
    lock.acquire()

    if thread is None or not thread.is_alive():
        thread=threading.Thread(target=__sync_clitool_run, args=(crows_nest_config,))
        thread.start()
    lock.release()

def __check_clitool():
    throw_error = False
    lock.acquire()
    throw_error = clitool_done
    lock.release()

    if throw_error:
        raise ConnectionError("TAK Server Connection lost")

def send_to_tak(msg:bytes):
    """ Queues a message to send to TAK server """
    __check_clitool()
    send_queue.put(msg)

def receive_from_tak() -> bytes:
    """ Fetches a queued message received from the TAK server """
    if receive_queue.empty():
        __check_clitool()
        return None
    return receive_queue.get_nowait()
