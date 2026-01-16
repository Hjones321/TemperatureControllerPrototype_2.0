from gpiozero import InputDevice, DigitalOutputDevice
import time

import adafruit_ads1x15.ads1115 as ADS1115
import adafruit_ads1x15.ads1x15 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import board,  busio
import math

import logging
logger= logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class ADSReader:
    def __init__(self, address, gain, vcc):
        
        
        self.vcc = vcc
        self.gain = gain
        self.address = address



        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.ads = ADS1115.ADS1115(self.i2c, address=address)
        self.ads.gain = gain

        self.sensors = {}
        
        self.channels = {
            0: AnalogIn(self.ads, 0),
            1: AnalogIn(self.ads, 1),
            2: AnalogIn(self.ads, 2),
            3: AnalogIn(self.ads, 3)
        }
        
        
    def addThermistor(self, channel, rFixed=10000, r0=10000, beta=3950, t0_c=25):
        self.sensors[channel] = {
            "r_fixed": rFixed,
            "r0": r0,
            "beta": beta,
            "t0_k": t0_c + 273.15
        }
        
        
        
    def readVoltage(self,channel):
        return self.channels[channel].voltage
    
    def readResistance(self, channel):
        vOut = self.readVoltage(channel)
        cfg = self.sensors[channel]



        #stops dividing by zero
        if vOut <=0.001 or vOut >= self.vcc:
            return None
        

        rFixed = cfg["r_fixed"]
        return rFixed * (vOut / (self.vcc - vOut))

    def readTemperature(self, channel):

        if channel not in self.sensors:
            logger.error(f"[ERROR] Channel {channel} has no thermistor configured")
        
        r = self.readResistance(channel)
        
        if r is None:
            return None
        
        cfg = self.sensors[channel]
        r0 = cfg["r0"]
        beta = cfg["beta"]
        t0 = cfg["t0_k"]

        tempK = 1/ (1/t0 + (1/beta) * math.log(r/r0))
        return tempK - 273.15
    
    def readAll(self):

        temps = {}
        for sensor in self.sensors:
            temps[sensor] = self.readTemperature(sensor)

        return temps
