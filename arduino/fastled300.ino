#define NUM_LEDS 300
#include "FastLED.h"
#define PIN 2

CRGB leds[NUM_LEDS];

void setup() {
    FastLED.addLeds<WS2811, PIN, GRB>(leds, NUM_LEDS).setCorrection( TypicalLEDStrip );
//    FastLED.setBrightness(20);
    pinMode(PIN, OUTPUT);
    Serial.begin(115200);
}

void loop() {
    Serial.readBytes((char*)&leds, NUM_LEDS * sizeof(CRGB));
    FastLED.show();
}
