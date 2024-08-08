#!/usr/bin/env python3
# JJY.py: a port of jjy.js library and a standalone script
# to synchronize time on JJY-enabled wristwatches via headphones
# Depends on pyaudio and ntplib
# Created by Luxferre in 2024, released into public domain

import array
import datetime
import math
import ntplib
import pyaudio
import time

OP_FREQ = 40000 / 1  # emitted frequency, Hz


# BCD and parity calculation helpers


def toBCD(val: int):
    return (val % 10) + ((int(val / 10) % 10) << 4) + (int(val / 100) << 8)


def calc_parity(val: int):
    i = 0
    while val != 0:
        i ^= (val & 1)
        val >>= 1
    return i


# internal time representation from unix time
# only fetches the fields necessary for JJY implementation
def intreptime(unixtm):
    res = {}
    tm = time.gmtime(unixtm)
    res["year"] = toBCD(tm.tm_year % 100)
    res["yday"] = toBCD(tm.tm_yday)
    res["hour"] = toBCD(tm.tm_hour)
    res["minute"] = toBCD(tm.tm_min)
    res["second"] = tm.tm_sec
    # in Python, Monday is 0; in JJY, Sunday is 0
    res["wday"] = (tm.tm_wday + 1) % 7
    res["unix"] = int(unixtm)  # save the unix time representation
    return res


# time fetching part (returns JST)
def fetchtime(params={}):
    delta = 0.0
    offset = 32400
    if "delta" in params:
        delta = float(params["delta"]) / 1000
    if "offset" in params:  # base offset from UTC in seconds
        offset = int(params["offset"])
    if "server" in params and params["server"] is not None:  # NTP server set
        ntpver = 3
        if "version" in params:
            ntpver = params["version"]
        c = ntplib.NTPClient()
        resp = c.request(params["server"], version=ntpver)
        unixtm = resp.tx_time
    else:  # use current system time by default
        unixtm = time.time()
    unixtm += offset + delta  # account for delta
    return intreptime(unixtm)


# timecode generation part
# accepts the result of fetchtime function
def gentimecode(ts):
    timecode = [2, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0,
                0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2]

    # populate minute
    timecode[1] = (ts["minute"] >> 6) & 1
    timecode[2] = (ts["minute"] >> 5) & 1
    timecode[3] = (ts["minute"] >> 4) & 1
    timecode[5] = (ts["minute"] >> 3) & 1
    timecode[6] = (ts["minute"] >> 2) & 1
    timecode[7] = (ts["minute"] >> 1) & 1
    timecode[8] = ts["minute"] & 1
    # populate hour
    timecode[12] = (ts["hour"] >> 5) & 1
    timecode[13] = (ts["hour"] >> 4) & 1
    timecode[15] = (ts["hour"] >> 3) & 1
    timecode[16] = (ts["hour"] >> 2) & 1
    timecode[17] = (ts["hour"] >> 1) & 1
    timecode[18] = ts["hour"] & 1
    # populate day number
    timecode[22] = (ts["yday"] >> 9) & 1
    timecode[23] = (ts["yday"] >> 8) & 1
    timecode[25] = (ts["yday"] >> 7) & 1
    timecode[26] = (ts["yday"] >> 6) & 1
    timecode[27] = (ts["yday"] >> 5) & 1
    timecode[28] = (ts["yday"] >> 4) & 1
    timecode[30] = (ts["yday"] >> 3) & 1
    timecode[31] = (ts["yday"] >> 2) & 1
    timecode[32] = (ts["yday"] >> 1) & 1
    timecode[33] = ts["yday"] & 1
    # populate parity bits
    timecode[36] = calc_parity(ts["hour"])
    timecode[37] = calc_parity(ts["minute"])
    # populate year
    timecode[41] = (ts["year"] >> 7) & 1
    timecode[42] = (ts["year"] >> 6) & 1
    timecode[43] = (ts["year"] >> 5) & 1
    timecode[44] = (ts["year"] >> 4) & 1
    timecode[45] = (ts["year"] >> 3) & 1
    timecode[46] = (ts["year"] >> 2) & 1
    timecode[47] = (ts["year"] >> 1) & 1
    timecode[48] = ts["year"] & 1
    # populate day of the week
    timecode[50] = (ts["wday"] >> 2) & 1
    timecode[51] = (ts["wday"] >> 1) & 1
    timecode[52] = ts["wday"] & 1
    return timecode


