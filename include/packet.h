#ifndef _PACKET_H_
#define _PACKET_H_

#include <Arduino.h>

#define xstr(s) str(s)
#define str(s) #s

#define CHANNEL_ZERO 0xBAE1F00100
#define address_for(channel) (CHANNEL_ZERO | (channel & 0xFF))

struct __attribute__ ((packed)) packet_t {
    /* Detector ID */
    uint8_t id;

    /* Flags */
    uint8_t motion:1;
    uint8_t knock:2;

    /* Time of system and last interrupts */
    unsigned long time;
    unsigned long time_last_knock;
    unsigned long time_last_motion;

    /* Accelerometer reading */
    float x;
    float y;
    float z;
};

#endif // _PACKET_H_