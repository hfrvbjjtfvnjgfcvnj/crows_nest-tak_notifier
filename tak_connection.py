import asyncio
from configparser import ConfigParser
import pytak
import threading
import time

instance=None;
thread=None;
lock=threading.Lock();

async def a_conn_thread():
    while True:
        task = asyncio.create_task(instance.setup());
        await task
        ex = task.exception();
        print(ex);
        time.sleep(5);


def conn_thread():
    asyncio.run(a_conn_thread());

def create_tak_connection(config):
    global instance
    global thread
    lock.acquire();
    if instance is None:
        print("create_tak_connection() - creating a new connection");
        instance = TakConnection(config);
        thread=threading.Thread(target=conn_thread);
        thread.start();
    time.sleep(1);
    lock.release();
    return instance;

class TakSerializer(pytak.QueueWorker):
    async def handle_data(self, data):
        #print("TakSerializer.handle_data() - Start");
        await self.put_queue(data);
        #print("TakSerializer.handle_data() - End");

class TakEnqueue:
    def __init__(self,conn,data):
        self.conn=conn;
        self.data=data;

    def __await__(self):
        pass

    async def run(self, number_of_iterations=1):
        await self.conn.serializer.handle_data(self.data);

class TakConnection:
    def __init__(self,config):
        self._config=config;
        self.pytakConfig=ConfigParser();
        self.pytakConfig["tak_server_config"]=config["tak_server_config"];
        self.pytakConfig=self.pytakConfig["tak_server_config"];
        self.clitool=pytak.CLITool(self.pytakConfig);
        self.msgs=[];
        #startup="TakConnection - Init".encode('utf-8');
        #self.clitool.tx_queue.put_nowait(startup);

    async def run_clitool(self):
        """Run this Thread and its associated coroutine tasks."""
        self.clitool._logger.info("Run: %s", self.__class__)

        await self.clitool.hello_event()
        self.clitool.run_tasks()

        done, _ = await asyncio.wait(
            self.clitool.running_tasks, return_when=asyncio.FIRST_COMPLETED
        )

        for task in done:
            #self._logger.info("Complete: %s", task)
            print("Complete: %s", task)

        for task in self.clitool.running_tasks:
            try:
                task.cancel();
                ex = task.exception();
                if ex is not None:
                    print(ex);
            except:
                pass;
        self.clitool.tasks.clear();
        self.clitool.running_tasks.clear();


    async def setup(self):
        print("settingup CLITOOL...");
        try:
            await self.clitool.setup();
            self.serializer=TakSerializer(self.clitool.tx_queue,self.pytakConfig);
            self.clitool.add_task(self.serializer);
            print("RUNNING CLITOOL");
            #await self.clitool.run();
            await self.run_clitool();
        except Exception as ex:
            print(ex);
        print("CLITOOL DONE");

    def send(self,data):
        #print("TakConnection.send() - Start");
        self.clitool.tx_queue.put_nowait(data);
        #print("TakConnection.send() - End");