# generate an audio data chunk of specified duration
def gen_audio(duration, freq=OP_FREQ, sr=48000):
    smps = int(sr * duration)
    # create the sine wave array for the whole second
    rawdata = []
    for k in range(0, sr):
        v = math.sin(2 * math.pi * k * freq / sr)
        if k > smps:  # reduced power mode
            v *= 0.1
        rawdata.append(int(v * 32767))  # max gain
    return array.array("h", rawdata).tobytes()


# global buffers for audio data and current position
curstream = b""
streampos = 0


# bitcode transmission callback
def bitcode_transmit(in_data, frame_count, time_info, status):
    global curstream, streampos
    framelen = frame_count << 1  # 2 bytes per frame as we're using int16
    framedata = curstream[streampos: streampos + framelen]
    streampos += framelen
    return (framedata, pyaudio.paContinue)


# main logic is here
def start_transmission(timeparams):
    global curstream
    p = pyaudio.PyAudio()
    sr = timeparams["sr"]
    mins = timeparams["duration"]
    jjy_bit_chunks = [  # pregenerate the chunks
        gen_audio(0.8, OP_FREQ, sr),  # data bit 0
        gen_audio(0.5, OP_FREQ, sr),  # data bit 1
        gen_audio(0.2, OP_FREQ, sr),  # marker bit
    ]
    ts = fetchtime(timeparams)  # get the current timestamp
    print("Time fetched (Unix):", ts["unix"])
    bitcode = gentimecode(ts)[ts["second"] + 1:]  # slice the rest of current minute
    nextmin = ts["unix"] - ts["second"]  # rewind to start of the minute
    for i in range(0, mins):  # generate bitcode for the next N minutes
        nextmin += 60  # calc the next minute
        bitcode += gentimecode(intreptime(nextmin))
    print("Transmitting... Press Ctrl+C to exit")
    # wait for the next second to start (roughly, with all the call overhead)
    time.sleep((1 - datetime.datetime.now().microsecond / 1000000) / 2)
    # open a PyAudio stream with callback
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        frames_per_buffer=16384,
        rate=sr,
        output=True,
        stream_callback=bitcode_transmit,
    )
    curstream = jjy_bit_chunks[bitcode.pop(0)]  # preload the first second
    while stream.is_active():  # wait for the stream to finish
        if len(bitcode) > 0:  # feed the stream in parallel
            curstream += jjy_bit_chunks[bitcode.pop(0)]
        time.sleep(0.75)  # feeding the stream should be faster than realtime
    # close audio
    stream.stop_stream()
    stream.close()
    p.terminate()
    print("Transmission ended")
    return


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser(
        description="JJY.py: an opensource longwave time synchronizer for JJY40-enabled watches and clocks",
        epilog="(c) Luxferre 2024 --- No rights reserved <https://unlicense.org>",
    )
    parser.add_argument(
        "-t",
        "--duration",
        type=int,
        default=60 * 23,
        help="Transmission duration (in minutes, default 23 hrs)",
    )
    parser.add_argument(
        "-d",
        "--delta",
        type=int,
        default=0,
        help="Manual delta correction (in ms, must be determined individually, 0 by default)",
    )
    parser.add_argument(
        "-o",
        "--tz-offset",
        type=float,
        default=7,
        help="Timezone offset from UTC to transmit (in hours, default 7 - corresponds to BKK (Vietnam)",
    )
    parser.add_argument(
        "-r",
        "--sample-rate",
        type=int,
        default=48000,
        help="Transmission sampling rate (in Hz, default 48000)",
    )
    parser.add_argument(
        "-s",
        "--ntp-server",
        type=str,
        default=None,
        help="NTP server to sync from (if not specified then will sync from the local system time)",
    )
    parser.add_argument(
        "-n",
        "--ntp-version",
        type=int,
        default=4,
        help="NTP protocol version to use (default 4)",
    )
    args = parser.parse_args()
    params = {  # populate parameters from the command line
        "server": args.ntp_server,
        "version": args.ntp_version,
        "delta": args.delta,
        "offset": int(args.tz_offset * 3600),
        "sr": args.sample_rate,
        "duration": args.duration,
    }

    start_transmission(params)
