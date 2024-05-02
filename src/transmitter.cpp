#include <Arduino.h>
#include <Wire.h>

#include <packet.h>
#define CHANNEL 9
packet_t packet = {};

#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>
RF24 radio(D4, D8); //CE, CSN

#include <Adafruit_Sensor.h>
#include <Adafruit_MPU6050.h>
Adafruit_MPU6050 mpu;
float acc_abs;
#define abs(x) ((x)>0?(x):-(x))

#define PIN_MOTION digitalPinToInterrupt(10)
unsigned long time_last_motion;
void ICACHE_RAM_ATTR motion_interrupt() {
  time_last_motion = millis();
}

#define PIN_KNOCK digitalPinToInterrupt(D3)
unsigned long time_last_knock;
void ICACHE_RAM_ATTR knock_falling() {
  time_last_knock = millis();
}

#define send_all true
// #define SERIAL_DEBUG

void setup(void) {
  Serial.begin(115200);

  while (!Serial)
    delay(10); // will pause Zero, Leonardo, etc until serial console opens

  if (!mpu.begin()) {
    Serial.println("Failed to find MPU6050 chip");
    while (1) {
      delay(10);
    }
  }
  Serial.println("MPU6050 Found!");

  /* MPU */
  mpu.setHighPassFilter(MPU6050_HIGHPASS_0_63_HZ);
  mpu.setMotionDetectionThreshold(5); //LSB = 2mg
  mpu.setMotionDetectionDuration(10); //ms
  mpu.setInterruptPinLatch(false);
  mpu.setInterruptPinPolarity(false);
  mpu.setMotionInterrupt(true);
  Serial.print("Motion pin = ");
  Serial.println(PIN_MOTION);
  pinMode(PIN_MOTION, INPUT_PULLUP);
  time_last_motion = millis();
  attachInterrupt(PIN_MOTION, motion_interrupt, FALLING);

  /* RF24 Radio */
  Serial.println("RF24 transmitter setup...");
  radio.begin();
  radio.setDataRate(RF24_2MBPS);
  // radio.setPALevel(RF24_PA_LOW);
  // radio.setRetries(3,5);
  radio.openWritingPipe(address_for(CHANNEL));
  radio.stopListening();
  radio.printDetails();

  /* Knock detector */
  Serial.print("Knock pin = ");
  Serial.println(PIN_KNOCK);
  pinMode(PIN_KNOCK, INPUT_PULLUP);
  time_last_knock = millis();
  attachInterrupt(PIN_KNOCK, knock_falling, FALLING);

  packet.id = CHANNEL;
}

#ifdef SERIAL_DEBUG
char debug_msg[100] = "";
#endif
sensors_event_t a, g, temp;

void loop() {
  mpu.getEvent(&a, &g, &temp);

  packet.x = a.acceleration.x;
  packet.y = a.acceleration.y;
  packet.z = a.acceleration.z;
  packet.motion = packet.time_last_motion != time_last_motion;
  packet.knock = packet.time_last_knock != time_last_knock;

  packet.time_last_knock = time_last_knock;
  packet.time_last_motion = time_last_motion;
  packet.time = millis();

  if(send_all || packet.motion || packet.knock) {
#ifdef SERIAL_DEBUG
    acc_abs = abs(packet.x) + abs(packet.y) + abs(packet.z);
    sprintf(debug_msg, "[%d] [ACC] %05.2f / %05.2f / %05.2f (%d/%d@%lu) - [KNOCK] %d @ %lu ms [%d]",
                      packet.id,
                      packet.x, packet.y, packet.z,
                      packet.motion,
                      digitalRead(PIN_MOTION),
                      packet.time_last_motion,
                      packet.knock,
                      packet.time_last_knock,
                      sizeof(packet));
    Serial.println(debug_msg);
#endif
    radio.write(&packet, sizeof(packet));
  }
}