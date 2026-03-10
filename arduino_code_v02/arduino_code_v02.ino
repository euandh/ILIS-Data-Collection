int trigPin = 3;
int NI_pin_control = A0;
int FVALPin = 5;
int NI_pin_FVAL = 8;

void setup() {
    Serial.begin(9600); 
    
    pinMode(trigPin, OUTPUT);
    digitalWrite(trigPin, LOW);
    
    pinMode(NI_pin_control, INPUT);
    
    // Use INPUT_PULLUP just in case the camera uses an open-drain output
    pinMode(FVALPin, INPUT_PULLUP); 
    
    pinMode(NI_pin_FVAL, OUTPUT);
    digitalWrite(NI_pin_FVAL, LOW);
}

void loop() {
    // Read the DAQ Control Pulse
    bool daq_pulse_active = analogRead(NI_pin_control) > 102;
    
    // Instantly mirror the DAQ pulse to the Camera
    if (daq_pulse_active) {
        digitalWrite(trigPin, HIGH);
    } else {
        digitalWrite(trigPin, LOW);
    }

    // Send FVAL back to the DAQ
    if (digitalRead(FVALPin) == HIGH) {
        digitalWrite(NI_pin_FVAL, HIGH);
    } else {
        digitalWrite(NI_pin_FVAL, LOW);
    }
}
