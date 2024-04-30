#include <Arduino.h>
#include <Wire.h>

#include <Adafruit_Sensor.h>
#include <Adafruit_MPU6050.h>
Adafruit_MPU6050 mpu;
float acc_abs;
#define abs(x) ((x)>0?(x):-(x))

#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>
RF24 radio(D4, D8); //CE, CSN

#include <packet.h>
const byte address[6] = "00009";
packet_t packet = {};

#define PIN_KNOCK digitalPinToInterrupt(D3)
#define KNOCK_MIN_DURATION 100

unsigned long last_knock_time;
void ICACHE_RAM_ATTR knock_falling() {
  unsigned long now = millis();
  if(now - last_knock_time > KNOCK_MIN_DURATION) {
    last_knock_time = now;
  }
}

#define send_all true

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
  mpu.setInterruptPinLatch(true);	// Keep it latched.  Will turn off when reinitialized.
  mpu.setInterruptPinPolarity(true);
  mpu.setMotionInterrupt(true);

  /* RF24 Radio */
  Serial.println("RF24 setup...");
  radio.begin();
  // radio.setPALevel(RF24_PA_LOW);
  // radio.setRetries(3,5);
  radio.openWritingPipe(address);
  radio.stopListening();
  radio.printDetails();

  /* Knock detector */
  Serial.print("Knock pin = ");
  Serial.println(PIN_KNOCK);
  pinMode(PIN_KNOCK, INPUT);
  last_knock_time = millis();
  attachInterrupt(PIN_KNOCK, knock_falling, FALLING);

  packet.id = address[5];
}

char rf24_msg[100] = "";
sensors_event_t a, g, temp;

void loop() {

  mpu.getEvent(&a, &g, &temp);

  packet.time = millis();
  packet.x = a.acceleration.x;
  packet.y = a.acceleration.y;
  packet.z = a.acceleration.z;
  packet.motion = mpu.getMotionInterruptStatus();
  packet.knock = packet.last_knock_time != last_knock_time;
  packet.last_knock_time = last_knock_time;

  if(send_all || packet.motion || packet.knock) {
    acc_abs = abs(packet.x) + abs(packet.y) + abs(packet.z);
    sprintf(rf24_msg, "Accelero %05.2f / %05.2f / %05.2f (%d) - KNOCK %d @ %lu ms",
                      packet.x, packet.y, packet.z,
                      packet.motion,
                      packet.knock,
                      packet.last_knock_time);
    Serial.println(rf24_msg);
    radio.write(&packet, sizeof(packet));
  }
}