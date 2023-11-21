# Video concat

I use `Shadowplay` and `losslessCut` to record gaming videos, for this
specific combination, the clip name can be used to generate chapter metadata
when concatenating clips.  
This script parse clips under a base directory, create an `Output` object.
This object generate required project folder and scripts, provide move/copy
functions to manage the clips, and can spawn subprocess to run ffmpeg command
to concat the clips.

# Requirements
* `ffmpeg`
* `python3` 

# Usage
Use the script in python interactive mode:
```sh
python -i script.py -b <base dir> -o <output dir>
```
Then available commands:
* `read()`: read clips information
* `reread()`: re-read from base directory
* `move_and_run()`: move clips into project folder, generate project files and run `ffmpeg` to concat the clips

Outputs:
* merged video with chapter metadata embedded
* `chapter.ffmetadata`: chapter metadata based on file name in ffmpeg metadata format
* `chapter.txt`: youtube chapter format in plain text
* `script.sh`: the ffmpeg concat script
* `inputs.txt`: contains the clips' path, used by ffmpeg command in `script.sh`
