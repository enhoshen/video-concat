#!/bin/bash
# The video source base directory
BASE=$1
# The video bitrate in M
BITRATE=$2

OUT=compressed
echo base=$1";" bitrate=$BITRATE
cd "$BASE"
mkdir ${OUT}
# Set separator to newline, ignore tab and space
IFS='
'
for i in $( ls *.mp4 ); do 
    bitrate=$(ffprobe -v quiet -select_streams v:0 -show_entries \
        stream=bit_rate $i | grep -E "[0-9]*" -o)
    if (( ${bitrate} > (${BITRATE} + 1)* 1000000 )); then
        ffmpeg -i $i -c:v hevc_nvenc -preset fast \
            -b:v ${BITRATE}M \
            -ar 48000 \
            -r 60 \
            -b:a 192k \
            -f mp4 -y ${BASE}/${OUT}/$( basename $i )
    else;
        echo skipping $i with bitrate: $bitrate
    fi;
done;
exit 0;
