#include <Arduino.h>
#include <Wire.h>

#define SERIAL_DEBUG 1
#include <packet.h>

#ifndef CHANNEL
#define CHANNEL 1
#endif

#define POWERSAVE false
#define KEEPALIVE_TIMEOUT 100

packet_t packet = {};
conf_t config = { .id = CHANNEL, .threshold = 20 };
void update_config(conf_t* config);

#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>
RF24 radio(10, 9); //CE, CSN

#include <I2Cdev.h>
#include <MPU6050.h>
#if I2CDEV_IMPLEMENTATION == I2CDEV_ARDUINO_WIRE
    #include "Wire.h"
#endif

MPU6050 mpu;
int16_t ax, ay, az;
uint8_t last_motion = 0;
#define MOT_DUR_DEFAULT 10

#define PIN_MOTION digitalPinToInterrupt(3)
unsigned long time_last_motion;
void motion_interrupt() {
  time_last_motion = millis();
}

void setup(void) {
  Serial.begin(BAUD);
  while (!Serial)
    delay(10);

#if I2CDEV_IMPLEMENTATION == I2CDEV_ARDUINO_WIRE
  Wire.begin();
#elif I2CDEV_IMPLEMENTATION == I2CDEV_BUILTIN_FASTWIRE
  Fastwire::setup(400, true);
#endif
  mpu.initialize();
  if(!mpu.testConnection()) {
    log_debug("MPU6050 connection failed");
    bool toggle = 0;
    pinMode(2, OUTPUT);
    while(true) {
      digitalWrite(2, toggle);
      toggle = !toggle;
      delay(500);
    }
  }

  /* MPU */
  // mpu.setRate(??);
  mpu.setDLPFMode(MPU6050_DLPF_BW_188);
  mpu.setDHPFMode(MPU6050_DHPF_0P63);
  update_config(&config);
  mpu.setMotionDetectionDuration(MOT_DUR_DEFAULT);
  mpu.setInterruptMode(MPU6050_INTMODE_ACTIVEHIGH);
  mpu.setInterruptDrive(MPU6050_INTDRV_PUSHPULL);
  mpu.setInterruptLatch(MPU6050_INTLATCH_50USPULSE);
  log_debug_fmt("Motion interrupt = %d", mpu.getIntEnabled());
  mpu.setIntEnabled(0);
  mpu.setIntMotionEnabled(true);

  log_debug_fmt("Motion pin = %d", PIN_MOTION);
  pinMode(PIN_MOTION, INPUT_PULLUP);
  time_last_motion = millis();
  attachInterrupt(PIN_MOTION, motion_interrupt, RISING);

  /* RF24 Radio */
  Serial.println("RF24 transmitter setup...");
  radio.begin();
  radio.setPALevel(RF24_PA_MAX);
  radio.enableDynamicPayloads();
  radio.enableAckPayload();
  radio.setDataRate(RF24_1MBPS);

  radio.openWritingPipe(address_for(CHANNEL));
  radio.stopListening();
  radio.printDetails();

  packet.id = CHANNEL;
}

void update_config(conf_t* config) {
  log_debug_fmt("CONF [%d] THR [%d]", config->id, config->threshold);
  if(config->id == CHANNEL) {
    mpu.setMotionDetectionThreshold(config->threshold);
    packet.cfg_threshold = config->threshold;
    packet.cfg_threshold_update = true;
  } else {
    log_debug_fmt("Config received for wrong channel %d (expecting " xstr(CHANNEL) ")", config->id);
  }
}

uint8_t pipe = 0;
bool transmit;
unsigned long now;

void loop() {
  transmit = !POWERSAVE;
  if(time_last_motion != packet.time_last_motion) {
    transmit = true;
    last_motion = mpu.getMotionStatus();
  }
  now = millis();
  transmit |= now - packet.time > KEEPALIVE_TIMEOUT;

  if (transmit) {
    mpu.getAcceleration(&ax, &ay, &az);
    packet.x = ax;
    packet.y = ay;
    packet.z = az;
    if(last_motion)
      packet.motion = last_motion;
    packet.time_last_motion = time_last_motion;
    packet.time = millis();

#if SERIAL_DEBUG
    log_debug_fmt("[%d] [ACC] %7d / %7d / %7d (%02X @ %lu ms) [%d] [%02X]",
      packet.id,
      packet.x, packet.y, packet.z,
      packet.motion,
      packet.time_last_motion,
      sizeof(packet),
      last_motion);
#endif

    if(radio.write(&packet, sizeof(packet))) {
      packet.cfg_update = 0;
      if (radio.available(&pipe)) {
        uint8_t size = radio.getDynamicPayloadSize();
        if(size != sizeof(config)) {
          log_debug_fmt("Unexpected ACK payload size of %d", size);
        }
        radio.read(&config, sizeof(config));
        update_config(&config);
      }
    }
  }
}