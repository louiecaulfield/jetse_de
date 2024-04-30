#ifndef _PACKET_H_
#define _PACKET_H_

#include <Arduino.h>

typedef struct {
    byte id;
    unsigned long time;
    float x;
    float y;
    float z;
    bool motion;
    bool knock;
    unsigned long last_knock_time;
} packet_t;

#endif // _PACKET_H_