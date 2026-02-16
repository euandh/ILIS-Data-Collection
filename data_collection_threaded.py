"""
ELECTROSPRAY CONTROL AND DATA COLLECTION PROGRAM

┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│███████╗██╗     ███████╗ ██████╗████████╗██████╗  ██████╗ ███████╗██████╗ ██████╗  █████╗ ██╗   ██╗│
│██╔════╝██║     ██╔════╝██╔════╝╚══██╔══╝██╔══██╗██╔═══██╗██╔════╝██╔══██╗██╔══██╗██╔══██╗╚██╗ ██╔╝│
│█████╗  ██║     █████╗  ██║        ██║   ██████╔╝██║   ██║███████╗██████╔╝██████╔╝███████║ ╚████╔╝ │
│██╔══╝  ██║     ██╔══╝  ██║        ██║   ██╔══██╗██║   ██║╚════██║██╔═══╝ ██╔══██╗██╔══██║  ╚██╔╝  │
│███████╗███████╗███████╗╚██████╗   ██║   ██║  ██║╚██████╔╝███████║██║     ██║  ██║██║  ██║   ██║   │
│╚══════╝╚══════╝╚══════╝ ╚═════╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   │
│                                                                                                   │
│██████╗  █████╗ ████████╗ █████╗     ██╗      ██████╗  ██████╗  ██████╗ ███████╗██████╗            │
│██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗    ██║     ██╔═══██╗██╔════╝ ██╔════╝ ██╔════╝██╔══██╗           │
│██║  ██║███████║   ██║   ███████║    ██║     ██║   ██║██║  ███╗██║  ███╗█████╗  ██████╔╝           │
│██║  ██║██╔══██║   ██║   ██╔══██║    ██║     ██║   ██║██║   ██║██║   ██║██╔══╝  ██╔══██╗           │
│██████╔╝██║  ██║   ██║   ██║  ██║    ███████╗╚██████╔╝╚██████╔╝╚██████╔╝███████╗██║  ██║           │
│╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝    ╚══════╝ ╚═════╝  ╚═════╝  ╚═════╝ ╚══════╝╚═╝  ╚═╝           │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘

This program is designed to collect and record the live data from electrospray
test set-up. This is also designed to allow the inputting of the desired 
control voltage.

You will need to have the ThorCam software installed for this to work for
the camera connectivity.

Created on Thu Feb 12 14:53:11 2026

@author: euandh
"""

# Generic Python Libraries
import numpy as np
import time
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QComboBox, QLineEdit,
                             QDoubleSpinBox, QSpinBox, QTextEdit, QFileDialog,
                             QGroupBox)
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot

# National Instruments Libraries
import nidaqmx
from nidaqmx.constants import AcquisitionType, READ_ALL_AVAILABLE
from nidaqmx import stream_readers
from nidaqmx import stream_writers
from nidaqmx import constants

# ThorLabs and Camera/Image Libraries
import windows_setup   # This is Thorlabs windows set-up code    
import tifffile
from thorlabs_tsi_sdk.tl_camera import TLCameraSDK
from thorlabs_tsi_sdk.tl_mono_to_color_processor import MonoToColorProcessorSDK
from thorlabs_tsi_sdk.tl_camera_enums import SENSOR_TYPE
import imagecodecs

# --- WORKER THREAD 1: CAMERA CONTROL ---
class CameraWorker(QThread):
    # Signals to send data back to the GUI
    image_ready = pyqtSignal(object)  # Sends the image array
    log_message = pyqtSignal(str)     # Sends text logs
    
    def __init__(self):
        super().__init__()
        self.is_running = False
        
        # Initialise control variables (with some default values)
        self.camera_fps = 10
        self.filepath = ""
        self.ROI = [4096, 3000]
        self.trigger_mode = "Software" # Default

    def run(self):
        """This runs when you call worker.start()"""
        self.is_running = True
        self.log_message.emit("Camera: Initializing SDK...")

        # --- [INSERT YOUR THORLABS SETUP CODE HERE] ---
        # sdk = TLCameraSDK()
        # camera = sdk.open_camera(...)
        # camera.arm(10)
        
        self.log_message.emit(f"Camera: Armed in {self.trigger_mode} mode.")

        while self.is_running:
            try:
                # --- [INSERT YOUR FRAME CAPTURE CODE HERE] ---
                # frame = camera.get_pending_frame_or_null()
                
                # SIMULATION (Delete this block later)
                time.sleep(0.1) # Simulate 10 FPS
                fake_image = np.random.randint(0, 255, (1024, 1024), dtype=np.uint8)
                
                # Emit the data to the GUI
                self.image_ready.emit(fake_image)

                # --- [INSERT YOUR TIFF SAVING CODE HERE] ---
                # tiff.save(data=image_data, ...)

            except Exception as e:
                self.log_message.emit(f"Camera Error: {str(e)}")
                break

        # --- [INSERT YOUR TEAR DOWN CODE HERE] ---
        # camera.disarm()
        # camera.dispose()
        self.log_message.emit("Camera: Disconnected.")

    def stop(self):
        self.is_running = False
        self.wait() # Wait for the thread to finish safely


