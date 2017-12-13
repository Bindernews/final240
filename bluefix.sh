#!/bin/bash
# Fixes weird bugs with bluetooth on the Raspberry Pi. Must run as root.

function getpids {
  echo $(ps aux | grep "$1" | head -n-1 | awk '{print $2}')
}

service bluetooth stop
procs=$(getpids "bluetoothd")
if [ -n "$procs" ]; then
  kill $procs
fi
procs=$(getpids "obexpushd")
if [ -n "$procs" ]; then kill $procs; fi
bluetoothd --compat &
