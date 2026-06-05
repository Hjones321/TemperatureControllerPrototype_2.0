import time
from Logger import get_logger
from deviceManager import DeviceManager as deviceManager
import threading
from evdev import ecodes
import evdev
from dotenv import load_dotenv
import os
import uuid as _uuid
import hashlib
from mqttCluster import MQTTHandler
import queue


from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS





load_dotenv(os.path.join(os.path.dirname(__file__),"config.env"))

logger = get_logger()
barcodeQueue = queue.Queue()
laptopJustConnected = False
scannerConnected = False
shelfStates = []

BROKER = os.environ.get("MQTT_BROKER")
PORT= 8883
USER = os.environ.get("MQTT_USER")
PASS = os.environ.get("MQTT_PASS")
STORE_ID = os.environ.get("STORE_ID", "00001")

def _derive_serial():
    mac = _uuid.getnode()
    h = hashlib.sha256(mac.to_bytes(6, byteorder='big')).hexdigest().upper()
    return f"{h[0:6]}.{h[6:9]}-{h[9:16]}-{h[16:21]}"

SERIAL_NUM = os.environ.get("SERIAL_NUM") or _derive_serial()

INFLUX_URL = os.environ.get("INFLUX_URL")
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN")
INFLUX_ORG = os.environ.get("INFLUX_ORG")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET")

influxClient = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
writeApi = influxClient.write_api(write_options=SYNCHRONOUS)

def logTemps(temps):
    for i, temp in enumerate(temps):
        if temp is not None:
            point = (
                Point("Temperature")
                .tag("shelf", f"shelf_{i+1}")
                .field("value", round(float(temp), 2))
            )
            writeApi.write(bucket=INFLUX_BUCKET, record=point)

def onPiCommand(msg):
    typ = msg.get("type")

    if typ == None:
        logger.warning("Pi receieved command with no type")
        return
    
    try:
        if typ == "SET":
            indx = msg["shelfIndex"]
            dm.shelves[indx].setNewTemp(msg["setpoint"])

            a, b, c = dm.shelves[indx].getSetpoints()
            mqtt.publishSetpoint(indx, a,b,c, qos=1)
            logger.info(f"new setpoint - {msg['setpoint']} - for shelf - {indx + 1}")
        
        elif typ == "RESET":
            shelfIndex = msg.get("shelfIndex")
            if shelfIndex is not None:
                shelf = dm.shelves[shelfIndex]
                for alarm in shelf.alarmList.values():
                    alarm.clear(override= True)
                dm.start()
                shelf.turnOn(manual=True)
                logger.info(f"Shelf {shelfIndex+1} reset and restarted")
            else:
                for i, shelf in enumerate(dm.shelves):
                    shelf = dm.shelves[i]
                    for alarm in shelf.alarmList.values():
                        alarm.clear(override= True)
                    shelf.turnOn(manual=True)
                dm.start()
                logger.info("Full system reset")


        elif typ == "SHELF_COUNT":
            logger.info(f"SHELF_COUNT received - shelf {msg['shelfIndex']+1}, count {msg['count']}")
            indx = msg["shelfIndex"]
            count = msg["count"]

            shelf = dm.shelves[indx]

            
            hasCritical = False
            for a in shelf.alarmList.values():
                if a.severity == "critical" and a.isActive():
                    logger.debug("Critical alarm - hasCritical set to TRUE")
                    hasCritical = True
            
            if count > 0 and not shelf.isOn and not hasCritical and dm.unitOn:
                shelf.turnOn()
                shelf.setLight(True)
                logger.info(f"{count} items loaded onto shelf {indx+1}")
                onEspConnect()
            
            elif count > 0 and (not dm.unitOn or hasCritical):
                onEspConnect()

            elif count == 0 and shelf.isOn:
                shelf.turnOff()
                shelf.setLight(False)
                logger.info(f"Shelf {indx+1} turning off - no items remaining")
                onEspConnect()

            



        elif typ == "LIGHT":
            dm.shelves[msg["shelfIndex"]].setLight(msg["on"] == 1)
            logger.info(f"Light command: shelf {msg['shelfIndex']+1} -> {'on' if msg['on'] == 1 else 'off'}")
        elif typ == "ACK":
            dm.shelves[msg["shelfIndex"]].alarmList[msg["alarmName"]].ack()
            
        elif typ == "TRIGGER":
            dm.shelves[msg["shelfIndex"]].alarmList[msg["alarmName"]].trigger(override=True)
        elif typ == "CLEAR":
            dm.shelves[msg["shelfIndex"]].alarmList[msg["alarmName"]].clear(override= True)
            
        elif typ == "POWER":
            
            if msg["on"] == 1:
                if dm.unitOn:
                    dm.shelves[msg["shelfIndex"]].turnOn(manual= True)
                else:
                    onEspConnect()
                    
            else:
                dm.shelves[msg["shelfIndex"]].turnOff(manual= True)
            logger.info(f"Power command: shelf {msg['shelfIndex']+1} -> {'on' if msg['on'] == 1 else 'off'}")
        
    except Exception as e:
        logger.warning(f"exception in onPiCommand() - {e}")



