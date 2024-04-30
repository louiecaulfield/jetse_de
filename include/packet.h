#ifndef _PACKET_H_
#define _PACKET_H_

#include <Arduino.h>

#define xstr(s) str(s)
#define str(s) #s

#define PREFIX "100F"
#define address_for(INDEX) xstr(INDEX) PREFIX

struct __attribute__ ((packed)) packet_t {
    uint8_t id;
    uint8_t motion:1;
    uint8_t knock:2;
    unsigned long time;
    float x;
    float y;
    float z;
    unsigned long last_knock_time;
};

#endif // _PACKET_H_