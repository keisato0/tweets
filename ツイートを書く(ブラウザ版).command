#!/bin/bash
cd "$(dirname "$0")"

(python3 compose_server.py > /tmp/tweets_compose_server.log 2>&1 &)
sleep 1
open "http://localhost:8765/"
