JJY.py: sync JJY40-enabled watches and clocks from Python 3
-----------------------------------------------------------
This is a Python port of the 7-year old "Project Fukushima" JJY40 emulator
for syncing longwave-enabled watches and clocks that support this station.
With the help of any sort of loop antenna (or even headphones or speakers), it
allows you to adjust your watch without having to be close to the Japanese
signal. This program follows the JJY timecode specification and modulation
methods used by the oldest desktop applications for this very purpose, and
transmits on 13333.(3) Hz, whose 3rd harmonic is the reference frequency,
40 KHz, but the base frequency here is within the spectrum supported by any
consumer-grade audio hardware.

== Dependencies ==

JJY.py depends on PyAudio (>=0.2.14) and ntplib (>=0.4.0). Just install them
by running pip install -r requirements.txt from the project directory. Note
that installing PyAudio will also pull its PortAudio (>=v19) dependency.

The program has been primarily tested on Python 3.10.

== Usage ==

JJY.py can be run like this:

python jjy.py [-t duration] [-d delta] [-s ntp_server] [-n ntp_version] \
              [-o tz_offset] [-r sample_rate]

All parameters are optional here:

* -h: display help screen
* -t: transmission duration in minutes (default 30)
* -d: manual delta correction in milliseconds (default 0, see below)
* -o: timezone offset from UTC (in hours, default 9, see below)
* -r: transmission sampling rate (in Hz, default 48000, only change if this
      fails to work)
* -s: specify NTP server to fetch time from (if no server is specified, then
      local system time is used)
* -n: specify NTP protocol version to use, default is 4, good for most cases

After running the command, you must enter the synchronization mode on your
watch/clock (making sure that JJY40 is selected if it's multiband) and put it
close enough to your (improvised) loop antenna, headphones or speakers. The
script will fetch the UTC time according to your source, apply the TZ offset,
then the manual delta offset and then will attempt to start the transmission
from the closest second. The TZ offset is set to +9 hours by default because
most JJY-enabled watches/clocks expect the JST time to be sent in order to
then apply their own timezone correction according to your settings. If your
watch/clock doesn't have such correction, you can always use this -o flag to
zero out this offset (with -o 0) and transmit the local time directly onto it.
In case your equipment, software or time source server introduce any delay to
the synchronization process, you can add a constant delta (in milliseconds)
with the -d flag. E.g. Citizens tend to lag behind an entire second with my
equipment (unlike Casios), so the -d 1000 parameter is usually helpful for me.

After the synchronization is successful, you can press the
Ctrl+C combination or wait until the entire sequence (which is 30 minutes long
by default, adjustable with -t flag) gets transmitted.

== FAQ ==

- How is this even possible?

To put it simply, to emit any audio signal, electricity has to travel through
many wires and coils. This inevitably creates electromagnetic interference. If
we send the signal of a particular constant frequency with enough intensity
through audio circuits, this interference will turn into radio emission in the
longwave spectrum, which is exactly what we need for syncing radio-controlled
clocks and watches. This emission is too weak to cause any harm outside but
enough to be received by the watch or clock several centimeters apart.

- Which watches/clocks has this been tested on?

Some Casio and Citizen models, including Casio GW-B5600BC, GMW-B5000D and
Citizen PMD56-2951.

- Is my particular watch/clock model supported?

As long as it can receive JJY40 signal and you know how to make it do this, it
is automatically supported by JJY.py. At this point, I can surely say that if 
anything goes wrong, it's not the fault of your watch or your emulator, but 
something in between: audio setup, antenna setup or the placement of the watch
relative to the antenna. It might take some trial and error and a great deal
of patience to make sure everything works as expected.

For most digital Casio models, you can force JJY40 reception by entering one
of the test menus: press and hold first Light, then Receive and then Mode
button. Scroll through with the Receive button to ensure that "J 40" is on the
screen, then start the reception process with the Light button. You should get
a "JOK" message if the process is successful, or "JNG" if unsuccessful.

- Aren't there enough JJY emulation apps already?

In 2017, there were almost no cross-platform solutions for this, and this was
the primary reason the Fukushima project started. However, even in 2024, I
could not find any Python solution for this meant for normal desktop and not
for Raspberry Pi, Arduino and other embedded platforms. That's why a port of
the JJY.js library to Python was deemed necessary.

- Are there still any plans for implementing other longwave time protocols?

Maybe. DCF77 and WWVB are of the primary interest.

== Credits ==

Original research, JS library and web demo application by Luxferre, 2017.
Ported to Python in 2024. Released into public domain with no warranties.
