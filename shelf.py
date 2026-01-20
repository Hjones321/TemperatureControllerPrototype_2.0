import time
from gpiozero import InputDevice, DigitalOutputDevice

from Logger import get_logger
logger = get_logger()

class Shelf():
    def __init__(self, relays: list, tempSensor:object, setTemp = 80) :
        
        #default temperature setpoint
        self.setTemp = setTemp
        
        self.maxTemp, self.minTemp = 95, 60

        #how much the temperature can go above or below the setpoint
        self.overtempAllowance, self.undertempAllowance = 0, -2
        
        #the actual values produced from the upper and lower allowance above
        self.lowerTempBound = self.setTemp + self.undertempAllowance
        self.upperTempBound = self.setTemp + self.overtempAllowance
        
        #lists to hold the temperature sensors and the relays
        self.tempSensor = tempSensor
        self.relayList = relays
        
        self.isOn = False
        
    def relaysOff(self):
        for relay in self.relayList:
            relay.off()

    def start(self):
        for relay in self.relayList:
            relay.on()



    def startupChecks(self, temp):
        #checks to see if the sensors are all receiving inputs

        startTemp = temp
        acceptanceDiff = 1
        

        

        #personally not a fan of this system, might be better with a current sensor
        for relay in self.relayList:
            #test that the relays work
            #if they do not return False
            relay.on()
            
        time.sleep(30)
        if self.tempSensor.read() < acceptanceDiff + startTemp:
            time.sleep(30)
            if self.tempSensor.read() < acceptanceDiff + startTemp:
                logger.error("[ERROR] relay error")
                return False
        

        

        logger.debug("relay working")
        return True
        
    def setNewTemp(self, newTemp: int):
        if newTemp > self.maxTemp:
            newTemp = self.maxTemp
        elif newTemp < self.minTemp:
            newTemp = self.minTemp
        self.setTemp = newTemp
        self.upperTempBound = self.setTemp + self.overtempAllowance
        self.lowerTempBound = self.setTemp + self.undertempAllowance

    def shelfToggle(self):
        if not self.isOn:
            self.isOn = True
            self.start()

        else:
            self.isOn = False
            self.relaysOff()
        
    def control(self, temp):
        if self.isOn:    
            #if temperature goes above the upper bound, it turns the heating element off
            if temp > self.upperTempBound:
                for relay in self.relayList:
                    if relay.name() == "element":
                        relay.off()

            #if the temperature goes below the lower bound, it turns the heating elements on
            elif temp < self.lowerTempBound:
                for relay in self.relayList:
                    if relay.name() == "element":
                        relay.on()