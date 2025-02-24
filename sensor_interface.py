import serial
import numpy as np
import time

class GyroSensor:
    def __init__(self, port='COM3', baud_rate=115200):
        try:
            self.serial = serial.Serial(port, baud_rate, timeout=1)
            self.connected = True
            print(f"Successfully connected to {port}")
        except serial.SerialException as e:
            print(f"Warning: Could not connect to port {port}: {str(e)}")
            self.connected = False
            self.t = 0
            
    def read_angles(self):
        if self.connected:
            try:
                data = self.serial.readline()
                return self.parse_angles(data)
            except serial.SerialException:
                return self.generate_test_angles()
        else:
            return self.generate_test_angles()
            
    def read_encoders(self):
        if self.connected:
            try:
                data = self.serial.readline()
                return self.parse_encoders(data)
            except serial.SerialException:
                return self.generate_test_encoders()
        else:
            return self.generate_test_encoders()
        
    def parse_angles(self, raw_data):
        try:
            values = raw_data.decode().strip().split(',')
            return float(values[0]), float(values[1]), float(values[2])
        except:
            return 0.0, 0.0, 0.0
            
    def parse_encoders(self, raw_data):
        try:
            values = raw_data.decode().strip().split(',')
            return float(values[3]), float(values[4]), float(values[5])
        except:
            return 0.0, 0.0, 0.0
            
    def generate_test_angles(self):
        self.t += 0.01
        pitch = 45 * np.sin(2 * np.pi * 0.1 * self.t)
        roll = 30 * np.cos(2 * np.pi * 0.15 * self.t)
        yaw = (self.t * 10) % 360
        return pitch, roll, yaw
        
    def generate_test_encoders(self):
        self.t += 0.01
        return ((self.t * 20) % 360,
                (self.t * 15) % 360,
                (self.t * 25) % 360) 
        
    def disconnect(self):
        if self.connected and hasattr(self, 'serial'):
            try:
                self.serial.close()
            except:
                pass
            self.connected = False
            print("Disconnected from serial port") 