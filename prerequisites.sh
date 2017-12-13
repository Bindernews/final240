#!/bin/bash
# Run this to install all the prerequisites

# We need pip3, obexpushd, and python3-pyocr
sudo apt-get install python3-pip obexpushd python3-pyocr
# Now we can install lark-parser and pyinotify (these are installed globally)
sudo pip3 install lark-parser pyinotify
