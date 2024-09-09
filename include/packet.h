#ifndef _PACKET_H_
#define _PACKET_H_

#include <Arduino.h>


#ifndef log
#define log(level, msg) Serial.print(level);Serial.println(msg)
#endif

char debug_msg[100] = "";
#if SERIAL_DEBUG_TRACKER
#define log_debug(x) log("[DBG]", x)
#define log_debug_fmt(args...) snprintf(debug_msg, sizeof(debug_msg), args); log_debug(debug_msg)
#else
#define log_debug(x)
#define log_debug_fmt(args...)
#endif
#define log_info(x)  log("[INF]",x)
#define log_info_fmt(args...) snprintf(debug_msg, sizeof(debug_msg), args); log_info(debug_msg)

#define xstr(s) str(s)
#define str(s) #s

#ifndef N_RECEIVERS
#error The number of receivers should be defined by N_RECEIVERS
#endif

#ifndef N_CHANNELS
#error The number of channels should be defined by N_CHANNELS
#endif

#define N_PIPES (6)
#define CHANNELS_PER_PIPE ((N_CHANNELS + N_PIPES - 1) / N_PIPES)
#define pipe_for_channel(channel) ((channel / CHANNELS_PER_PIPE) & 0x7)

#define PIPE_ADDRESS_BASE 0xBAE1F00100
#define pipe_address_for_channel(channel) (PIPE_ADDRESS_BASE | pipe_for_channel(channel))

#define FREQ_BASE 100
// Space frequencies by 8 MHz (1<<3=8)
#define frequency_for_receiver(receiver) (FREQ_BASE + ((receiver) << 3))

#if ((FREQ_BASE + ((N_RECEIVERS - 1) << 3)) > 125)
#error N_RECEIVERS too large, resulting in frequency beyond maximum 2525 MHz
#endif


/* Channel config */
struct __attribute__ ((packed)) channel_config_t {
    uint8_t threshold;
    uint8_t duration;
};

/* Channel configs belonging to a certain pipe */
typedef channel_config_t pipe_config_t[CHANNELS_PER_PIPE];

struct __attribute__ ((packed)) channel_event_t {
    /* Tracker's channel ID, zero-based */
    uint8_t id;

    /* Time of system and last interrupts */
    unsigned long time;
    unsigned long time_last_motion;

    /* Accelerometer reading */
    int16_t x;
    int16_t y;
    int16_t z;
    union {
        uint8_t motion;
        uint8_t _unused:2;
        uint8_t motion_z_pos:1;
        uint8_t motion_z_neg:1;
        uint8_t motion_y_pos:1;
        uint8_t motion_y_neg:1;
        uint8_t motion_x_pos:1;
        uint8_t motion_x_neg:1;
    };
    union {
        uint8_t cfg_update;
        uint8_t cfg_threshold_update:1;
        uint8_t cfg_duration_update:1;
    };
    channel_config_t cfg;
};


/* Channel event packet as sent over serial interface */
struct __attribute__ ((packed)) packet_channel_event_t {
    uint16_t magic;
    uint8_t ptype;
    uint8_t freq; /* RF24 channel = actual frequency - 2400MHz */
    channel_event_t payload;
    uint8_t checksum;
};

/* Channel config request packet as transmitted over serial interface */
struct __attribute__ ((packed)) packet_channel_config_req_t {
    uint16_t magic;
    uint8_t ptype;
    uint8_t channel;
    uint8_t checksum;
};

/* Channel config packet as received over serial interface */
struct __attribute__ ((packed)) packet_channel_config_t {
    uint16_t magic;
    uint8_t ptype;
    uint8_t channel;
    channel_config_t config;
    uint8_t checksum;
};

struct __attribute__ ((packed)) packet_log_t {
    uint16_t magic;
    uint8_t ptype;
    char msg[200];
    uint8_t checksum;
};


#define PACKET_MAGIC (0xBAE1)

#define PACKET_TYPE_LOG                 (0x00)
#define PACKET_TYPE_CHANNEL_EVENT       (0x01)
#define PACKET_TYPE_CHANNEL_CONFIG_REQ  (0x02)
#define PACKET_TYPE_CHANNEL_CONFIG      (0x03)
#define PACKET_TYPE_RESET               (0x55)

#endif // _PACKET_H_