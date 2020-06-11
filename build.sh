#!/bin/bash
docker build --force-rm -t amoffat/receipts\
    --build-arg uid=$UID\
    --build-arg gid=$UID\
    .
