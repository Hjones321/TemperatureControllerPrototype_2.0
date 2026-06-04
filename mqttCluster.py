from paho.mqtt import client as mqtt
import time, ssl, json
from Logger import get_logger
import threading
import os

from datetime import datetime


class MQTTHandler:
    logger = get_logger()
    def __init__(self, messageHandler, onEspConnect,onLaptopConnect, broker, port, username, password, ws=False):
        self.messageHandler = messageHandler
        self.port = port
        self.broker = broker
        self.username = username
        self.password = password
        

        if ws:
            self.client = mqtt.Client(client_id="pi_controller",transport="websockets")
            self.client.ws_set_options(path="/mqtt")
        else:
            self.client = mqtt.Client(client_id="pi_controller")
        self.client.max_queued_messages_set(100)

        self.client.username_pw_set(self.username, self.password)
        
        self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.client.tls_insecure_set(False)

        self.client.on_connect = self.onConnect
        self.client.on_message = self.onMessage
        self.client.on_disconnect = self.onDisconnect

        self.onLaptopConnect = onLaptopConnect
        self.onEspConnect = onEspConnect

        self.client.will_set("pi/system_state", payload=json.dumps({"online": False}), qos=1, retain=True)

        try:
            self.client.connect(self.broker, self.port, keepalive=60)
            
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker {self.broker}: {e}")
        
        
        self.client.loop_start()
    
    def onConnect(self, client, userdata, flags, rc):
        self.logger.info(f"[MQTT] connected with code {rc}")
        client.publish("pi/system_state", json.dumps({"online": True}), qos=1, retain=True)

        # subscribe to commands from laptop/dashboard
        client.subscribe("laptop/cmd")
        client.subscribe("esp/set_temp")
        client.subscribe("esp/light")
        client.subscribe("esp/setpoint")
        client.subscribe("esp/on_off")
        client.subscribe("laptop/system_state")
        client.subscribe("esp/system_state")
        self.logger.info("[MQTT] Subscribed to all alarm topics")

    def onDisconnect(self, client, userdata, rc):
        if rc != 0:
            self.logger.warning("[MQTT] unexpected disconnect")

    def onMessage(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            if msg.topic == "laptop/system_state":
                if data.get("online") and self.onLaptopConnect:
                    self.onLaptopConnect()
            elif msg.topic == "esp/system_state":
                if data.get("online") and self.onEspConnect:
                    self.onEspConnect()
            else:
                if self.messageHandler:
                    self.messageHandler(data)
                
            

            
        except Exception as e:
            self.logger.debug(f"[MQTT] Bad MQTT message: {e}")

    

    def publishStatus(self, statusDict, qos=0):
        self.client.publish("pi/status", json.dumps(statusDict), qos=qos, retain=False)

    def publishLiveTemp(self, shelf, temp, qos=0):
        offset = 5
        self.client.publish("pi/live_temp", json.dumps({"shelf": shelf, "temp": temp}), qos=qos, retain=False)

    def publishBarcode(self, barcode, shelf=None, action="LOAD", qos=0):
        self.client.publish("pi/barcode", json.dumps({"sku": barcode, "action": action, "shelf": shelf}), qos=qos, retain=False)

    def publishOnOff(self, shelfIndex, onOff: int, qos=0):
        self.client.publish("pi/onOff", json.dumps([shelfIndex, onOff]), qos=qos, retain= False)

    def publishLight(self, shelfIndex, lightOnOff: int, qos=0):
        self.client.publish("pi/light", json.dumps([shelfIndex, lightOnOff]), qos=qos, retain= False)
    
    def publishLogs(self, logdir, lastPosition=0, qos=0):
        


        try: 
            currentSize = os.path.getsize(logdir)

            if currentSize < lastPosition:
                self.logger.info("Log file rotated, resetting position")
                lastPosition = 0

        
            with open(logdir, "r") as f:
                f.seek(lastPosition)
                newLines = f.readlines()
                newPosition = f.tell()

            newLines = [l.strip() for l in newLines if l.strip()]
            newLines = newLines[:50]

            if newLines:
                self.client.publish("pi/logs", json.dumps(newLines), qos=qos)

            return newPosition
        except Exception as e:
            self.logger.warning(f"Failed to publish logs - {e}")
            return lastPosition
            
        
    def publishSetpoint(self, shelfIndex, setpoint, upper, lower, qos=0):
        self.client.publish("pi/setpoint", json.dumps([shelfIndex, setpoint, upper, lower]), qos=qos, retain=False)


    def publishAlarm(self, shelfIndex, alarm, qos=1):
        payload = {
            "shelf": shelfIndex,
            "name": alarm.name,
            "active": alarm.isActive(),
            "acknowledged": alarm.acknowledged,
            "severity": alarm.severity,
            "description": alarm.description,
            "timestamp": alarm.timestamp,
            "clearedTimestamp": alarm.clearedTimestamp
        }
        self.client.publish("pi/alarms", json.dumps(payload), qos=qos, retain=False)