def onLaptopConnect():
    global laptopJustConnected
    global lastLogPosition
    if dm is None:
        return
    lastLogPosition = 0
    laptopJustConnected = True
    logger.info("Laptop came online - republishing data")
    def sendAlarms():
        time.sleep(1)
        alarms = dm.getActiveAlarms()
        for shelfIndex, alarmList in alarms.items():
            for alarm in alarmList:
                mqtt.publishAlarm(shelfIndex, alarm)
    threading.Thread(target=sendAlarms, daemon=True).start()

def onEspConnect():
    if dm is None:
        return
    
    logger.info("ESP came online - republishing state")
    for i, shelf in enumerate(dm.shelves):
        a, b, c = dm.shelves[i].getSetpoints()
        mqtt.publishSetpoint(i, a,b,c,qos=1)
        mqtt.publishLight(i, shelf.getLight())
        mqtt.publishOnOff(i, 1 if shelf.isOn else 0)
    


mqtt = MQTTHandler(
    messageHandler=onPiCommand,
    onEspConnect=onEspConnect,
    onLaptopConnect=onLaptopConnect,
    broker=BROKER,
    port=PORT,
    username=USER,
    password=PASS,
    storeId=STORE_ID,
    serialNum=SERIAL_NUM,
)

KEYMAP = {
    2: '1', 3: '2', 4: '3', 5: '4', 6: '5',
    7: '6', 8: '7', 9: '8', 10: '9', 11: '0',
    16: 'q', 17: 'w', 18: 'e', 19: 'r', 20: 't',
    21: 'y', 22: 'u', 23: 'i', 24: 'o', 25: 'p',
    30: 'a', 31: 's', 32: 'd', 33: 'f', 34: 'g',
    35: 'h', 36: 'j', 37: 'k', 38: 'l', 44: 'z',
    45: 'x', 46: 'c', 47: 'v', 48: 'b', 49: 'n',
    50: 'm', 12: '-',
}

def barcodeReader():
    global scannerConnected

    while True:
    
        try:
            dev = evdev.InputDevice('/dev/input/event5')
            dev.grab()
        except FileNotFoundError:
            logger.debug("Barcode scanner not found at /dev/input/event5")
            time.sleep(10)
            continue
        except Exception as e:
            logger.warning(f"failed to connect scanner - {e}")
            time.sleep(10)
            continue
        
        scannerConnected = True
        current = []
        shift = False

        try:

            for event in dev.read_loop():
                if event.type != ecodes.EV_KEY:
                    continue

                data = evdev.categorize(event)

                # track shift state
                if data.scancode == 42:  # KEY_LEFTSHIFT
                    shift = data.keystate == 1
                    continue

                if data.keystate != 1:  # only key down
                    continue

                if data.scancode == 28:
                    if current:
                        scanned = ''.join(current)
                        logger.debug(f"scanned: {scanned}")
                        barcodeQueue.put(scanned)
                    current = []  # ← make sure this is OUTSIDE the if current: block
                    shift = False
                    continue

                if data.scancode in KEYMAP:
                    char = KEYMAP[data.scancode]
                    if shift:
                        char = char.upper()
                    current.append(char)
        except Exception as e:
            logger.warning(f"Exception in barcode loop - {e}")
            continue




