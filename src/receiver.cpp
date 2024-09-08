#include <Arduino.h>

#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>
#include <PacketSerial.h>

PacketSerial packet_serial;
#define log(level, msg) (serial_tx_log(level, msg))
#include <packet.h>

#ifndef RECEIVER_ID
#error No receiver ID defined <RECEIVER_ID>
#endif

RF24 radio(RADIO_CE_CS);

packet_channel_event_t packet_event = {
  .magic = PACKET_MAGIC,
  .ptype = PACKET_TYPE_CHANNEL_EVENT
};
packet_channel_config_req_t packet_cfg_req = {
  .magic = PACKET_MAGIC,
  .ptype = PACKET_TYPE_CHANNEL_CONFIG_REQ
};
packet_log_t packet_log = {
  .magic = PACKET_MAGIC,
  .ptype = PACKET_TYPE_LOG
};

channel_config_t channel_config[N_CHANNELS];
packet_channel_config_t config_packet;

uint8_t update_pipe[N_PIPES];

int get_missing_config() {
  for(uint8_t channel = 0; channel < N_CHANNELS; channel++) {
    if (!bitRead(update_pipe[pipe_for_channel(channel)], channel % CHANNELS_PER_PIPE)) {
      return channel;
    }
  }

  return -1;
}

void serial_tx_log(const char* level, const char* msg) {
  snprintf(packet_log.msg, sizeof(packet_log.msg), "%s%s", level, msg);

  uint8_t * checksum = (uint8_t *)packet_log.msg + strnlen(packet_log.msg, sizeof(packet_log.msg));
  *checksum = 0;
  for(uint8_t* b = (uint8_t *)&packet_log; b < checksum; b++) {
    *checksum += *b;
  }

  packet_serial.send((uint8_t *)&packet_log, checksum - (uint8_t*)&packet_log + 1);
}

void serial_tx_chan_event() {
  /* Simple checksum */
  packet_event.checksum = 0;
  for(unsigned int i=0; i < sizeof(packet_event) - 1; i++) {
    packet_event.checksum += ((uint8_t *)&packet_event)[i];
  }

  /* Send the packet data */
  packet_serial.send((uint8_t *)&packet_event, sizeof(packet_event));
}

void serial_tx_chan_cfg_req(uint8_t channel) {
  packet_cfg_req.channel = channel;
  packet_cfg_req.checksum = 0;
  for(unsigned int i=0; i < sizeof(packet_cfg_req) - 1; i++) {
    packet_cfg_req.checksum += ((uint8_t *)(&packet_cfg_req))[i];
  }

  /* Send the packet data */
  packet_serial.send((uint8_t *)&packet_cfg_req, sizeof(packet_cfg_req));
}


void handle_packet(const uint8_t * buf, size_t size) {
  /* To be implementeed */
  uint16_t magic = (buf[1] << 8) | buf[0];
  if(magic != PACKET_MAGIC) {
    log_debug_fmt("Invalid magic %04X", magic);
    return;
  }

  uint8_t checksum = 0;
  for(uint8_t i = 0; i < size - 1; i++)
    checksum += buf[i];
  if (checksum != buf[size-1]) {
    log_debug("Invalid checksum");
    return;
  }

  switch(buf[2]) { // ptype
    case PACKET_TYPE_CHANNEL_CONFIG:
    {
      if(size != sizeof(packet_channel_config_t)) {
        log_debug_fmt("Channel config packet bad size %d != %d", size, sizeof(packet_channel_config_t));
        return;
      }
      packet_channel_config_t* packet = (packet_channel_config_t*)buf;

      if(packet->channel >= N_CHANNELS) {
        log_info_fmt("Config packet's channel ID %d too large", packet->channel);
        return;
      }

      /* Echo back the packet by means of ACK */
      packet_serial.send(buf, size);

      log_debug_fmt("Updating channel %d threshold -> %d, duration -> %d",
                      packet->channel,
                      packet->config.threshold,
                      packet->config.duration);

      channel_config[packet->channel].threshold = packet->config.threshold;
      channel_config[packet->channel].duration = packet->config.duration;
      bitSet(update_pipe[pipe_for_channel(packet->channel)],
             packet->channel % CHANNELS_PER_PIPE);
      return;
    }
    default:
    {
      log_debug_fmt("Unsupported packet type %d", buf[2]);
      return;
    }
  }
}

void setup() {
  Serial.begin(BAUD);
  while(!Serial)
    delay(10);

  packet_serial.setStream(&Serial);
  packet_serial.setPacketHandler(& handle_packet);

  log_debug("Initializing channel configuration");
  for(uint8_t ch = 0; ch < N_CHANNELS; ch++) {
    channel_config[ch] = {.threshold=255, .duration=255};
  }

  /* Ensure all pipe configs are received before starting radio */
  int missing_config_channel = get_missing_config();
  while(missing_config_channel >= 0) {
    serial_tx_chan_cfg_req((uint8_t)(missing_config_channel & 0xff));
    for(int tries = 0; tries < 1000; tries++) {
      packet_serial.update();
      int new_missing_config = get_missing_config();
      if(new_missing_config != missing_config_channel) {
        missing_config_channel = new_missing_config;
        continue;
      }
    }
  }
  log_debug("All pipes configured");

  log_debug("Initializing radio");
  radio.begin();
  radio.setPALevel(RF24_PA_MAX);
  radio.enableDynamicPayloads();
  radio.enableAckPayload();
  radio.setDataRate(RF24_1MBPS);
  radio.setChannel(frequency_for_receiver(RECEIVER_ID));

  for(uint8_t i = 0; i < N_PIPES; i++) {
    update_pipe[i] = 0;
    radio.openReadingPipe(i, PIPE_ADDRESS_BASE + i);
  }

  radio.startListening();
}

void loop() {
  if (radio.available()) {
    radio.read(&(packet_event.payload), sizeof(packet_event.payload));
    log_debug_fmt("[%10lu] [%d] [ACC] %8d / %8d / %8d (%02X@%10lu ms) [%d]",
      packet_event.payload.time,
      packet_event.payload.id,
      packet_event.payload.x, packet_event.payload.y, packet_event.payload.z,
      packet_event.payload.motion,
      packet_event.payload.time_last_motion,
      sizeof(packet_event.payload));

    uint8_t channel = packet_event.payload.id;
    if(channel >= N_CHANNELS)
      goto next;

    if(channel_config[channel].duration  != packet_event.payload.cfg.duration ||
        channel_config[channel].threshold != packet_event.payload.cfg.threshold)
    {
      bitSet(update_pipe[pipe_for_channel(channel)], channel % CHANNELS_PER_PIPE);
      // log_debug_fmt("Setting config bit for pipe %d at index %d",pipe_for_channel(channel), channel % CHANNELS_PER_PIPE);
    } else {
      bitClear(update_pipe[pipe_for_channel(channel)], channel % CHANNELS_PER_PIPE);
      // log_debug_fmt("Clearing config bit for pipe %d at index %d",pipe_for_channel(channel), channel % CHANNELS_PER_PIPE);
      serial_tx_chan_event();
    }

    if(update_pipe[pipe_for_channel(channel)])
    {
      log_debug_fmt("Writing ACK payload on pipe %d with config state %02X (%d bytes)",
                      pipe_for_channel(channel),
                      update_pipe[pipe_for_channel(channel)],
                      sizeof(pipe_config_t));
      radio.writeAckPayload(pipe_for_channel(channel),
                            &(channel_config[pipe_for_channel(channel) * CHANNELS_PER_PIPE]),
                            sizeof(pipe_config_t));
    }
  }
next:
  packet_serial.update();
}