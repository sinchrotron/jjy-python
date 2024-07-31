import array
import datetime
import logging
import math
import ntplib
import pyaudio
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
logger.addHandler(handler)


OP_FREQ = 40000 / 3  # emitted frequency, Hz


# BCD and parity calculation helpers


def to_bcd(val: int):
    return (val % 10) + ((val // 10 % 10) << 4) + (val // 100 << 8)


def calc_parity(val: int):
    parity = 0
    while val:
        parity ^= val & 1
        val >>= 1
    return parity


# internal time representation from unix time
# only fetches the fields necessary for JJY implementation
def unix_time_to_dict(unix_time):
    time_in_utc = time.gmtime(unix_time)

    values_mapping = {
        "year": to_bcd(time_in_utc.tm_year % 100),
        "yday": to_bcd(time_in_utc.tm_yday),
        "hour": to_bcd(time_in_utc.tm_hour),
        "minute": to_bcd(time_in_utc.tm_min),
        "second": time_in_utc.tm_sec,
        "wday": (time_in_utc.tm_wday + 1)
        % 7,  # In Python, Monday is 0; in JJY, Sunday is 0
        "unix": int(unix_time),  # save the unix time representation
    }

    return values_mapping


# time fetching part (returns JST)
def fetch_time(parameters=None):
    delta = parameters.get("delta", 0) / 1000
    offset = parameters.get("offset", 32400)
    try:
        ntp_version = parameters.get("version", 3)
        unix_time = ntplib.NTPClient().request(parameters["server"], version=ntp_version)
        logger.info(f"Using time from NTP server {parameters['server']}")
    except Exception as e:
        logger.info(f"Failed to fetch time from NTP server {parameters['server']}")
        logger.info("Using local time")
        unix_time = time.time()
    return unix_time_to_dict(unix_time + offset + delta)


# timecode generation part
# accepts the result of fetchtime function
def generate_timecode(ts):
    timecode = [2] * 60
    bit_indices = {
        "minute": [1, 2, 3, 5, 6, 7, 8],
        "hour": [12, 13, 15, 16, 17, 18],
        "yday": [22, 23, 25, 26, 27, 28, 30, 31, 32, 33],
        "year": [41, 42, 43, 44, 45, 46, 47, 48],
        "wday": [50, 51, 52],
    }
    for key, indices in bit_indices.items():
        value = ts[key]
        for index in indices:
            timecode[index] = (value >> indices.index(index)) & 1
    timecode[36] = calc_parity(ts["hour"])
    timecode[37] = calc_parity(ts["minute"])
    return timecode


# generate an audio data chunk of specified duration
def gen_audio(duration, freq=OP_FREQ, sr=48000):
    samples = int(sr * duration)
    # create the sine wave array for the whole second
    rawdata = []
    for k in range(0, sr):
        v = math.sin(2 * math.pi * k * freq / sr)
        if k > samples:  # reduced power mode
            v *= 0.1
        rawdata.append(int(v * 32767))  # max gain
    return array.array("h", rawdata).tobytes()


# global buffers for audio data and current position
current_stream = b""
stream_pos = 0


# bitcode transmission callback
def bitcode_transmit(in_data, frame_count, time_info, status):
    global current_stream, stream_pos
    frame_len = frame_count << 1  # 2 bytes per frame as we're using int16
    frame_data = current_stream[stream_pos : stream_pos + frame_len]
    stream_pos += frame_len
    return frame_data, pyaudio.paContinue


# main logic is here
def start_transmission(time_params):
    global current_stream
    p = pyaudio.PyAudio()
    sr = time_params["sr"]
    mins = time_params["duration"]
    jjy_bit_chunks = [  # pre-generate the chunks
        gen_audio(0.8, OP_FREQ, sr),  # data bit 0
        gen_audio(0.5, OP_FREQ, sr),  # data bit 1
        gen_audio(0.2, OP_FREQ, sr),  # marker bit
    ]
    ts = fetch_time(time_params)  # get the current timestamp
    logger.info("Time fetched:", ts)
    logger.info(f"Timezone: {int(time_params['offset'] / 3600)}")
    bitcode = generate_timecode(ts)[
        ts["second"] + 1 :
    ]  # slice the rest of current minute
    next_min = ts["unix"] - ts["second"]  # rewind to start of the minute
    for _ in range(mins):  # generate bitcode for the next N minutes
        next_min += 60  # calc the next minute
        bitcode += generate_timecode(unix_time_to_dict(next_min))
    logger.info(
        f"Transmitting for {params['duration']} minutes... Press Ctrl+C to exit"
    )
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
    current_stream = jjy_bit_chunks[bitcode.pop(0)]  # preload the first second
    try:
        while stream.is_active():
            if bitcode:
                current_stream += jjy_bit_chunks[bitcode.pop(0)]
            time.sleep(0.75)
    except KeyboardInterrupt:
        logger.info("Transmission interrupted by user")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        logger.info("Transmission ended")


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser(
        description="JJY.py: an opensource long wave time synchronizer for JJY40-enabled watches and clocks",
    )
    parser.add_argument(
        "-t",
        "--duration",
        type=int,
        default=4 * 60,
        help="Transmission duration (in minutes, default 4 hrs)",
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
        help="Timezone offset from UTC to transmit (in hours, default 7 - corresponds to BKK)",
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
