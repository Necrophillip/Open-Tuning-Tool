import serial
import time
import sys

port = '/dev/cu.usbmodem0x80000001'
baud = 115200

try:
    ser = serial.Serial(port, baud, timeout=2)
    time.sleep(1)
    
    ser.write(b'#\n') # wake up CLI
    time.sleep(0.5)
    ser.read_all()
    
    print("Sending status...")
    ser.write(b'status\n')
    time.sleep(1)
    status_out = ser.read_all().decode('utf-8', errors='replace')
    
    print("Sending get gyro...")
    ser.write(b'get gyro\n')
    time.sleep(0.5)
    gyro_out = ser.read_all().decode('utf-8', errors='replace')
    
    print("Sending sensor_hardware...")
    ser.write(b'sensor_hardware\n')
    time.sleep(0.5)
    sensor_out = ser.read_all().decode('utf-8', errors='replace')
    
    print("Sending get sensor_hardware...")
    ser.write(b'get sensor_hardware\n')
    time.sleep(0.5)
    get_sensor_out = ser.read_all().decode('utf-8', errors='replace')

    with open('capture.txt', 'w') as f:
        f.write("=== STATUS ===\n" + status_out + "\n")
        f.write("=== GET GYRO ===\n" + gyro_out + "\n")
        f.write("=== SENSOR HARDWARE ===\n" + sensor_out + "\n")
        f.write("=== GET SENSOR HARDWARE ===\n" + get_sensor_out + "\n")
        
    print("Capture saved to capture.txt")
except Exception as e:
    print("Error:", e)
