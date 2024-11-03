# The video source base directory
BASE=$1
# The video bitrate in M
BITRATE=$2

OUT=compressed
echo base=$1";" bitrate=$BITRATE
cd "$BASE"
mkdir ${OUT}
IFS='
'
for i in $( ls *.mp4 ); do 
    ffmpeg -i $i -c:v hevc_nvenc -preset fast \
        -b:v ${BITRATE}M \
        -ar 48000 \
        -r 60 \
        -b:a 192k \
        -f mp4 -y ${BASE}/${OUT}/$( basename $i )
done;
exit 0;
