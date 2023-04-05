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
        self.last_metadata_time=time.time();
        self.sent_metadata=False;
        self.uuid_hex_map={};
        tak_tracker_config=config.get("tak_tracker",{});
        self.config=config;
        self.tak_tracker_config=tak_tracker_config;
        self.track_interval_sec=tak_tracker_config.get("update_interval_seconds",15);
        self.metadata_interval_sec=tak_tracker_config.get("metadata_update_interval_seconds",300);
        self.attitude_map=tak_tracker_config.get("attitude_map",{});
        print("tak_tracker - attitude_map");
        print(self.attitude_map)
        print("tak_tracker - Tracker() initialized");

        #note loiter exclusions for broadcast to tak server
        self.loiter_exclusions=config.get("alert_loiter_exclusions",[]);

    def track_alert_aircraft(self,list_of_aircraft,field_map):
        t=time.time();
        if (t-self.last_track_time >= self.track_interval_sec):
            for aircraft in list_of_aircraft:
                custom=self.__customize_pli_template(aircraft,field_map);
                self.connection.send(custom.encode('utf-8'));
            self.last_track_time=t;
            self.__try_send_metadata(t);

    def __try_send_metadata(self,t):
        if (self.sent_metadata == False) or (t-self.last_metadata_time >= self.metadata_interval_sec): #resend at configured interval
            #send station range rings
            custom = self.__customize_range_rings_template();
            if (custom != ""):
                self.connection.send(custom.encode('utf-8'));

            #send loiter exclusion zones
            for exclusion_zone in self.loiter_exclusions:
                if not exclusion_zone.get("enabled",False):
                    continue;
                print("Exclusion Zone: %s"%(exclusion_zone["name"],));
                custom=self.__customize_exclusion_zone_template(exclusion_zone);
                self.connection.send(custom.encode('utf-8'));
            self.last_metadata_time=t;
            self.sent_metadata=True;

    def __loadxml(self):
        self.pli_template = Path('plugins/tak_notifier/plitemplate.xml').read_text();
        self.range_rings_template = Path('plugins/tak_notifier/range_rings_template.xml').read_text();
        self.ellipse_template = Path('plugins/tak_notifier/ellipse_template.xml').read_text().replace("\n","");
    
    def __customize_pli_template(self,aircraft,field_map):
        custom = self.pli_template;
        custom=custom.replace("\n","");
        custom=custom.replace("\t","");
        custom=re.sub("\s\s+"," ",custom)
        custom=custom.replace("> <","><")
        
        replacements = self.__build_pli_replacments(aircraft,field_map);
        keys=replacements.keys();
        for key in keys:
            rep=replacements[key];
            custom=custom.replace(key,rep);
        return custom
   
    def __customize_range_rings_template(self):
        custom = self.range_rings_template;
        custom=custom.replace("\n","");
        custom=custom.replace("\t","");
        custom=re.sub("\s\s+"," ",custom)
        custom=custom.replace("> <","><")
        
        range_zone={}
        range_zone["name"] = "Station";
        range_zone["latitude"]=str(self.config["station_latitude"]);
        range_zone["longitude"]=str(self.config["station_longitude"]);
        range_zone["radius_meters"]=str(self.tak_tracker_config["range_rings_distance_meters"]);

        replacements = self.__build_range_rings_replacements(range_zone,self.tak_tracker_config["feature_colors"]["station_range_rings"]);
        
        #here we inject a special rule to replace the single ellipse in the template with N ellipses
        rings="";
        for i in range(self.tak_tracker_config.get("range_rings_count",0)):
            rings=rings+self.ellipse_template;
            radius=int(range_zone["radius_meters"])*(i+1);
            rings=rings.replace("[RADIUS_METERS]",str(radius));

        if rings=="":
            return "";
        
        print("mapping %s -> %s"%(self.ellipse_template,rings));
        #replacements[self.ellipse_template]=rings;
        #print("BEFORE: %s"%custom);
        custom=custom.replace(self.ellipse_template,rings);
        keys=replacements.keys();
        for key in keys:
            rep=replacements[key];
            custom=custom.replace(key,rep);
        print(custom);
        return custom

        
    def __customize_exclusion_zone_template(self,exclusion_zone):
        custom = self.range_rings_template;
        custom=custom.replace("\n","");
        custom=custom.replace("\t","");
        custom=re.sub("\s\s+"," ",custom)
        custom=custom.replace("> <","><")
        
        replacements = self.__build_range_rings_replacements(exclusion_zone,self.tak_tracker_config["feature_colors"]["exclusion_zone_range_rings"]);
        keys=replacements.keys();
        for key in keys:
            rep=replacements[key];
            custom=custom.replace(key,rep);
        return custom


    def __build_callsign(self,aircraft,field_map):
        callsign=aircraft[field_map['icao_name']];
        operator=aircraft[field_map['registrant_name']];

        if callsign is None:
            callsign=aircraft[field_map['registration']];
        if callsign is None:
            callsign=aircraft[field_map['hex']];

        if (operator is not None) and (operator != "None"):
            #callsign=operator+"\n"+callsign;
            callsign="%s - %s"%(operator,callsign);

        #if callsign is None or "" == callsign:
        #    callsign=aircraft[field_map['registration']];
        #    if callsign is None or "" == callsign:
        #        callsign=aircraft[field_map['hex']];
        return callsign


    def __build_pli_replacments(self,aircraft,field_map):
        replacements={}
        t0=datetime.utcnow().replace(tzinfo=timezone.utc)
        duration=timedelta(seconds=(int(self.metadata_interval_sec)*2));
        stale=t0+duration;
        replacements["[TIME]"] = t0.isoformat();
        replacements["[STALE]"] = stale.isoformat();
        replacements["[UUID]"] = self.uuid_hex_map.get(aircraft[field_map['hex']],str(uuid.uuid4()));
        self.uuid_hex_map[aircraft[field_map['hex']]] = replacements["[UUID]"];
        replacements["[LAT]"] = str(aircraft[field_map['latitude']]);
        replacements["[LON]"] = str(aircraft[field_map['longitude']]);
        callsign=self.__build_callsign(aircraft,field_map);
        replacements["[CALLSIGN]"] = callsign;
        replacements["[TRACK]"] = str(aircraft[field_map['track']]);
        replacements["[SPEED]"] = str(aircraft[field_map['speed']]);
        replacements["[TYPE]"] = self.__aircraft_type_milstd(aircraft,field_map);
        return replacements;

    def __build_range_rings_replacements(self,ring_zone,color_map):
        replacements={};
        t0=datetime.utcnow().replace(tzinfo=timezone.utc)
        duration=timedelta(minutes=1);
        stale=t0+duration;
        
        ename=ring_zone["name"];
        ekey="ring_zone: %s"%(ename,);
        elat=ring_zone["latitude"];
        elon=ring_zone["longitude"];
        radius=ring_zone["radius_meters"];

        replacements["[TIME]"] = t0.isoformat();
        replacements["[STALE]"] = stale.isoformat();
        replacements["[UUID]"] = self.uuid_hex_map.get(ekey,str(uuid.uuid4()));
        self.uuid_hex_map[ekey] = replacements["[UUID]"];
        replacements["[LAT]"] = str(elat);
        replacements["[LON]"] = str(elon);
        replacements["[RADIUS_METERS]"] = str(radius);
        replacements["[NAME]"] = ename;
        #replacements["[COLOR]"] = self.__hex_str_to_color(self.tak_tracker_config.get('exclusion_range_rings_color','FFFF0000'));
        #replacements["[FILL_COLOR]"] = self.__hex_str_to_color(self.tak_tracker_config.get('exclusion_range_rings_fill_color','00FF0000'));
        #replacements["[STROKE_WEIGHT]"] = str(self.tak_tracker_config.get('exclusion_range_stroke_weight',3));
        replacements["[COLOR]"] = self.__hex_str_to_color(color_map['color']);
        replacements["[FILL_COLOR]"] = self.__hex_str_to_color(color_map['fill_color']);
        replacements["[STROKE_WEIGHT]"] = str(color_map['stroke_weight']);

        return replacements;

    def __hex_str_to_color(self,hex_str):
        v=int(hex_str,16);
        #print("v:%d"%(v,));
        s=v-(1<<32);
        #print("s:%d"%(s,));
        #print("%s - > %s"%(hex_str,str(s)));
        return str(s);


        return str(u);

    def __build_range_rings_elipse(self,radius_meters):
        t='<ellipse minor="17058.58" angle="360" major="17058.58"/>'

    def __faa_to_icao_type(self,aircraft,field_map):
        faa_type_name=aircraft[field_map['faa_type_name']];
        if (faa_type_name is not None) and ('rotorcraft' in faa_type_name):
            return 'H2T';
        #assume a single-engine turboprop as a catch-all
        return 'L1T';

    def __aircraft_type_milstd(self,aircraft,field_map):
        attitude=self.attitude_map.get(aircraft[field_map['alert_type_name']],'s');
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
