#!/usr/bin/env python

# Import libraries
import socketio
import eventlet
from flask import Flask
import numpy as np
from multiprocessing.shared_memory import SharedMemory
import struct
import autodrive

################################################################################

# Create a shared memory with a name
shared_mem = SharedMemory(name='AutoDRIVE', size=1024, create=True)

# Initialize environment
environment = autodrive.Environment()

# Initialize vehicle(s)
opencav_1 = autodrive.OpenCAV()
opencav_1.id = 'V1'

# Initialize the server
sio = socketio.Server()

# Flask (web) app
app = Flask(__name__) # '__main__'

# Registering "connect" event handler for the server
@sio.on('connect')
def connect(sid, environ):
    print('Connected!')

# Registering "Bridge" event handler for the server
@sio.on('Bridge')
def bridge(sid, data):
    try:
        if data:
            
            ########################################################################
            # PERCEPTION
            ########################################################################

            # Vehicle data
            opencav_1.parse_data(data, verbose=False)

            ########################################################################
            # PLANNING
            ########################################################################

            DTC = np.linalg.norm(opencav_1.position - np.array([-242.16, -119.00, 341.91])) # Compute DTC
            shared_mem.buf[36:44] = struct.pack('d', DTC) # Pack the float to bytes ('d' is for double-precision (64-bit) float

            # Print data in shared memory
            print("THROTTLE : ", struct.unpack('d', shared_mem.buf[0:8])[0])   # Unpack the bytes to float
            print("STEERING : ", struct.unpack('d', shared_mem.buf[9:17])[0])  # Unpack the bytes to float
            print("BRAKE    : ", struct.unpack('d', shared_mem.buf[18:26])[0]) # Unpack the bytes to float
            print("HANDBRAKE: ", struct.unpack('d', shared_mem.buf[27:35])[0]) # Unpack the bytes to float
            print("DTC      : ", struct.unpack('d', shared_mem.buf[36:44])[0]) # Unpack the bytes to float 

            ########################################################################
            # CONTROL
            ########################################################################

            # Environmental conditions
            environment.auto_time = "False" # ["False", "True"]
            environment.time_scale = 60 # [0, inf) (only used if auto_time==True)
            environment.time_of_day = 560 # [minutes in 24 hour format] (only used if auto_time==False)
            environment.weather_id = 3 # [0=Custom, 1=Sunny, 2=Cloudy, 3=LightFog, 4=HeavyFog, 5=LightRain, 6=HeavyRain, 7=LightSnow, 8=HeavySnow]
            environment.cloud_intensity = 0.0 # [0, 1] (only used if weather_id==0)
            environment.fog_intensity = 0.0 # [0, 1] (only used if weather_id==0)
            environment.rain_intensity = 0.0 # [0, 1] (only used if weather_id==0)
            environment.snow_intensity = 0.0 # [0, 1] (only used if weather_id==0)

            # Co-simulation mode
            opencav_1.cosim_mode = 0
            
            # Actuator commands (only if cosim_mode==0)
            opencav_1.throttle_command  = struct.unpack('d', shared_mem.buf[0:8])[0]/100   # Unpack the bytes to float
            opencav_1.steering_command  = struct.unpack('d', shared_mem.buf[9:17])[0]/100  # Unpack the bytes to float
            opencav_1.brake_command     = struct.unpack('d', shared_mem.buf[18:26])[0]/100 # Unpack the bytes to float
            opencav_1.handbrake_command = struct.unpack('d', shared_mem.buf[27:35])[0]/100 # Unpack the bytes to float

            # Light commands
            opencav_1.headlights_command = 0 # Vehicle headlights command [0 = Disabled, 1 = Low Beam, 2 = High Beam, 3 = Parking Lights, 4 = Fog Lights, 5 = 1+3, 6 = 1+4, 7 = 2+3, 8 = 2+4, 9 = 3+4, 10 = 1+3+4, 11 = 2+3+4]
            if opencav_1.collision_count > 0:
                opencav_1.indicators_command = 3 # Vehicle indicators command [0 = Disabled, 1 = Left Turn Indicator, 2 = Right Turn Indicator, 3 = Hazard Indicators]
            else:
                opencav_1.indicators_command = 0 # Vehicle indicators command [0 = Disabled, 1 = Left Turn Indicator, 2 = Right Turn Indicator, 3 = Hazard Indicators]
            
            ########################################################################

            json_msg = environment.generate_commands(verbose=False) # Generate environment message
            json_msg.update(opencav_1.generate_commands(verbose=False)) # Append vehicle 1 message

            try:
                sio.emit('Bridge', data=json_msg)
            except Exception as exception_instance:
                print(exception_instance)
    
    except KeyboardInterrupt:
        # Close the shared memory
        shared_mem.close()

        # Destroy the shared memory
        shared_mem.unlink()

################################################################################

if __name__ == '__main__':
    app = socketio.Middleware(sio, app) # Wrap flask application with socketio's middleware
    eventlet.wsgi.server(eventlet.listen(('', 4567)), app) # Deploy as an eventlet WSGI server
