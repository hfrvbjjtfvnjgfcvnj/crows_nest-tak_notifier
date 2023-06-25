import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from datetime import timezone
from datetime import timedelta
import uuid
import re
import time
from tak_connection import create_tak_connection
import random
import copy

DEMO_OFFSET=False
DEMO_OFFSET_LAT = random.uniform(-30, 30);
DEMO_OFFSET_LON = random.uniform(-30, 30);

class UUID_Manager:
    def __init__(self,db_file):
        self.db_file=db_file;
        self.uuid_map={}

        #restore UUIDs from cache
        map=self.__read_db_file();
        for key in map.keys():
            self.uuid_map[key]=(map[key],True);

    def uuid(self,key,persist=False):
        write=False;
        if (persist) and (not key in self.uuid_map.keys()):
            write=True
        _uuid,persist=self.uuid_map.get(key,(str(uuid.uuid4()),persist));
        self.uuid_map[key]=(_uuid,persist);
        if write:
            self.__write_db_file();
        return _uuid;
    
    def get_historical_uuids(self):
        map=self.__read_db_file();
        return map.values();

    def __write_db_file(self):
        text=""
        for key in self.uuid_map.keys():
            uuid,persist=self.uuid_map[key];
            if not persist:
                continue;
            line='%s,%s\n'%(key,uuid);
            text=text+line;
        Path(self.db_file).write_text(text,'utf-8');


    def __read_db_file(self):
        kvp={}
        if not Path(self.db_file).exists():
            return kvp;
        data=Path(self.db_file).read_text();
        
        lines = data.rsplit("\n");
        for line in lines:
            parts = line.rsplit(",");
            if (len(parts) == 2):
                kvp[parts[0]] = parts[1];
        
        return kvp;

