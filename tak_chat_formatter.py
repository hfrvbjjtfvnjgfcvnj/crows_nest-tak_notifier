""" Classes for formatting messages to TAK specifications """

import uuid
import re
from pathlib import Path
from datetime import datetime
from datetime import timezone
from datetime import timedelta

class TakChatFormatter:
    """Formats strings into TAK chat messages"""
    def __init__(self,config):
        self.config = config
        self.__loadxml()

    def format_chat_msg(self, msg:str) -> str:
        """Returns a string properly formatted to pass a chat message to a TAK server"""
        return self.__customize_template(self.config, msg)

    def __loadxml(self):
        self.template = Path('plugins/tak_notifier/template.xml').read_text()

    def __customize_template(self,config,content):
        custom = self.template
        custom=custom.replace("\n","")
        custom=re.sub(r"\s\s+"," ",custom)
        custom=custom.replace("> <","><")

        replacements = self.__build_replacments(config,content)
        keys=replacements.keys()
        for key in keys:
            rep=replacements[key]
            custom=custom.replace(key,rep)
        return custom

    def __build_replacments(self,config,content):
        replacements={}
        t0=datetime.utcnow().replace(tzinfo=timezone.utc)
        duration=timedelta(minutes=1)
        stale=t0+duration
        replacements["[TIME]"] = t0.isoformat()
        replacements["[STALE]"] = stale.isoformat()
        replacements["[UUID]"] = str(uuid.uuid4())
        replacements["[LAT]"] = str(config["station_latitude"])
        replacements["[LON]"] = str(config["station_longitude"])
        replacements["[CALLSIGN]"] = config["tak_notifier_callsign"]
        replacements["[CONTENT]"] = content
        return replacements
