import socket
import time
from mpu6050 import mpu6050
from sklearn.linear_model import LogisticRegression
import pickle
import numpy as np

# Initialize the MPU6050
mpu = mpu6050(0x68)

SERVER_IP = ''
SERVER_PORT = 3002

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((SERVER_IP, SERVER_PORT))
s.listen(5)

state_size = 90

print('Server is now running.')

# Load the model from the file
with open('model.pkl', 'rb') as file:
    model = pickle.load(file)
print("Model loaded.")

def data_collector(state):
    # Get accelerometer data
    acc_data = mpu.get_accel_data()
    # Get gyroscope data
    gyro_data = mpu.get_gyro_data()
    
    acc_x = acc_data['x']   
    acc_y = acc_data['y']
    acc_z = acc_data['z'] 
    gyro_x = gyro_data['x']   
    gyro_y = gyro_data['y']
    gyro_z = gyro_data['z']
    
    state += [acc_x, acc_y, gyro_z]
    if (len(state) > state_size):
        state = state[3:]
        
    if (len(state) == state_size):
        probability = model.predict_proba(np.array(state).reshape(1, -1))[0][1]
        message = f"{probability:.2f}"
        print(message)
        client_socket.send(bytes(message, "utf-8"))
        
    time.sleep(.1)
    data_collector(state)
        
state = []
while True:
    client_socket, address = s.accept()
    print(f"Connection from {address} has been established.")
    data_collector(state)