def simulateError(shelf: int, name: str):
    dm.shelves[shelf-1].alarmList[name.upper()].trigger()

def acknowledgeAlarm(shelf: int, name: str):
    dm.shelves[shelf-1].alarmList[name.upper()].ack()
    
    
def clearAlarm(shelf: int, name: str):
    dm.shelves[shelf - 1].alarmList[name.upper()].clear()
        

dm = None
def getStatus():
    
    latestTemps = dm.latestTemps
   

     #{0: [setpoint, upper alarm, lower alarm], 2: [setpoint, upper alarm, lower alarm]}
    onOffStatus = dm.getActives() # [False, True, True]
    
    maxFanLife, maxElementLife = 8820, 8820 #365 days, 2 years, 12 hours a day


    shelves = [
    {
        "shelf": int(i+1),
        "temp": latestTemps[i] if latestTemps[i] is not None else -999,
        
        "hours": dm.shelves[i].getRelayLife(), #fan, element
        "systemOn": onOffStatus[i],
        "elementOn": dm.shelves[i].elementTurnedOn is not None

    }
    for i in range(0, len(dm.shelves))]

    return {
        "type": "STATUS",
        "shelves": shelves,
        "maintenance": [maxFanLife, maxElementLife]
    }





#log the cleaning times


def mainLoop():
    global dm, laptopJustConnected, shelfStates, scannerConnected, lastLogPosition

    dm = deviceManager()
    dm.addAllShelves(2)
    dm.start()
    dm.setSetpointCallback(mqtt.publishSetpoint)
    for shelf in dm.shelves:
        shelf.setAlarmCallback(mqtt.publishAlarm)

    
    t = threading.Thread(target=barcodeReader, daemon= True)
    t.start()
    logger.debug("Barcode input handler thread started")
    time.sleep(2)
    lastSave = time.time()

    lastLogPosition = 0
    shelfStates = dm.getShelfStates()


    try:
        while True:
            
            try:
                while not barcodeQueue.empty():
                    val = barcodeQueue.get_nowait()
                    mqtt.publishBarcode(val, None, "LOAD", qos=1)


            except Exception as e:
                logger.debug(f"Exception in barcode runtime - {e}")
            

            
            
            
            dm.controlLoop()
            logTemps(dm.latestTemps)
            
            
            mqtt.publishStatus(getStatus())
            
           
            for i, shelf in enumerate(dm.shelves):

                mqtt.publishLiveTemp(i, dm.getTemp(i))
                a, b, c = dm.shelves[i].getSetpoints()
                mqtt.publishSetpoint(i, a,b,c, qos=0)

                currentStates = dm.getShelfStates()
                if currentStates != shelfStates:
                    mqtt.publishOnOff(i, 1 if shelf.isOn else 0)
                    shelfStates = currentStates

            if time.time() - lastSave >= 60:
                
                dm.saveShelfStates()
                lastSave = time.time()

            if laptopJustConnected:
                lastLogPosition = mqtt.publishLogs("logs/app.log",0)
                laptopJustConnected = False

            lastLogPosition = mqtt.publishLogs("logs/app.log", lastLogPosition)

            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("ctrl+c pressed - saving and exiting")

    finally:
        dm.saveShelfStates()
    
def main(args):
    logger.debug("Main loop started")
    mainLoop()
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))