class Tracker:
    def __init__(self,config):
        global DEMO_OFFSET;
        DEMO_OFFSET=config.get("demo_coordinate_offset",False);

        self.connection=create_tak_connection(config);
        self.__loadxml();
        time.sleep(2);
        self.last_track_time=time.time();
        self.last_metadata_time=time.time();
        self.sent_metadata=False;
        self.uuid_map=UUID_Manager('plugins/tak_notifier/uuids.csv');
        tak_tracker_config=config.get("tak_tracker",{});
        self.config=config;
        self.tak_tracker_config=tak_tracker_config;
        self.track_interval_sec=tak_tracker_config.get("update_interval_seconds",15);
        self.metadata_interval_sec=tak_tracker_config.get("metadata_update_interval_seconds",300);
        self.attitude_map=tak_tracker_config.get("attitude_map",{});

        self.eta_zones=copy.deepcopy(config.get("alert_eta_positions", []));
        self.eta_radius=config.get("alert_eta_radius_meters",0);
        if config.get("alert_eta_station_position",False):
            eta_zone={}
            eta_zone["name"] = "Station";
            eta_zone["latitude"]=(self.config["station_latitude"]);
            eta_zone["longitude"]=(self.config["station_longitude"]);
            eta_zone["radius_meters"]=(self.config["alert_eta_radius_meters"]);
            eta_zone["enabled"]=True;
            self.eta_zones.append(eta_zone);
        print ("tak_tracker - eta_zones");
        print(self.eta_zones);

        print("tak_tracker - attitude_map");
        print(self.attitude_map)
        print("tak_tracker - Tracker() - Initialized");

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
# NOTE Apparently this does NOT work for shapes - neither does STALE expiration
#        #encourage others to delete any objects tied to historical UUIDs
#        if (self.sent_metadata == False):
#            old_uuids=self.uuid_map.get_historical_uuids();
#            for old_uuid in old_uuids:
#                print("trying to delete %s"%old_uuid);
#                custom = self.__customize_delete_template(old_uuid);
#                if (custom != ""):
#                    print("################")
#                    print(custom)
#                    print("################")
#                    self.connection.send(custom.encode('utf-8'));

        if (self.sent_metadata == False) or (t-self.last_metadata_time >= self.metadata_interval_sec): #resend at configured interval
            #send station range rings
            if (self.tak_tracker_config.get("range_rings_count",0) > 0):
                custom = self.__customize_range_rings_template();
                if (custom != ""):
                    self.connection.send(custom.encode('utf-8'));

            #send eta (intercept) zones
            if (self.tak_tracker_config.get("eta_rings_enabled",False)):
                i=0;
                for zone in self.eta_zones:
                    if not zone.get("enabled",False):
                        continue;
                    
                    custom = self.__customize_eta_zone_template(zone);
                    if (custom != ""):
                        self.connection.send(custom.encode('utf-8'));
                    i=i+1;

            #send loiter exclusion zones
            if (self.tak_tracker_config.get("exclusion_zone_rings_enabled",False)):
                for zone in self.loiter_exclusions:
                    if not zone.get("enabled",False):
                        continue;
                    
                    custom=self.__customize_exclusion_zone_template(zone);
                    if (custom != ""):
                        self.connection.send(custom.encode('utf-8'));
                self.last_metadata_time=t;
                self.sent_metadata=True;

    def __loadxml(self):
        self.pli_template = self.__xml_cleanup(Path('plugins/tak_notifier/plitemplate.xml').read_text());
        self.range_rings_template = self.__xml_cleanup(Path('plugins/tak_notifier/range_rings_template.xml').read_text());
        self.ellipse_template = self.__xml_cleanup(Path('plugins/tak_notifier/ellipse_template.xml').read_text());
        self.delete_template = self.__xml_cleanup(Path('plugins/tak_notifier/delete_template.xml').read_text());
    
    def __xml_cleanup(self,xml):
        xml=xml.replace("\n","");
        xml=xml.replace("\t","");
        xml=re.sub("\s\s+"," ",xml)
        xml=xml.replace("> <","><")
        return xml
    
    def __customize_delete_template(self,_uuid):
        custom = self.delete_template;
    
        replacements = self.__build_delete_replacements(_uuid);
        keys=replacements.keys();
        for key in keys:
            rep=replacements[key];
            custom=custom.replace(key,rep);
        return custom

    def __customize_pli_template(self,aircraft,field_map):
        custom = self.pli_template;
        
        replacements = self.__build_pli_replacments(aircraft,field_map);
        keys=replacements.keys();
        for key in keys:
            rep=replacements[key];
            custom=custom.replace(key,rep);
        return custom
   
    def __customize_range_rings_template(self):
        custom = self.range_rings_template;
        
        range_zone={}
        range_zone["name"] = "Station Ranges";
        range_zone["latitude"]=(self.config["station_latitude"]);
        range_zone["longitude"]=(self.config["station_longitude"]);
        range_zone["radius_meters"]=(self.tak_tracker_config["range_rings_distance_meters"]);

        replacements = self.__build_range_rings_replacements(range_zone,self.tak_tracker_config["feature_colors"]["station_range_rings"]);
        
        #here we inject a special rule to replace the single ellipse in the template with N ellipses
        rings="";
        for i in range(self.tak_tracker_config.get("range_rings_count",0)):
            rings=rings+self.ellipse_template;
            radius=int(range_zone["radius_meters"])*(i+1);
            rings=rings.replace("[RADIUS_METERS]",str(radius));

        if rings=="":
            return "";
        
        #print("mapping %s -> %s"%(self.ellipse_template,rings));
        #replacements[self.ellipse_template]=rings;
        #print("BEFORE: %s"%custom);
        custom=custom.replace(self.ellipse_template,rings);
        keys=replacements.keys();
        for key in keys:
            rep=replacements[key];
            custom=custom.replace(key,rep);
        return custom

        
    def __customize_exclusion_zone_template(self,exclusion_zone):
        custom = self.range_rings_template;
        
        replacements = self.__build_range_rings_replacements(exclusion_zone,self.tak_tracker_config["feature_colors"]["exclusion_zone_range_rings"]);
        keys=replacements.keys();
        for key in keys:
            rep=replacements[key];
            custom=custom.replace(key,rep);
        return custom
    
    def __customize_eta_zone_template(self,eta_zone):
        custom = self.range_rings_template;
        
        replacements = self.__build_range_rings_replacements(eta_zone,self.tak_tracker_config["feature_colors"]["eta_range_rings"]);
        keys=replacements.keys();
        for key in keys:
            rep=replacements[key];
            custom=custom.replace(key,rep);
        return custom
    def __add_newline_if_printable(self,text):
        if (text is None) or (len(text) == 0):
            return "";
        return "%s\n"%text;

    def __remarks_text(self,aircraft,field_map):
        hex=aircraft[field_map['hex']];
        registration=aircraft[field_map['registration']];
        operator=aircraft[field_map['registrant_name']];
        model=aircraft[field_map['icao_name']];
        comment=aircraft[field_map['comment']];

        remarks="%s%s%s%s%s"%(self.__add_newline_if_printable(comment),
            self.__add_newline_if_printable(operator),
            self.__add_newline_if_printable(model),
            self.__add_newline_if_printable(registration),
            self.__add_newline_if_printable(hex));
        return remarks;
    
    def __build_callsign(self,aircraft,field_map):
        callsign=aircraft[field_map['icao_name']];
        operator=aircraft[field_map['registrant_name']];
        comment=aircraft[field_map['comment']];
        if (comment is None):
            comment=""
        else:
            comment=comment+" "

        if callsign is None:
            callsign=aircraft[field_map['registration']];
        if callsign is None:
            callsign=aircraft[field_map['hex']];

        if (operator is not None) and (operator != "None"):
            callsign="%s - %s"%(operator,callsign);
        
        #prepend any comments
        callsign=comment+callsign;

        return callsign

    def __build_time_format(self,t0):
        return "%sZ"%(t0.isoformat().rsplit(".")[0]);

    def __build_coordinate_format(self,lat,lon):
        #this is used to inject a random offset to all mapped coordinates for 
        #generating demo/screenshot data and retaining privacy

        #it is possible after a service restart to get aircraft records down here that
        #dont yet have a lat/lon position - so handle it gracefully
        if (lat is None) or (lon is None):
            return ("0.0","0.0");
        lat=float(lat);
        lon=float(lon);
        if DEMO_OFFSET:
            olat = (lat+DEMO_OFFSET_LAT);
            olon = (lon+DEMO_OFFSET_LON);
            while(olat<-180):
                olat=olat+360;
            while(olon<-180):
                olon=olon+360;
            while (olat>180):
                olat=olat-360;
            while (olon>180):
                olon=olon-360;
            return (olat,olon);
        return (lat,lon);

    def __build_pli_replacments(self,aircraft,field_map):
        replacements={}
        t0=datetime.utcnow().replace(tzinfo=timezone.utc)
        duration=timedelta(seconds=(int(self.metadata_interval_sec)*2));
        stale=t0+duration;
        replacements["[TIME]"] = self.__build_time_format(t0);
        replacements["[STALE]"] = self.__build_time_format(stale);
        replacements["[UUID]"] = self.uuid_map.uuid(aircraft[field_map['hex']]);
        
        lat,lon = self.__build_coordinate_format(aircraft[field_map['latitude']],aircraft[field_map['longitude']]);
        replacements["[LAT]"] = str(lat);
        replacements["[LON]"] = str(lon);
        
        callsign=self.__build_callsign(aircraft,field_map);
        replacements["[CALLSIGN]"] = callsign;
        replacements["[TRACK]"] = str(aircraft[field_map['track']]);
        replacements["[SPEED]"] = str(aircraft[field_map['speed']]);
        replacements["[TYPE]"] = self.__aircraft_type_milstd(aircraft,field_map);
        replacements["[REMARKS]"] = self.__remarks_text(aircraft,field_map);
        return replacements;

    def __build_range_rings_replacements(self,ring_zone,color_map):
        replacements={};
        t0=datetime.utcnow().replace(tzinfo=timezone.utc)
        duration=timedelta(minutes=1);
        stale=t0+duration;
        
        ename=ring_zone["name"];
        ekey="ring_zone: %s"%(ename,);
        elat,elon = self.__build_coordinate_format(ring_zone["latitude"],ring_zone["longitude"]);
        radius=ring_zone["radius_meters"];

        replacements["[TIME]"] = self.__build_time_format(t0);
        replacements["[STALE]"] = self.__build_time_format(stale);
        replacements["[UUID]"] = self.uuid_map.uuid(ekey,persist=True);
        replacements["[LAT]"] = str(elat);
        replacements["[LON]"] = str(elon);
        replacements["[RADIUS_METERS]"] = str(radius);
        replacements["[NAME]"] = ename;
        replacements["[COLOR]"] = self.__hex_str_to_color(color_map['color']);
        replacements["[FILL_COLOR]"] = self.__hex_str_to_color(color_map['fill_color']);
        replacements["[STROKE_WEIGHT]"] = str(color_map['stroke_weight']);

        return replacements;

    def __build_delete_replacements(self,_uuid):
        replacements={};
        t0=datetime.utcnow().replace(tzinfo=timezone.utc)
        duration=timedelta(minutes=1);
        stale=t0+duration;

        replacements["[TIME]"] = self.__build_time_format(t0);
        replacements["[STALE]"] = self.__build_time_format(stale);
        replacements["[LAT]"] = "0.0";
        replacements["[LON]"] = "0.0";
        replacements["[UUID]"] = str(_uuid);

        return replacements

    def __hex_str_to_color(self,hex_str):
        v=int(hex_str,16);
        #print("v:%d"%(v,));
        s=v-(1<<32);
        #print("s:%d"%(s,));
        #print("%s - > %s"%(hex_str,str(s)));
        return str(s);

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
