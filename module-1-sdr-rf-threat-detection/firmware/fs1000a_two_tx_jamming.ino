// Two 433 MHz FS1000A transmitters on one Uno.
// TX1 (pin 12) runs the normal data link the whole time.
// TX2 (pin 11) is the second transmitter, on only during the JAM phases.
// Wiring: each module VCC -> 5V rail, GND -> GND, DATA -> its pin, antenna on ANT.
// Serial (115200) prints "millis,LABEL" whenever the phase changes.

const uint8_t TX1_PIN = 12;
const uint8_t TX2_PIN = 11;
const unsigned long PHASE_MS = 10000;
const uint8_t CYCLES = 1;

uint8_t cyclesDone = 0;
unsigned long lastBit = 0;
uint8_t bitState = 0;

// Keep TX1 streaming ~1 kbps of random bits so the link is always present.
void serviceLink() {
  unsigned long now = micros();
  if (now - lastBit >= 1000) {
    lastBit = now;
    bitState = random(2);
    digitalWrite(TX1_PIN, bitState);
  }
}

void logPhase(const char* label) {
  Serial.print(millis());
  Serial.print(',');
  Serial.println(label);
}

// Run one phase while keeping the link alive.
// jammer: 0 off, 1 constant, 2 pulsed, 3 random.
void phase(const char* label, uint8_t jammer) {
  logPhase(label);
  unsigned long start = millis();
  unsigned long nextTog = micros();
  uint8_t js = 0;
  while (millis() - start < PHASE_MS) {
    serviceLink();
    unsigned long now = micros();
    if (jammer == 0) {
      digitalWrite(TX2_PIN, LOW);
    } else if (jammer == 1) {
      digitalWrite(TX2_PIN, HIGH);
    } else if (jammer == 2) {
      if (now - nextTog >= 10000) { nextTog = now; js = !js; digitalWrite(TX2_PIN, js); }
    } else if (jammer == 3) {
      if (now - nextTog >= (unsigned long)random(2000, 30000)) {
        nextTog = now; js = !js; digitalWrite(TX2_PIN, js);
      }
    }
  }
  digitalWrite(TX2_PIN, LOW);
}

void setup() {
  pinMode(TX1_PIN, OUTPUT);
  pinMode(TX2_PIN, OUTPUT);
  digitalWrite(TX1_PIN, LOW);
  digitalWrite(TX2_PIN, LOW);
  Serial.begin(115200);
  randomSeed(analogRead(A0));
  delay(3000);
  logPhase("START");
}

void loop() {
  if (cyclesDone >= CYCLES) {
    digitalWrite(TX1_PIN, LOW);
    digitalWrite(TX2_PIN, LOW);
    logPhase("DONE");
    while (true) { delay(1000); }
  }

  phase("LINK_ONLY",    0);
  phase("JAM_CONSTANT", 1);
  phase("LINK_ONLY",    0);
  phase("JAM_PULSED",   2);
  phase("LINK_ONLY",    0);
  phase("JAM_RANDOM",   3);
  phase("LINK_ONLY",    0);

  cyclesDone++;
}
