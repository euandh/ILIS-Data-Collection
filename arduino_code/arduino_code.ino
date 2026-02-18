int trigPin = 3;
int NI_pin = A0;

void setup() {
  // put your setup code here, to run once:
  pinMode(trigPin, OUTPUT);
  digitalWrite(trigPin, HIGH);
  pinMode(NI_pin, INPUT);
}

void loop() {
  // put your main code here, to run repeatedly:
  if (analogRead(NI_pin) > 0.5) {
    digitalWrite(trigPin, LOW);
  }
  else{
    digitalWrite(trigPin, HIGH);
  }
}
