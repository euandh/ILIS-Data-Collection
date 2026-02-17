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
import csv
import datetime

# GUI Libaries
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QComboBox, QLineEdit,
                             QDoubleSpinBox, QSpinBox, QTextEdit, QFileDialog,
                             QGroupBox, QGridLayout, QDialog, QFormLayout,
                             QDialogButtonBox)
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot, Qt

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
    log_message = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.is_running = False
        
        # Initialise set-up variables
        self.filepath = "data.csv"
        self.sample_rate = 4e-3 
        
        # Initialise control variables
        self.target_voltage = 0.0
        self.polarity_mode = 0
        self.high_time = 1 
        
        # Initialise modules
        self.ai_channel_name = "cDAQ9185-2023AF4Mod1"
        self.ao_channel_name = "cDAQ9185-2023AF4Mod2"
        self.ai_channels_to_use = [0, 1]
        self.ao_channels_to_use = [0]
        self.ai_lims = [-10, 10]
        self.ao_lims = [-10, 10]
        
        # Define channels for purposes
        self.ai_channel_assignments = {
                                      "Matsusada": 0  
                                      }

    def set_voltage(self, val):
        self.target_voltage = val
        
    def set_hightime(self, val):
        self.high_time = val
        
    def set_polarity_mode(self, val):
        self.polarity_mode = val

    def run(self):
        self.is_running = True
        
        # Create NI Tasks
        self.ai_task = nidaqmx.Task()
        self.ao_task = nidaqmx.Task()

        try:
            # Setup Channels
            for i in self.ai_channels_to_use:
                self.ai_task.ai_channels.add_ai_voltage_chan(
                    f"{self.ai_channel_name}/ai{i}", 
                    min_val=self.ai_lims[0], max_val=self.ai_lims[1]
                )
            self.log_message.emit(f"AI channels {self.ai_channels_to_use} added.")

            for i in self.ao_channels_to_use:
                self.ao_task.ao_channels.add_ao_voltage_chan(
                    f"{self.ao_channel_name}/ao{i}", 
                    min_val=self.ao_lims[0], max_val=self.ao_lims[1]
                )
            self.log_message.emit(f"AO channels {self.ao_channels_to_use} added.")
            
            # Create File Header
            with open(self.filepath, mode='w', newline='') as f:
                csv.writer(f).writerow(["Timestamp", "Requested Voltage", "Applied Voltage", "Collected Current"])
            
            # Main Loop
            with open(self.filepath, mode='a', newline='') as f:
                writer = csv.writer(f)
                
                while self.is_running:
                    # --- Update voltage to PSU --- 
                    self.ao_task.write([self.target_voltage/1000])
                    
                    
                    # --- Read/Write Logic ---
                    # Need to add actual .read() and .write() calls here eventually
                    read_volts = self.target_voltage
                    read_current = read_volts / 1000 
                    
                    # Write to open file
                    writer.writerow([datetime.datetime.now(), self.target_voltage, read_volts, read_current])
                    
                    time.sleep(self.sample_rate)
                    self.data_ready.emit(read_volts, read_current)

        except Exception as e:
            self.log_message.emit(f"DAQ Error: {e}")

        finally:
            # CLEANUP
            self.log_message.emit("Stopping DAQ tasks...")
            
            # Set AOs to zero
            try:
                self.ao_task.write([0])
            except:
                print("error lol")
            
            # Close AI
            try:
                self.ai_task.stop()
                self.ai_task.close() 
            except:
                pass
                
            # Close AO
            try:
                self.ao_task.stop()
                self.ao_task.close() 
            except:
                pass
                
            self.log_message.emit("DAQ resources released.")

    def stop(self):
        self.is_running = False
        self.wait()

