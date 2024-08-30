#!/bin/sh

if [[ $# -ne 4 ]]; then
    cat << EOF
Usage: $0 <board-version> <upload-port> <start channel> <stop channel>

EOF
    exit -1
fi

VERSION=$1
PORT=$2
START=$3
STOP=$4


for channel in $(seq $START $STOP); do
    export PLATFORMIO_BUILD_FLAGS=-DCHANNEL=${channel}
    # export PLATFORMIO_BUILD_FLAGS="${PLATFORMIO_BUILD_FLAGS} -DSERIAL_DEBUG_TRACKER"

    echo Flashing channel $channel to board version ${VERSION} via $PORT with flags [${PLATFORMIO_BUILD_FLAGS}]
    read -p "Ready? [yn]" -n 1 input
    echo
    case $input in
        y)  ;;
        *)  exit -2
            ;;
    esac

    python -m platformio run -e transmitter-v${VERSION} -t upload --upload-port ${PORT}

    python -m platformio device monitor -p ${PORT} --no-reconnect
done
