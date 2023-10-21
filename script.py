# Contributors
# ---------------------------
# En-Ho Shen <enhoshen@gmail.com>, 2023

import ffmpeg
import os
import re
import datetime
from dataclasses import dataclass


@dataclass
class Time:
    hr: int=0
    min: int=0
    sec: int=0
    msec: int=0

    def __str__(self) -> str:
        return f"{self.hr:02}.{self.min:02}.{self.sec:02}.{self.msec:04}"

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
class Chapter:
    name: str
    date: str
    time: str 
    length: Time
    probe: dict


class Splicer:
    def __init__(self):
        pass

    def init(self):
        base = "./"
        files = os.listdir(base)
        files = [f for f in files if re.match(r".*\.mp4$", f)]
        return files

    def basic_pattern(self) -> str:
        """Return basic pattern strings"""
        name = r"(.*)"
        date = r"(\d{4}\.\d{2}\.\d{2})"
        time = r"(\d{2}\.\d{2}\.\d{2}\.\d{3})"
        filetype = r"(\.DVR\.mp4)"
        return fr"{name} {date} - {time}{filetype}"

    def cut_pattern(self) -> str:
        start = r"(\d{2}\.\d{2}\.\d{2}\.\d{3})"
        end = r"(\d{2}\.\d{2}\.\d{2}\.\d{3})"
        return fr"{start}-{end}"

    def time_pattern(self) -> str:
        return r"(\d{2})\.(\d{2})\.(\d{2})\.(\d{3})"

    def parse(self, name: str) -> Chapter:
        """Parse file name to Chapter"""
        # discard first element which is an empty string
        probe = ffmpeg.probe(name)
        name, date, time, filetype, rest = (
            re.split(self.basic_pattern(), name)[1:]
        )
        # length is in sec
        length: float = float(probe["format"]["duration"])
        chapter = Chapter(
            name=name,
            date=date,
            time=time,
            length=Time().from_sec(length),
            probe=probe,
        )
        return chapter


class Test:
    pass


def concat():
    (ffmpeg.concat())


if __name__ == "__main__":
    splice = Splicer()
    files = splice.init()
    ch = splice.parse(files[0])