# --- HARDWARE CONFIGURATION DIALOGUE ---
class HardwareConfigDialog(QDialog):
    def __init__(self, current_config, parent = None):
        super().__init__(parent)
        self.setWindowTitle("Hardware and Channel Settings")
        self.resize(400, 200)
        
        # Variable to store the configuration
        self.config = current_config
        
        self.layout = QFormLayout(self)
        
        # Inputs
            # AI Card
        self.input_device_ai = QLineEdit(self.config.get("ai_device", "cDAQ9185-2023AF4Mod1"))
        self.input_chans_ai = QLineEdit(self.config.get("ai_channels", "0, 1"))
        self.input_chans_ai.setPlaceholderText("e.g. 0, 1, 2")

        self.input_device_ao = QLineEdit(self.config.get("ao_device", "cDAQ9185-2023AF4Mod2"))
        self.input_chans_ao = QLineEdit(self.config.get("ao_channels", "0, 1"))
        
        self.layout.addRow("AI Device Name:", self.input_device_ai)
        self.layout.addRow("AI Channels (csv):", self.input_chans_ai)
        self.layout.addRow("AO Device Name:", self.input_device_ao)
        self.layout.addRow("AO Channels (csv):", self.input_chans_ao)

        # UI Buttons (OK | Cancel)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.save_and_close)
        self.buttons.rejected.connect(self.reject)
        self.layout.addRow(self.buttons)
        
    def save_and_close(self):
        # Update the dictionary with new values
        self.config["ai_device"] = self.input_device_ai.text()
        self.config["ao_device"] = self.input_device_ao.text()
        self.config["ai_channels"] = self.input_chans_ai.text()
        self.config["ao_channels"] = self.input_chans_ao.text()
        self.accept() # Closes window and returns "True" result

