import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from datetime import timezone
from datetime import timedelta
import uuid
import re
import time
from tak_connection import create_tak_connection

class NotifierFunctor:
  def __init__(self,config):
    self.connection=create_tak_connection(config);
    self.__loadxml();
    time.sleep(2);
    self(config,"TakNotifier - Active","0",0,"","control","");
    self(config,"TakNotifier - Active","1",0,"","control","");
    self(config,"TakNotifier - Active","2",0,"","control","");
  
  def __call__(self,config,title,msg_text,priority,alert_type_name,sound,url):
    tak_notifier_alert_on=config.get("tak_notifier_alert_on",[]);
    if ("control" == alert_type_name) or  ("*" in tak_notifier_alert_on) or (alert_type_name in tak_notifier_alert_on):
      content="%s||%s"%(title,msg_text);
      msg=self.__customize_template(config,content);
      print("############################################")
      print(msg);
      print("############################################")
      self.connection.send(msg.encode("utf-8"));
    #else:
    #  print("__call__(%s) dropping..."%alert_type_name);
    
  def __loadxml(self):
    self.template = Path('plugins/tak_notifier/template.xml').read_text();

  def __customize_template(self,config,content):
    custom = self.template;
    custom=custom.replace("\n","");
    custom=re.sub("\s\s+"," ",custom)
    custom=custom.replace("> <","><")
    
    replacements = self.__build_replacments(config,content);
    keys=replacements.keys();
    for key in keys:
      rep=replacements[key];
      custom=custom.replace(key,rep);
    #custom=custom.replace("\n","");
    #custom=re.sub("\s\s+"," ",custom)
    #custom=custom.replace("> <","><")
    return custom
  
  def __build_replacments(self,config,content):
    replacements={}
    t0=datetime.utcnow().replace(tzinfo=timezone.utc)
    duration=timedelta(minutes=1);
    stale=t0+duration;
    replacements["[TIME]"] = t0.isoformat();
    replacements["[STALE]"] = stale.isoformat();
    replacements["[UUID]"] = str(uuid.uuid4());
    replacements["[LAT]"] = str(config["station_latitude"]);
    replacements["[LON]"] = str(config["station_longitude"]);
    replacements["[CALLSIGN]"] = config["tak_notifier_callsign"];
    replacements["[CONTENT]"] = content;
    return replacements




