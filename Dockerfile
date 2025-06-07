FROM ubuntu:22.04
COPY time-signal .
CMD ./time-signal  -v -s JJY60
