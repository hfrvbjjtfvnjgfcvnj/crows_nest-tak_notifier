import os
import json
import time
import tak_connection

from tak_chat_formatter import TakChatFormatter

def load_configuration():
    dirname = os.path.dirname(__file__)
    filename = os.path.join(dirname, 'config.json')
    f=open(filename)
    config=json.load(f)
    f.close()
    return config

config=load_configuration()
print(config)

tak_connection.create_tak_connection(config)
formatter = TakChatFormatter(config)

seconds = 0
while seconds < 30:
    #sender.send(formatter.format_chat_msg("THIS IS A TEST MESSAGE"))
    tak_connection.send_to_tak(formatter.format_chat_msg("THIS IS A TEST MESSAGE"))
    time.sleep(1)
    seconds = seconds + 1
