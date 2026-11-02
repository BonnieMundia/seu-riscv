// w4_attitude.c - W4: fixed-point attitude filter + attitude-hold loop, 200 steps
// (avionics-style control loop).
//
// Three axes (roll, pitch, yaw). Each step, per axis:
//   1. plant:      the true body rate changes by the last actuator command plus a random
//                  disturbance; the true angle integrates the rate.
//   2. sensors:    gyro = true rate + constant bias + noise;
//                  accelerometer angle (roll and pitch only) = true angle + noise.
//   3. filter:     complementary filter: integrate the gyro (predict), then pull the
//                  estimate 1/32 of the way toward the accelerometer angle (correct).
//                  Yaw has no accelerometer reference, so its estimate drifts with the
//                  gyro bias, exactly like a real IMU without a magnetometer.
//   4. controller: PD attitude hold, u = -(1.5*angle + 0.25*rate), saturated.
// Fixed point: Q16.16 (1.0 = 65536), dt = 1/64 s. Every gain is a power of two or a sum
// of powers of two, so all "multiplies" are shifts and adds: RV32I has no multiply
// instruction and libgcc's __mulsi3 would cost up to ~800 cycles per signed product.
// Output: one checksum; per step it mixes in the sum over axes of (estimate XOR command).
#include "common.h"

#define STEPS     200
#define AXES      3
#define DT_SHIFT  6          // dt = 1/64 s     -> x*dt  = x >> 6
#define K_SHIFT   5          // filter gain 1/32 -> pull 1/32 toward the accelerometer
#define RATE_MAX  (1 << 16)  // |true rate| <= 1.0 rad/s
#define U_MAX     (1 << 15)  // |command|   <= 0.5

// Signed noise from a bit field of a random word: bits [lo, lo+bits) of w, centred on 0,
// i.e. a value in [-2^(bits-1), 2^(bits-1)-1]. One xorshift32 call per axis per step feeds
// all three noise values (bits 0-11, 12-21, 22-31): 600 calls instead of 1,600, because
// every call costs three multi-bit shifts and PicoRV32 has no barrel shifter.
static int32_t field(uint32_t w, int lo, int bits)
{
    return (int32_t)((w >> lo) & ((1u << bits) - 1)) - (1 << (bits - 1));
}

static int32_t sat(int32_t v, int32_t lim)
{
    if (v > lim)
        return lim;
    if (v < -lim)
        return -lim;
    return v;
}

int main(void)
{
    static const int32_t bias[AXES] = {655, -983, 1311};   // ~0.010, -0.015, 0.020 rad/s
    int32_t rate[AXES] = {0}, truth[AXES] = {0}, est[AXES] = {0}, u[AXES] = {0};
    uint32_t seed = 0xA77170DEu;
    uint32_t cs = 0;

    for (int step = 0; step < STEPS; step++) {
        uint32_t step_sum = 0;
        for (int ax = 0; ax < AXES; ax++) {
            uint32_t w = xorshift32(&seed);

            // 1. plant
            rate[ax] = sat(rate[ax] + (u[ax] >> 4) + field(w, 0, 12), RATE_MAX);
            truth[ax] += rate[ax] >> DT_SHIFT;

            // 2-3. sensors + complementary filter
            int32_t gyro = rate[ax] + bias[ax] + field(w, 12, 10);
            est[ax] += gyro >> DT_SHIFT;                      // predict
            if (ax < 2) {                                     // roll, pitch only
                int32_t acc = truth[ax] + field(w, 22, 10);
                est[ax] += (acc - est[ax]) >> K_SHIFT;        // correct
            }

            // 4. PD controller: 1.5*est = est + est/2, 0.25*gyro = gyro/4
            u[ax] = sat(-(est[ax] + (est[ax] >> 1)) - (gyro >> 2), U_MAX);

            step_sum += (uint32_t)est[ax] ^ (uint32_t)u[ax];
        }
        // One mix per step (mix() costs two multi-bit shifts; 200 calls instead of 1,200).
        // A wrong estimate or command on any axis changes step_sum, and the closed loop
        // carries the error into every later step as well.
        cs = mix(cs, step_sum);
    }

    report(cs);
    return 0;
}
