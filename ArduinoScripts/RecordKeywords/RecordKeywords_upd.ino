#include <PDM.h>

const int RECORD_DURATION_MS = 1500; 
const int PAUSE_DURATION_MS = 1500; 

short sampleBuffer[256]; 
volatile int samplesRead; // Updated by PDM interrupt
bool isRecording = false;
bool sessionActive = false;
bool isWaitingForSave = false; // <-- NEW STATE
unsigned long stateStartTime = 0;

void readPDMdata() {
  int bytesAvailable = PDM.available();
  // Divide by 2 because sampleBuffer samples are 16 bits = 2 bytes
  samplesRead = bytesAvailable / 2; 
  PDM.read(sampleBuffer, bytesAvailable); 
}

void setup() {
  Serial.begin(1000000); // Ultra-fast baud rate for audio streaming
  delay(200);
  pinMode(LED_BUILTIN, OUTPUT); 
  
  PDM.setGain(80);
  PDM.onReceive(readPDMdata); // <-- UNCOMMENTED: Required to actually get mic data

  if (!PDM.begin(1, 16000)) {
    while (1) {
      digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
      delay(200); 
    }
  }
}

void loop() {
  // 1. Handle incoming commands from Python
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n'); 
    cmd.trim(); 

    if (cmd == "STARTSESSION") {
      sessionActive = true;
      isRecording = false;
      isWaitingForSave = false;
      stateStartTime = millis();
      digitalWrite(LED_BUILTIN, LOW);
      Serial.println("SESSION_ON");
    }
    else if (cmd == "ENDSESSION") {
      sessionActive = false;
      isRecording = false;
      isWaitingForSave = false;
      digitalWrite(LED_BUILTIN, LOW);
    }
    // <-- NEW: If Python says SAVED, move out of the wait state
    else if (cmd == "SAVED") { 
      isWaitingForSave = false;
      stateStartTime = millis(); // Reset timer for the PAUSE phase
    }
  }

  if (!sessionActive) { 
    return;
  }

  // 2. If Python is busy saving on its end, we do NOTHING and wait here safely
  if (isWaitingForSave) {
    return; 
  }

  unsigned long currentTime = millis();

  // 3. State Machine: Transition between Pause and Recording
  if (!isRecording) {
    // PAUSE STATE: Wait 1.5 seconds, then trigger recording
    if (currentTime - stateStartTime >= PAUSE_DURATION_MS) {
      isRecording = true;
      stateStartTime = currentTime;
      digitalWrite(LED_BUILTIN, HIGH); // Turn LED ON
      Serial.println("RECORD_NOW"); 
    }
  } else {
    // RECORDING STATE: Capture audio for 1.5 seconds
    if (currentTime - stateStartTime >= RECORD_DURATION_MS) {
      isRecording = false;
      isWaitingForSave = true;       // <-- Enter wait state until Python finishes saving
      digitalWrite(LED_BUILTIN, LOW);  // Turn LED OFF
      Serial.println("STOP_RECORDING"); 
    }
  }

  // 4. Audio Streaming Logic
  if (isRecording) {
    // Only write to serial if the PDM interrupt has filled the buffer
    if (samplesRead > 0) {
      Serial.write((uint8_t*)sampleBuffer, samplesRead * 2);
      samplesRead = 0; // Reset flag until next interrupt
    }
  } else {
    samplesRead = 0; // Clear the buffer during pauses/waiting
  }
}