int trigPin = 3;
int NI_pin_control = A0;
int FVALPin = 5;
int NI_pin_FVAL = 8;
bool lastControlState = false;

void setup() {
    pinMode(trigPin, OUTPUT);
    digitalWrite(trigPin, LOW);   
    pinMode(NI_pin_control, INPUT);
    
    pinMode(FVALPin, INPUT);
    pinMode(NI_pin_FVAL, OUTPUT);
    digitalWrite(NI_pin_FVAL, LOW);
}

void loop() {
    bool currentControlState = analogRead(NI_pin_control) > 102;
    
    // Only trigger on the rising edge of the control signal
    if (currentControlState && !lastControlState) {
        digitalWrite(trigPin, HIGH);  // Rising edge pulse
        delay(10);
        digitalWrite(trigPin, LOW);
    }
    lastControlState = currentControlState;

    // Leave FVAL high long enough for NI DAQ to sample it
    if (digitalRead(FVALPin) == HIGH) {
        digitalWrite(NI_pin_FVAL, HIGH);
        delay(200);
        digitalWrite(NI_pin_FVAL, LOW);
    }
}
