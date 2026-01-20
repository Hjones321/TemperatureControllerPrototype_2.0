from gpiozero import InputDevice, DigitalOutputDevice
from ADSReader import ADSReader
import time
from shelf import Shelf
from relay import Relay
import serial

from Logger import get_logger
logger = get_logger()

class DeviceManager():
    
    def __init__(self):
        self.shelves = []
        self.unitOn = True
        self.adsReader = ADSReader(0x48,1,3.3)
        self.adsReader.addThermistor(0)
        self.relayList= [[Relay(16, "element"), Relay(26, "fan")]]


    def addShelves(self, shelf):
        self.shelves.append(shelf)
        

    def startupChecks(self):
        #ads test here

        for channel, shelf in enumerate(self.shelves):
            validCheck = shelf.startupChecks(self.adsReader.readTemperature(channel))
            if validCheck == False:
                logger.critical("[CRITICAL] System failed startup checks - Shutting Down ")
                self.systemShutdown()


    def systemShutdown(self):
        self.unitOn = False
        fanList = []
        fanCooldownTime = 30 #seconds

        for shelf in self.shelves:
            for relay in shelf.relayList:
                if relay.name() == "element":
                    relay.off()
                elif relay.name() == "fan":
                    relay.on()
                    fanList.append(relay)

        time.sleep(fanCooldownTime)

        for fan in fanList:
            fan.off()


    def allOff(self):
        self.queue.put({"command": "allOff"})
        for shelf in self.shelves:
            shelf.relaysOff()
 
    def addAllShelves(self, shelves):
        for i in range(0, shelves):
            self.addShelves(Shelf(self.relayList[i], self.adsReader))
    
    def controlLoop(self):
        #self.startupChecks()
        
        
        
        for channel, shelf in enumerate(self.shelves):
            temp = self.adsReader.readTemperature(channel)
            #shelf.control(temp)
            
            return temp



    