# --- WORKER THREAD 2: NI DAQ CONTROL ---
class DAQWorker(QThread):
    data_ready = pyqtSignal(float, float) # Sends (Voltage, Current)
    
    def __init__(self):
        super().__init__()
        self.is_running = False
        
        # Initialise set-up variables
        self.filepath = "data.csv"
        self.sample_rate = 4e-3 #time between samples in seconds
        
        # Initialise control variables and set default values.
        self.target_voltage = 0.0
        self.polarity_mode = 0
        self.high_time = 1 #dwell time in seconds

    def set_voltage(self, val):
        self.target_voltage = val
        
    def set_hightime(self, val):
        self.high_time = val
        
    def set_polarity_mode(self, val):
        self.polarity_mode = val

    def run(self):
        self.is_running = True
        
        # --- [INSERT YOUR NI SETUP CODE HERE] ---
        # ai_task = nidaqmx.Task() ...
        
        while self.is_running:
            # --- [INSERT YOUR NI READ/WRITE CODE HERE] ---
            # ai_task.read() ...
            # ao_task.write(self.target_voltage) ...
            
            # SIMULATION (Delete this later)
            time.sleep(self.sample_rate) # 20 Hz read rate
            read_volts = self.target_voltage
            read_current = read_volts / 1000 # Placeholder current
            
            self.data_ready.emit(read_volts, read_current)
            
        # --- [INSERT YOUR NI TEAR DOWN CODE HERE] ---
        # ai_task.stop() ...

    def stop(self):
        self.is_running = False
        self.wait()

