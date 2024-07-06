#!/bin/sh

if [[ $# -ne 3 ]]; then
    cat << EOF
Usage: $0 <upload-port> <start channel> <stop channel>

EOF
    exit -1
fi

PORT=$1

for channel in $(seq $2 $3); do
    export PLATFORMIO_BUILD_FLAGS=-DCHANNEL=${channel}
    # export PLATFORMIO_BUILD_FLAGS="${PLATFORMIO_BUILD_FLAGS} -DSERIAL_DEBUG"

    echo Flashing channel $channel via $PORT with flags [${PLATFORMIO_BUILD_FLAGS}]
    read -p "Ready? [yn]" -n 1 input
    echo
    case $input in
        y)  ;;
        *)  exit -2
            ;;
    esac

    python -m platformio run -e transmitter -t upload --upload-port ${PORT}

    python -m platformio device monitor -p ${PORT} --no-reconnect
done