# --- MAIN GUI WINDOW ---
class ElectrosprayUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Electrospray Control and Data Acquisition")
        self.resize(1200, 800)

        # Start set-up of layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.centralWidget())

        # Row 1: Control box
        self.top_controls_group = QGroupBox("Global Controls")
        self.top_controls_group.setFixedHeight(80)
        self.controls_layout = QHBoxLayout()
        self.top_controls_group.setLayout(self.controls_layout)
        
            # Boxes
        self.btn_start = QPushButton("Start Acquisition")
        self.btn_start.clicked.connect(self.start_system)
        
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_system)

        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Current Collection Only",\
                                  "Camera and Current Collection"])

        self.controls_layout.addWidget(self.btn_start)
        self.controls_layout.addWidget(self.btn_stop)
        self.controls_layout.addWidget(self.combo_mode)
        self.controls_layout.addStretch()        # Push everything left
        
        self.main_layout.addWidget(self.top_controls_group)
        
        
        # Row 2: Settings (Static Settings | Live Control)
        self.settings_layout = QHBoxLayout()
        
            # LEFT: Static Settings
        self.group_static_settings = QGroupBox("Data Collection Settings")
        self.static_set_layout = QGridLayout()
        self.group_static_settings.setLayout(self.static_set_layout)
        
                # FPS
        self.input_fps = QDoubleSpinBox()
        self.input_fps.setValue(10)
        self.input_fps.setRange(0, 914.4)
        self.input_fps.setSuffix(" FPS")
                # ROI
        self.input_ROI_width = QSpinBox()
        self.input_ROI_width.setMaximum(4096)        
        self.input_ROI_width.setValue(4096)        
        self.input_ROI_width.setSuffix(" px")  
        self.input_ROI_height = QSpinBox()
        self.input_ROI_height.setMaximum(3000)
        self.input_ROI_height.setValue(3000)
        self.input_ROI_height.setSuffix(" px")
                # Filepath
        self.input_filepath = QLineEdit()
        self.input_filepath.setPlaceholderText("Enter filepath to folder for data logging here...")
                # Sample rate
        self.input_sample_rate = QDoubleSpinBox()
        self.input_sample_rate.setValue(40)
        self.input_sample_rate.setSuffix(" ms")
        self.input_sample_rate.setMinimum(0)
        self.input_sample_rate.setSingleStep(10)

                # Add all widgets
        self.static_set_layout.addWidget(QLabel("Frame rate:"), 0, 0)
        self.static_set_layout.addWidget(self.input_fps, 0, 1, 1, 4)
        
        self.static_set_layout.addWidget(QLabel("Region of interest:"), 1, 0)
        self.static_set_layout.addWidget(QLabel("Width:"), 1, 1, alignment=Qt.AlignmentFlag.AlignRight)
        self.static_set_layout.addWidget(self.input_ROI_width, 1, 2)
        self.static_set_layout.addWidget(QLabel("Height:"), 1, 3, alignment=Qt.AlignmentFlag.AlignRight)
        self.static_set_layout.addWidget(self.input_ROI_height, 1, 4, )
        
        self.static_set_layout.addWidget(QLabel("Save directory:"), 2, 0)
        self.static_set_layout.addWidget(self.input_filepath, 2, 1, 1, 4)
        
        self.static_set_layout.addWidget(QLabel("Sample rate:"), 3, 0)
        self.static_set_layout.addWidget(self.input_sample_rate, 3, 1, 1, 4)

            # RIGHT: Rolling/live inputs
        self.group_live_settings = QGroupBox("Live Settings")
        self.live_set_layout = QGridLayout()
        self.group_live_settings.setLayout(self.live_set_layout)
        
                # Voltage Control Spinner
        self.input_voltage = QDoubleSpinBox()
        self.input_voltage.setSuffix(" V")
        self.input_voltage.setRange(-5000, 5000)
        self.input_voltage.setSingleStep(10)
        self.input_voltage.valueChanged.connect(self.update_DAQ_voltage)
                # High time
        self.input_high_time = QDoubleSpinBox()
        self.input_high_time.setSuffix(" s")
        self.input_high_time.setMinimum(0)
        self.input_high_time.valueChanged.connect(self.update_DAQ_hightime)
                # Polarity mode
        self.input_polarity_mode = QComboBox()
        self.input_polarity_mode.addItems(["Bipolar switching", "Unipolar switching", "Unipolar constant"])
        self.input_polarity_mode.currentIndexChanged.connect(self.update_DAQ_polarity_mode)

                # Add all widgets
        self.live_set_layout.addWidget(QLabel("Emitter voltage: "), 0, 0)
        self.live_set_layout.addWidget(self.input_voltage, 0, 1)
        
        self.live_set_layout.addWidget(QLabel("High time:"), 1, 0)
        self.live_set_layout.addWidget(self.input_high_time, 1, 1)
        
        self.live_set_layout.addWidget(QLabel("Polarity mode:"), 2, 0)
        self.live_set_layout.addWidget(self.input_polarity_mode, 2, 1)
        
            # MAKE WHOLE ROW: Add both groups to the layout
        self.settings_layout.addWidget(self.group_static_settings)
        self.settings_layout.addWidget(self.group_live_settings)
        
        self.main_layout.addLayout(self.settings_layout)

        # Row 3: Live feeds (Camera Feed | Plot Feed)
        self.feeds_layout = QHBoxLayout()
        
            # LEFT: Camera Feed (placeholder)
        self.group_cam_feed = QGroupBox("Camera Feed")
        self.group_cam_feed.setStyleSheet("background-color: black;") # placeholder black background
        self.cam_feed_layout = QVBoxLayout()
        self.group_cam_feed.setLayout(self.cam_feed_layout)
        
                # Placeholder label
        self.camera_placeholder_text = QLabel("Waiting for camera...")
        self.camera_placeholder_text.setStyleSheet("color: white; font-size:20px;")
        self.cam_feed_layout.addWidget(self.camera_placeholder_text)


            # RIGHT: Plot feed (placeholder)
        self.group_plots = QGroupBox("Voltage and Current Plots")
        self.plots_layout = QVBoxLayout()
        self.group_plots.setLayout(self.plots_layout)
        
                # Placeholder label
        self.voltage_placeholder_text = QLabel("0.00 V")
        self.voltage_placeholder_text.setStyleSheet("font-size: 20px;")
        self.plots_layout.addWidget(self.voltage_placeholder_text)
            
                # Log Window
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(100)
        self.plots_layout.addWidget(self.log_box)
        
            # BUILD WHOLE ROW
        self.feeds_layout.addWidget(self.group_cam_feed, stretch = 1)
        self.feeds_layout.addWidget(self.group_plots, stretch = 1)
        self.main_layout.addLayout(self.feeds_layout, stretch = 2)

        # Menu Bar and Hardware Config Menu/Dialogue
        self.hw_config = {
                         "ai_device": "cDAQ9185-2023AF4Mod1",
                         "ai_channels": "0, 1",
                         "ao_device": "cDAQ9185-2023AF4Mod2",
                         "ao_channels": "0, 1"  
                         }       
        
        self.menubar = self.menuBar()
        self.config_menu = self.menubar.addMenu("Configuration")
        
            #actions
        action_hardware = self.config_menu.addAction("Hardware connections...")
        action_hardware.triggered.connect(self.open_hardware_config)
        
        # Initialize Workers
        self.cam_worker = CameraWorker()
        self.daq_worker = DAQWorker()

        # Connect Signals (Worker -> GUI)
        self.cam_worker.log_message.connect(self.append_log)
        self.cam_worker.image_ready.connect(self.update_image_display) # You need to write this function
        self.daq_worker.data_ready.connect(self.update_daq_display)
        self.daq_worker.log_message.connect(self.append_log)

    def start_system(self):
        # UI Updates
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.combo_mode.setEnabled(False)
        self.append_log("System Starting...")
        
        # Create timestamp linked filename
        self.filenametime = time.strftime("ESPRAY_%Y-%m-%d_%H%M")
        
        # Lock inputs
        self.input_fps.setEnabled(False)
        self.input_filepath.setEnabled(False)
        self.input_sample_rate.setEnabled(False)
        
        # Check if camera is in use
        if "Camera" in self.combo_mode.currentText():
            use_cam = True
            self.cam_worker.trigger_mode = "Hardware"
        else:
            use_cam = False
    
        # Pass settings to workers
            # Cam worker
        if use_cam == True:
            self.cam_worker.filepath = f"{self.input_filepath.text()}/{self.filenametime}_IMAGES.tiff"
            self.cam_worker.ROI = [self.input_ROI_width.value(), self.input_ROI_height.value()]
            # Daq worker
        self.daq_worker.filepath = f"{self.input_filepath.text()}/{self.filenametime}_DATA.csv"
        
        self.inputted_fps = self.input_fps.value()
        self.inputted_filepath = self.input_filepath.text()
        
        # Parse Configuration from Settings
        try:
            ai_chans = [int(x.strip()) for x in self.hw_config["ai_channels"].split(',')]
            ao_chans = [int(x.strip()) for x in self.hw_config["ao_channels"].split(',')]
        except ValueError:
            self.append_log("Error parsing channels! Check config format (e.g. '0, 1').")
            self.btn_start.setEnabled(True) # Re-enable start button
            return

            # Update workers
        self.daq_worker.ai_channel_name = self.hw_config["ai_device"]
        self.daq_worker.ao_channel_name = self.hw_config["ao_device"]
        self.daq_worker.ai_channels_to_use = ai_chans
        self.daq_worker.ao_channels_to_use = ao_chans
        
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

    def open_hardware_config(self):
        # Pass the dictionary to the dialog so it can read/write to it
        dialog = HardwareConfigDialog(self.hw_config, self)
        if dialog.exec():
            self.append_log("Hardware configuration updated.")
            self.append_log(f"Current AI Device: {self.hw_config['ai_device']}")

    def stop_system(self):
        self.append_log("Stopping...")
        self.cam_worker.stop()
        self.daq_worker.stop()
        
        # unlock inputs
        self.input_fps.setEnabled(True)
        self.input_filepath.setEnabled(True)
        self.input_sample_rate.setEnabled(True)
        
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
        self.voltage_placeholder_text.setText(f"Voltage: {volts:.2f} V | Current: {amps:.6f} A")

# --- APP ENTRY POINT ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ElectrosprayUI()
    window.show()
    sys.exit(app.exec())