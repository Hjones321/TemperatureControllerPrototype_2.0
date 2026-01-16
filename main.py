import time
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from deviceManager import DeviceManager as deviceManager
import serial

PORT = "/dev/ttyACM0"
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=0.1)
time.sleep(2)

print("[CONNECTION SUCCESS]")

def send(msg):
    ser.write((msg+ "\n").encode())
    
def read():
    while ser.in_waiting:
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            handle(line)
            
def handle(msg):
    if msg.startswith("SET:"):
        setpoint = int(msg.split(":")[1])
        print(f"[SETPOINT UPDATED] new setpoint: {setpoint}")

running = True


def setupLogging():
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()


    logFormat = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s: %(message)s')

    #writes to the console
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormat)
    consoleHandler.setLevel(logging.DEBUG)
    logger.addHandler(consoleHandler)

    #error only file 
    errorFileHandler = logging.FileHandler("errors.log")
    errorFileHandler.setFormatter(logFormat)
    errorFileHandler.setLevel(logging.ERROR)
    logger.addHandler(errorFileHandler)
    

    


    logging.basicConfig(
            filename="log.txt",
            level=logging.DEBUG,
            format= '%(asctime)s - %(levelname)s - %(name)s: %(message)s',
            handlers= [
                logging.FileHandler('log.txt'),
                logging.StreamHandler(),
                RotatingFileHandler("log.txt", maxBytes=5_000_000, backupCount=7)
            ]
        )
    return logger


def mainLoop():
    dm = deviceManager()
    dm.addAllShelves(1)
    while running:
        read()
        time.sleep(1)
        temp = dm.controlLoop()
        send(f"LIVE_TEMP:{temp}")

    
def main(args):
    logger = setupLogging()
    mainLoop()
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))

