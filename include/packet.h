#ifndef _PACKET_H_
#define _PACKET_H_

#include <Arduino.h>


#define log(level, msg) Serial.print(level);Serial.println(msg)
char debug_msg[100] = "";
#if SERIAL_DEBUG
#define log_debug(x) log("[DBG]", x)
#define log_debug_fmt(args...) sprintf(debug_msg, args); log_debug(debug_msg)
#else
#define log_debug(x)
#define log_debug_fmt(args...)
#endif
#define log_info(x)  log("[INF]",x)
#define log_info_fmt(args...) sprintf(debug_msg, args); log_info(debug_msg)

#define xstr(s) str(s)
#define str(s) #s

#define CHANNEL_ZERO 0xBAE1F00100
#define address_for(channel) (CHANNEL_ZERO | (channel & 0xFF))

#define PIPES_PER_RADIO 6
#define FREQ_BASE 100
#define frequency_for(channel) (FREQ_BASE + (((channel - 1) & 0xff) / PIPES_PER_RADIO))

struct __attribute__ ((packed)) packet_t {
    /* Detector ID */
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
    uint8_t cfg_threshold;
    uint8_t cfg_duration;
};

struct __attribute__ ((packed)) conf_t {
    uint8_t id;
    uint8_t threshold;
    uint8_t duration;
};

struct __attribute__ ((packed)) packet_conf_t {
    uint16_t magic;
    conf_t payload;
    uint8_t checksum;
};

#endif // _PACKET_H_