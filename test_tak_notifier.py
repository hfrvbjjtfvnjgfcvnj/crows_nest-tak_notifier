import os
import json
from tak_notifier import NotifierFunctor

def load_configuration():
  global config;
  dirname = os.path.dirname(__file__)
  filename = os.path.join(dirname, 'config.json')
  f=open(filename);
  config=json.load(f);
  f.close();
  return config

config=load_configuration();
#print(config)
nf=NotifierFunctor(config);
sleep(10);
nf(config,"This is a title","This is some text",0,"spook","none");
counter=0;
while 1:
    nf(config,"Loop Message","Message %d"%counter,0,"spook","none");
    counter=counter+1

