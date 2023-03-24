import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from datetime import timezone
from datetime import timedelta
import uuid
import re

class NotifierFunctor:
  def __init__(self):
    self.__loadxml();
  
  def __call__(self,config,title,msg_text,priority,sound,url):
    tak_notifier_alert_on=config.get("tak_notifier_alert_on",[]);
    if ("*" in tak_notifier_alert_on) or (sound in tak_notifier_alert_on):
      content="%s||%s"%(title,msg_text);
      msg=self.__customize_template(config,content);
      print(msg);
    
  def __loadxml(self):
    self.template = Path('template.xml').read_text();

  def __customize_template(self,config,content):
    custom = self.template;
    
    replacements = self.__build_replacments(config,content);
    keys=replacements.keys();
    for key in keys:
      rep=replacements[key];
      custom=custom.replace(key,rep);
    custom=custom.replace("\n","");
    custom=re.sub("\s\s+"," ",custom)
    custom=custom.replace("> <","><")
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




