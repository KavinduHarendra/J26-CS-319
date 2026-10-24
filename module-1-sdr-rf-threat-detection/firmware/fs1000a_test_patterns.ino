// Single 433 MHz FS1000A transmitter test patterns (one-transmitter setup).
// Cycles through idle, constant carrier, pulsed and random bursts, and an OOK
// data pattern, printing "millis,LABEL" over serial at each change.
// Wiring: DATA -> pin 12, VCC -> 5V, GND -> GND, antenna on ANT.

const uint8_t TX_PIN = 12;
const unsigned long PHASE_MS = 10000;
const uint8_t CYCLES = 1;

uint8_t cyclesDone = 0;

void logPhase(const char* label) {
  Serial.print(millis());
  Serial.print(',');
  Serial.println(label);
}

void phaseIdle() {
  logPhase("IDLE");
  digitalWrite(TX_PIN, LOW);
  delay(PHASE_MS);
}

void phaseCarrier() {
  logPhase("CARRIER");
  digitalWrite(TX_PIN, HIGH);
  delay(PHASE_MS);
  digitalWrite(TX_PIN, LOW);
}

void phasePulsed(unsigned int onMs, unsigned int offMs, const char* label) {
  logPhase(label);
  unsigned long start = millis();
  while (millis() - start < PHASE_MS) {
    digitalWrite(TX_PIN, HIGH);
    delay(onMs);
    digitalWrite(TX_PIN, LOW);
    delay(offMs);
  }
}

void phaseRandomBursts() {
  logPhase("RANDOM_BURSTS");
  unsigned long start = millis();
  while (millis() - start < PHASE_MS) {
    digitalWrite(TX_PIN, HIGH);
    delay(random(5, 200));
    digitalWrite(TX_PIN, LOW);
    delay(random(20, 500));
  }
}

void phaseOokData() {
  logPhase("OOK_DATA");
  const unsigned int bitUs = 1000;
  unsigned long start = millis();
  while (millis() - start < PHASE_MS) {
    for (int i = 0; i < 8; i++) {
      digitalWrite(TX_PIN, (i % 2 == 0) ? HIGH : LOW);
      delayMicroseconds(bitUs);
    }
    for (int i = 0; i < 32; i++) {
      digitalWrite(TX_PIN, random(2) ? HIGH : LOW);
      delayMicroseconds(bitUs);
    }
    digitalWrite(TX_PIN, LOW);
    delay(50);
  }
}

void setup() {
  pinMode(TX_PIN, OUTPUT);
  digitalWrite(TX_PIN, LOW);
  Serial.begin(115200);
  randomSeed(analogRead(A0));
  delay(3000);
  logPhase("START");
}

void loop() {
  if (cyclesDone >= CYCLES) {
    digitalWrite(TX_PIN, LOW);
    logPhase("DONE");
    while (true) { delay(1000); }
  }

  phaseIdle();
  phaseCarrier();
  phaseIdle();
  phasePulsed(50, 50, "PULSED_50_50");
  phaseIdle();
  phasePulsed(5, 95, "PULSED_5_95");
  phaseRandomBursts();
  phaseOokData();
  phaseIdle();

  cyclesDone++;
}
