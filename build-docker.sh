#!/bin/bash

echo "Building TribunaliBot docker images"
docker build --tag 'tribunalibot-base' ./ &&
    {
        docker build --tag "tribunalibot-telegram" ./telegram
        docker build --tag "tribunalibot-postman" ./postman
        docker build --tag "tribunalibot-sherlock" ./sherlock
    }
wait