# --- MAIN GUI WINDOW ---
class ElectrosprayUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Electrospray Control and Data Acquisition")
        self.resize(1200, 800)

        # 1. Setup UI Elements
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Control Panel
        controls_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("Start Acquisition")
        self.btn_start.clicked.connect(self.start_system)
        
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_system)

        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Current Collection Only",\
                                  "Camera and Current Collection"])

        controls_layout.addWidget(self.btn_start)
        controls_layout.addWidget(self.btn_stop)
        controls_layout.addWidget(self.combo_mode)
        self.layout.addLayout(controls_layout)
        
            # Set-up (static) variables
                # FPS
        self.input_fps = QDoubleSpinBox()
        self.input_fps_label = QLabel("Camera FPS:")
        self.input_fps_label.setBuddy(self.input_fps)
        self.layout.addWidget(self.input_fps_label)
        self.input_fps.setValue(10)
        self.input_fps.setRange(0, 914.4)
        self.layout.addWidget(self.input_fps)
        self.input_fps.setSuffix(" FPS")
        self.input_fps.setSingleStep(1)
                # ROI
        self.input_ROI_width, self.input_ROI_height  = QSpinBox(), QSpinBox()
        self.input_ROI_label = QLabel("Camera ROI :")
        self.input_ROI_label.setBuddy(self.input_ROI_width)
        self.layout.addWidget(self.input_ROI_label)
        self.input_ROI_width.setMaximum(4096)
        self.input_ROI_height.setMaximum(3000)
        self.input_ROI_width.setValue(4096)
        self.input_ROI_height.setValue(3000)
        self.input_ROI_width.setSuffix(" px")
        self.input_ROI_height.setSuffix(" px")
        self.layout.addWidget(self.input_ROI_width)
        self.layout.addWidget(self.input_ROI_height)
                # Filepath
        self.input_filepath = QLineEdit()
        self.input_filepath_label = QLabel("Filepath:")
        self.input_filepath_label.setBuddy(self.input_filepath)
        self.input_filepath.setPlaceholderText("Enter filepath to folder for data logging here...")
        self.input_filepath.setFixedHeight(30)
        self.layout.addWidget(self.input_filepath_label)
        self.layout.addWidget(self.input_filepath)
                # Create a filename linked to the booting time
        self.filenametime = time.strftime("ESPRAY_%Y-%m-%d_%H%M")
                # Sample rate
        self.input_sample_rate = QDoubleSpinBox()
        self.input_sample_rate_label = QLabel("Sample time:")
        self.input_sample_rate_label.setBuddy(self.input_sample_rate)
        self.layout.addWidget(self.input_sample_rate_label)
        self.input_sample_rate.setValue(40)
        self.input_sample_rate.setSuffix(" ms")
        self.input_sample_rate.setMinimum(0)
        self.input_sample_rate.setSingleStep(10)
        self.layout.addWidget(self.input_sample_rate)
        
        # Rolling inputs
            # Voltage Control Spinner
        self.voltage_spinner = QDoubleSpinBox()
        self.voltage_spinner_label = QLabel("Emitter voltage:")
        self.voltage_spinner_label.setBuddy(self.voltage_spinner)
        self.layout.addWidget(self.voltage_spinner_label)
        self.voltage_spinner.setSuffix(" V")
        self.voltage_spinner.setRange(-5000, 5000)
        self.voltage_spinner.setSingleStep(10)
        self.voltage_spinner.valueChanged.connect(self.update_DAQ_voltage)
        self.layout.addWidget(self.voltage_spinner)
            # High time
        self.input_high_time = QDoubleSpinBox()
        self.input_high_time_label = QLabel("Voltage high time:")
        self.input_high_time_label.setBuddy(self.input_high_time)
        self.layout.addWidget(self.input_high_time_label)
        self.input_high_time.setSuffix(" s")
        self.input_high_time.setMinimum(0)
        self.input_high_time.valueChanged.connect(self.update_DAQ_hightime)
        self.layout.addWidget(self.input_high_time)
            # Polarity mode
        self.input_polarity_mode = QComboBox()
        self.input_polarity_mode_label = QLabel("Polarity mode:")
        self.input_polarity_mode_label.setBuddy(self.input_polarity_mode)
        self.layout.addWidget(self.input_polarity_mode_label)
        self.input_polarity_mode.addItems(["Bipolar switching", "Unipolar switching", "Unipolar constant"])
        self.layout.addWidget(self.input_polarity_mode)
        self.input_polarity_mode.currentIndexChanged.connect(self.update_DAQ_polarity_mode)

        # Dashboard (Voltage Display)
        self.lbl_status = QLabel("System Ready")
        self.lbl_voltage = QLabel("Voltage: 0.00 V")
        self.layout.addWidget(self.lbl_status)
        self.layout.addWidget(self.lbl_voltage)

        # Log Window
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.layout.addWidget(self.log_box)

        # 2. Initialize Workers
        self.cam_worker = CameraWorker()
        self.daq_worker = DAQWorker()

        # 3. Connect Signals (Worker -> GUI)
        self.cam_worker.log_message.connect(self.append_log)
        self.cam_worker.image_ready.connect(self.update_image_display) # You need to write this function
        self.daq_worker.data_ready.connect(self.update_daq_display)

    def start_system(self):
        # UI Updates
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.combo_mode.setEnabled(False)
        self.append_log("System Starting...")
        
        # Lock inputs
        self.input_fps.setEnabled(False)
        self.input_filepath.setEnabled(False)
        self.input_polarity_mode.setEnabled(False)
        
        # Check if camera is in use
        if "Camera" in self.combo_mode.currentText():
            use_cam = True
            self.cam_worker.trigger_mode = "Hardware"
        else:
            use_cam = False
    
        # Pass settings to workers
            # Cam worker
        if use_cam == True:
            self.cam_worker.trigger_mode = self.combo_mode.currentText()
            self.cam_worker.filepath = f"{self.input_filepath.text()}/{self.filenametime}_IMAGES.tiff"
            self.cam_worker.ROI = [self.input_ROI_width.value(), self.input_ROI_height.value()]
            # Daq worker
        self.daq_worker.filepath = f"{self.input_filepath.text()}/{self.filenametime}_DATA.csv"
        
        self.inputted_fps = self.input_fps.value()
        self.inputted_filepath = self.input_filepath.text()
        
        # Start Threads
        self.daq_worker.start()
        if use_cam == True:
            self.cam_worker.start()

    def update_DAQ_voltage(self, value):
        self.daq_worker.set_voltage(value)
        
    def update_DAQ_hightime(self, value):
        self.daq_worker.set_hightime(value)
        
    def update_DAQ_polarity_mode(self, value):
        self.daq_worker.set_polarity_mode(value)

    def stop_system(self):
        self.append_log("Stopping...")
        self.cam_worker.stop()
        self.daq_worker.stop()
        
        # unlock inputs
        self.input_fps.setEnabled(True)
        self.input_filepath.setEnabled(True)
        self.input_polarity_mode.setEnabled(True)
        
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.combo_mode.setEnabled(True)

    @pyqtSlot(str)
    def append_log(self, text):
        self.log_box.append(text)

    @pyqtSlot(object)
    def update_image_display(self, image_array):
        # Here you would update a plot/image widget
        # For now, just print the shape to prove it works
        pass 

    @pyqtSlot(float, float)
    def update_daq_display(self, volts, amps):
        self.lbl_voltage.setText(f"Voltage: {volts:.2f} V | Current: {amps:.6f} A")

# --- APP ENTRY POINT ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ElectrosprayUI()
    window.show()
    sys.exit(app.exec())