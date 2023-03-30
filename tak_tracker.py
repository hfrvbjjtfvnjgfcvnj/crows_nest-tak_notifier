import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from datetime import timezone
from datetime import timedelta
import uuid
import re
import time
from tak_connection import create_tak_connection


class Tracker:
    def __init__(self,config):
        self.connection=create_tak_connection(config);
        self.__loadxml();
        time.sleep(2);
        self.last_track_time=time.time();
        self.track_interval_sec=config.get("tak_tracker_update_interval_seconds",15);
        self.uuid_hex_map={};
        print("tak_tracker - Tracker() initialized");

    def track_alert_aircraft(self,list_of_aircraft,field_map):
        t=time.time();
        if (t-self.last_track_time >= self.track_interval_sec):
            for aircraft in list_of_aircraft:
                custom=self.__customize_template(aircraft,field_map);
                self.connection.send(custom.encode('utf-8'));
            self.last_track_time=t;

    def __loadxml(self):
        self.template = Path('plugins/tak_notifier/plitemplate.xml').read_text();
    
    def __customize_template(self,aircraft,field_map):
        custom = self.template;
        custom=custom.replace("\n","");
        custom=re.sub("\s\s+"," ",custom)
        custom=custom.replace("> <","><")
        
        replacements = self.__build_replacments(aircraft,field_map);
        keys=replacements.keys();
        for key in keys:
            rep=replacements[key];
            custom=custom.replace(key,rep);
        #custom=custom.replace("\n","");
        #custom=re.sub("\s\s+"," ",custom)
        #custom=custom.replace("> <","><")
        return custom
    
    def __build_replacments(self,aircraft,field_map):
        replacements={}
        t0=datetime.utcnow().replace(tzinfo=timezone.utc)
        duration=timedelta(minutes=1);
        stale=t0+duration;
        replacements["[TIME]"] = t0.isoformat();
        replacements["[STALE]"] = stale.isoformat();
        replacements["[UUID]"] = self.uuid_hex_map.get(aircraft[field_map['hex']],str(uuid.uuid4()));
        self.uuid_hex_map[aircraft[field_map['hex']]] = replacements["[UUID]"];
        replacements["[LAT]"] = str(aircraft[field_map['latitude']]);
        replacements["[LON]"] = str(aircraft[field_map['longitude']]);
        callsign=aircraft[field_map['registration']];
        if callsign is None or "" == callsign:
            callsign=aircraft[field_map['hex']];
        replacements["[CALLSIGN]"] = callsign;
        replacements["[TRACK]"] = str(aircraft[field_map['track']]);
        replacements["[SPEED]"] = str(aircraft[field_map['speed']]);
        replacements["[TYPE]"] = self.__aircraft_type_milstd(aircraft,field_map);
        return replacements;

    def __faa_to_icao_type(self,aircraft,field_map):
        faa_type_name=aircraft[field_map['faa_type_name']];
        if (faa_type_name is None):
            return None;
        if ('rotorcraft' in faa_type_name):
            return 'H2T';
        #assume a single-engine turboprop as a catch-all
        return 'L1T';

    def __aircraft_type_milstd(self,aircraft,field_map):
        attitude='u';
        affiliation='M';
        type='F';
        icao_description=aircraft[field_map['description']];

        #try to make FAA type to an ICAO description
        if (icao_description is None) or (len(icao_description) < 3):
            icao_description = self.__faa_to_icao_type(aircraft,field_map);

        #map ICAO helo and tilt-rotor to CoT helo type
        if (icao_description[0] == 'H') or (icao_description[0] == 'T'):
            type='H';
        
        if (icao_description[2] == 'J'):
            type="F-F";

        milstd="a-%s-A-%s-%s"%(attitude,affiliation,type);
        print("tracking %s: %s->%s %s %s"%(aircraft[field_map['hex']],icao_description,milstd,aircraft[field_map['latitude']],aircraft[field_map['longitude']]));
        return milstd;
