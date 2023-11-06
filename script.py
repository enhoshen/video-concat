# Contributors
# ---------------------------
# En-Ho Shen <enhoshen@gmail.com>, 2023

import ffmpeg
import path
import re
from typing import List, Optional
from dataclasses import dataclass
import logging
import subprocess


logger = logging.getLogger()

@dataclass
class Time:
    hr: int=0
    min: int=0
    sec: int=0
    msec: int=0

    def __post_init__(self):
        """support for init with str"""
        self.hr = int(self.hr)
        self.min = int(self.min)
        self.sec = int(self.sec)
        self.msec = int(self.msec)
        # if msec is 4 digits
        if self.msec >= 1000:
            self.msec = int(self.msec//10)

    def __str__(self) -> str:
        return f"{self.hr:02}.{self.min:02}.{self.sec:02}.{self.msec:0<4}"

    def to_text(self) -> str:
        """To youtube chapter text"""
        return f"{self.hr:02}:{self.min:02}:{self.sec:02}"

    def to_msec(self) -> int:
        hr = self.hr*3600
        min = self.min*60
        sec = self.sec
        msec = self.msec
        return ((hr+min+sec)*1000) + msec

    def from_sec(self, num: float):
        sec = int(num)
        self.msec = int((num-sec)*1000)
        min = sec // 60
        self.sec = sec % 60
        self.hr = min // 60
        self.min = min % 60
        return self


@dataclass
class Cut:
    start: Time
    end: Time

    def __str__(self):
        return f"{self.start}-{self.end}"


@dataclass
class Chapter:
    name: str
    date: str
    time: str 
    length: Time
    cut: Optional[Cut]

    def to_text(self, start: int):
        """
        Produce youtube chapter text
        Args:
        start: int
            start time in msec, the end time of the previous chapter
        """
        start = Time().from_sec(float(start/1000))
        cut = "" if self.cut is None else " "+str(self.cut)
        s = f"{start.to_text()} {self.date}-{self.time}{cut}\n"
        return s


    def to_meta(self, start: int):
        """
        Produce ffmpeg chapter metadata
        Args:
        start: int
            start time in msec, the end time of the previous chapter
        """
        end = start + self.length.to_msec()
        cut = "" if self.cut is None else " "+str(self.cut)
        s = ("[CHAPTER]\n"
            f"TIMEBASE=1/1000\n"
            f"START={start}\n"
            f"END={end}\n"
            f"title={self.date}-{self.time}{cut}\n"
        )
        return s

@dataclass
class Clip:
    path: path.Path
    probe: dict
    ch: Chapter


class Clips:
    def __init__(self, clips: List[Clip]):
        if len(clips) <= 0:
            logger.warning(f"no clip candidates")
        self.clips = clips

    def accum(self):
        """Accumulate start time of each chapters in msec"""
        lengths = [clip.ch.length.to_msec() for clip in self.clips]
        starts = [0]
        for i in lengths:
            starts.append(starts[-1] + i)
        return starts

    @property
    def title(self) -> str:
        if len(self.clips) <= 0:
            return ""
        title = (f"{self.clips[0].ch.name} "
            f"{self.clips[0].ch.date}-{self.clips[0].ch.time} "
            f"{self.clips[-1].ch.date}-{self.clips[-1].ch.time}"
        )
        return title

    def meta(self) -> List[str]:
        starts = self.accum()
        meta = [
            clip.ch.to_meta(start) for clip, start in zip(self.clips, starts)]
        return meta

    def text(self) -> List[str]:
        starts = self.accum()
        text = [
            clip.ch.to_text(start) for clip, start in zip(self.clips, starts)]
        return text 

    def __iter__(self):
        for c in self.clips:
            yield c

class Parser:
    """
    Parse file name produced by shadowplayer recording and lossless cut
    program, and probe dictionary from ffmpeg.probe(), convert to struct
    and output concated video with updated metadate containing chapter
    information
    """
    def files(self, base: path.Path):
        files = base.listdir()
        files = [path.Path(f) for f in files if re.match(r".*\.mp4$", str(f))]
        return files

    def clips(self, files: List[path.Path]) -> Clips:
        clips = [self.parse(file) for file in files]
        clips = [clip for clip in clips if clip is not None]
        return Clips(clips)

    def basic_pattern(self) -> str:
        """Return basic pattern strings"""
        name = r"(.*)"
        date = r"(\d{4}\.\d{2}\.\d{2})"
        time = r"(\d{2}\.\d{2}\.\d{2})"
        index = r"(\.\d*)" 
        filetype = r"(\.DVR(\.mp4)?)"
        return fr"{name} {date} - {time}{index}{filetype}"

    def cut_pattern(self) -> str:
        start = r"(\d{2}\.\d{2}\.\d{2}\.\d{3})"
        end = r"(\d{2}\.\d{2}\.\d{2}\.\d{3})"
        return fr"{start}-{end}"

    def time_pattern(self) -> str:
        return r"(\d{2})\.(\d{2})\.(\d{2})\.(\d{3})"

    def parse_cut(self, s: str) -> Optional[Cut]:
        cut = None
        if s != "":
            start, end, *_= re.split(self.cut_pattern(), s)[1:]
            _, *start, _ = re.split(self.time_pattern(), start)
            _, *end, _ = re.split(self.time_pattern(), end)
            cut = Cut(start=Time(*start), end=Time(*end))
        return cut

    def parse(self, file: path.Path) -> Optional[Clip]:
        """Parse file name to Clip"""
        # discard first element which is an empty string
        probe = ffmpeg.probe(file)
        try:
            name, date, time, index, DVR, mp4, rest = (
                re.split(self.basic_pattern(), str(file.basename()))[1:]
            )
        except ValueError:
            logger.warning(f"{file} is not a match")
            return None

        # length is in sec
        length: float = float(probe["format"]["duration"])
        chapter = Chapter(
            name=name,
            date=date,
            time=time,
            length=Time().from_sec(length),
            cut = self.parse_cut(rest)
        )
        clip = Clip(path=file, probe=probe,ch=chapter)
        return clip 


class Output:
    def __init__(self, clips: Clips, base:str="./", out_dir=None):
        self.clips = clips
        self.base = path.Path(base)
        self.out_dir = self.base if out_dir is None else path.Path(out_dir)
        self.out_dir = self.out_dir.joinpath(self.clips.title)
        self.meta_path = self.out_dir.joinpath("chapter.ffmetadata")
        self.text_path = self.out_dir.joinpath("chapter.txt")
        self.script_path = self.out_dir.joinpath(f"script.txt")
        try:
            self.out_dir.mkdir(mode=711)
        except FileExistsError:
            pass

    def meta(self) -> None:
        with open(self.meta_path, 'w') as file:
            file.write(f"title={self.clips.title}\n")
            meta = self.clips.meta()
            file.write("".join(meta))

    def text(self) -> None:
        with open(self.text_path, 'w') as file:
            file.write(f"{self.clips.title}\n")
            text = self.clips.text()
            file.write("".join(text))

    @property
    def concat(self) -> ffmpeg.nodes.OutputStream:
        out = self.out_dir.joinpath(f"{self.clips.title}.mp4")
        streams = [ffmpeg.input(c.path) for c in self.clips]
        concat = (ffmpeg.concat(*streams)
            .output(out)
        )
        return concat

    @property
    def map_chapter(self) -> List[str]:
        out_kwargs = [
            "-map_metadata", "0", 
            "-map_chapters", "-1", 
            "-movflags", "use_metadata_tags", 
            "-movflags", "+faststart", 
            ]
        meta_kwargs = [
            "-f", "ffmetadata",
            "-i", f"{self.meta_path}"
        ]
        cmd = self.concat.compile() 
        cmd = cmd[:-3] + meta_kwargs + out_kwargs + cmd[-3:]
        return cmd

    def script(self):
        with open(self.script_path, 'w') as file:
            file.write(subprocess.list2cmdline(self.concat.compile()))
            file.write('\n')
            file.write(subprocess.list2cmdline(self.map_chapter))

    def run(self):
        return subprocess.Popen(self.map_chapter)

    def move(self):
        for c in self.clips:
            c.path = c.path.move(self.out_dir.joinpath(c.path.basename()))

    def project(self, move: bool=True):
        self.meta()
        self.text()
        if move:
            self.move()
        self.script()


class Test:
    pass


def read(args) -> Output:
    parser = Parser()
    files = parser.files(path.Path(args.base))
    clips = parser.clips(files)
    output = Output(clips, args.base, args.out_dir)
    return output


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        prog="VideoConcat",
        description=(
            "Produce chapter metadata/text from video names produced "
            "combination of shadowplay and losslesscut",
        ),
    )
    parser.add_argument("-b", "--base", action="store")
    parser.add_argument("-o", "--out_dir", action="store")
    parser.add_argument("-m", "--move", action="store_true")
    args = parser.parse_args()
    output = read(args)
