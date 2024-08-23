#!/bin/bash

cp ./lostdogs.docker.service /etc/systemd/system
systemctl daemon-reload
systemctl enable lostdogs.docker.service