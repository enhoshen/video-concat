# Contributors
# ---------------------------
# En-Ho Shen <enhoshen@gmail.com>, 2025

import path
import re
from typing import List, Dict, Optional, Tuple, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod
import logging
import subprocess
from datetime import datetime, date, time, timedelta

from jinja2 import Environment, FileSystemLoader, select_autoescape
import ffmpeg
import yaml


logger = logging.getLogger()


class TimeToText(ABC):
    @abstractmethod
    def text(self, time: timedelta) -> str:
        ...


class All(TimeToText):
    def text(self, time: timedelta) -> str:
        total_seconds = int(time.total_seconds())
        hr = total_seconds // 3600
        min = (total_seconds % 3600) // 60
        sec = total_seconds % 60
        msec = int(time.microseconds / 1000)
        return f"{hr:02}.{min:02}.{sec:02}.{msec:0<4}"


class YoutubeTimestamp(TimeToText):
    def text(self, time: timedelta) -> str:
        total_seconds = int(time.total_seconds())
        hr = total_seconds // 3600
        min = (total_seconds % 3600) // 60
        sec = total_seconds % 60
        return f"{hr:02}:{min:02}:{sec:02}"


class NoHr(TimeToText):
    def text(self, time: timedelta) -> str:
        total_seconds = int(time.total_seconds())
        min = (total_seconds % 3600) // 60
        sec = total_seconds % 60
        return f"{min:02}:{sec:02}"


class DateTimeSec(TimeToText):
    def text(self, time: timedelta) -> str:
        return time.strftime("%m.%d-%H.%M.%S")


@dataclass
class Cut:
    start: timedelta
    end: timedelta
    style: TimeToText = NoHr()

    def __str__(self):
        start = self.style.text(time=self.start)
        end = self.style.text(time=self.end)
        return f"{start}-{end}"


@dataclass
class Chapter:
    name: str
    date: datetime
    time: timedelta
    length: timedelta
    index: str
    cut: Optional[Cut]
    comment: str = ""

    def __post_init__(self):
        self.yt_timestamp = YoutubeTimestamp()
        self.datetime_fmt = DateTimeSec()

    def to_text(self, start: int) -> str:
        """
        Produce youtube chapter text
        Args:
        start: int
            start time in msec, the end time of the previous chapter
        """
        start_td = timedelta(milliseconds=start)
        cut = self.cut
        cut_start = cut.start if cut is not None else timedelta(0)
        date_start = self.date + self.time + cut_start
        date_time_str = self.datetime_fmt.text(date_start)
        date_start_str = date_time_str
        s = f"{self.yt_timestamp.text(start_td)} {date_start_str}"
        if self.comment != "":
            s = f"{s} {self.comment}"
        return s + "\n"

    def to_meta(self, start: int) -> str:
        """
        Produce ffmpeg chapter metadata
        Args:
        start: int
            start time in msec, the end time of the previous chapter
        """
        end = start + int(self.length.total_seconds() * 1000)
        cut = "" if self.cut is None else " " + str(self.cut)
        date_str = self.date.strftime("%Y.%m.%d")
        time_str = (datetime.min + self.time).time().strftime("%H.%M.%S")
        s = (
            "[CHAPTER]\n"
            f"TIMEBASE=1/1000\n"
            f"START={start}\n"
            f"END={end}\n"
            f"title={date_str}-{time_str}{cut}\n"
            f"index={self.index}\n"
        )
        if self.comment != "":
            s += f"comment={self.comment}\n"
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
        lengths = [
            int(clip.ch.length.total_seconds() * 1000) for clip in self.clips
        ]
        starts = [0]
        for i in lengths:
            starts.append(starts[-1] + i)
        return starts

    @property
    def title(self) -> str:
        if len(self.clips) <= 0:
            return ""
        c0 = self.clips[0].ch
        cn = self.clips[-1].ch
        c0_date = c0.date.strftime("%Y.%m.%d")
        c0_time = (datetime.min + c0.time).time().strftime("%H.%M.%S")
        cn_date = cn.date.strftime("%Y.%m.%d")
        cn_time = (datetime.min + cn.time).time().strftime("%H.%M.%S")
        title = f"{c0.name} " f"{c0_date}-{c0_time} " f"{cn_date}-{cn_time}"
        return title

    def meta(self) -> List[str]:
        starts = self.accum()
        meta = [
            clip.ch.to_meta(start) for clip, start in zip(self.clips, starts)
        ]
        return meta

    def text(self) -> List[str]:
        starts = self.accum()
        text = [
            clip.ch.to_text(start) for clip, start in zip(self.clips, starts)
        ]
        return text

    def text_with_index(self) -> List[str]:
        starts = self.accum()
        text = [
            f"{clip.ch.index}-{clip.ch.to_text(start)}"
            for clip, start in zip(self.clips, starts)
        ]
        return text

    def __iter__(self):
        for c in self.clips:
            yield c

    @property
    def paths(self) -> str:
        return [str(c.path) for c in self.clips]


class Pattern(ABC):
    @abstractmethod
    def re(self) -> str:
        ...

    @abstractmethod
    def parse(self, inpt: str) -> str:
        ...


@dataclass
class ClipInfo:
    name: str
    date: datetime
    time: timedelta
    index: str = ""


class Basic(Pattern):
    def re(self) -> str:
        """Return basic pattern strings"""
        name = r"(.*)"
        date = r"(\d{4}\.\d{2}\.\d{2})"
        time = r"(\d{2}\.\d{2}\.\d{2})"
        index = r"\.(\d*)"
        filetype = r"(\.DVR(\.mp4)?)"
        return rf"{name} {date} - {time}{index}{filetype}"

    def cut_pattern(self) -> str:
        start = r"(\d{2}\.\d{2}\.\d{2}\.\d{3})"
        end = r"(\d{2}\.\d{2}\.\d{2}\.\d{3})"
        return rf"{start}-{end}"

    def time_pattern(self) -> str:
        return r"(\d{2})\.(\d{2})\.(\d{2})\.(\d{3})"

    def parse_cut(self, s: str) -> Optional[Cut]:
        cut = None
        if s != "":
            start, end, *_ = re.split(self.cut_pattern(), s)[1:]
            _, *start, _ = re.split(self.time_pattern(), start)
            _, *end, _ = re.split(self.time_pattern(), end)
            start_ints = [int(x) for x in start]
            end_ints = [int(x) for x in end]
            cut_start = timedelta(
                hours=start_ints[0],
                minutes=start_ints[1],
                seconds=start_ints[2],
                milliseconds=start_ints[3],
            )
            cut_end = timedelta(
                hours=end_ints[0],
                minutes=end_ints[1],
                seconds=end_ints[2],
                milliseconds=end_ints[3],
            )
            cut = Cut(start=cut_start, end=cut_end)
        return cut

    def parse(self, inpt: str) -> Tuple[ClipInfo, Optional[Cut]]:
        name, date_str, time_str, index, DVR, mp4, rest = re.split(
            self.re(), inpt
        )[1:]
        dt_obj = datetime.strptime(
            f"{date_str} {time_str}", "%Y.%m.%d %H.%M.%S"
        )
        date_val = datetime(dt_obj.year, dt_obj.month, dt_obj.day)
        time_val = timedelta(
            hours=dt_obj.hour, minutes=dt_obj.minute, seconds=dt_obj.second
        )
        clip = ClipInfo(
            name=name,
            date=date_val,
            time=time_val,
            index=index,
        )
        cut = None
        if rest:
            cut = self.parse_cut(s=rest)
        return clip, cut


def temporary_pattern(self) -> str:
    """Return old basic pattern strings"""
    name = r"(.*)"
    date = r"(\d{4} \d{2} \d{2})"
    time = r"(\d{2} \d{2} \d*)"
    # time = r"(\d{2} \d{2}})"
    index = r"( \d*)"
    # filetype = r"( DVR(\.mp4)?)"
    filetype = r"(\.mp4)"
    # return rf"{name} {date}   {time}{index}{filetype}"
    #
    #        # name, date, time, index, DVR, mp4, rest = re.split(
    #    try:
    #        name, date, time, rest = re.split(
    #            self.temporary_pattern(), str(file.basename())
    #        )[1:]
    #        no_match = False
    #        cut = ""
    #    except ValueError:
    #        pass
    return rf"{name} {date}   {time}"


class CommentParser:
    def parse(self, file_path: str) -> Dict[str, Union[str, List[str]]]:
        """Reads comments from a YAML file and returns a dictionary mapping index to comment(s)."""
        comments: Dict[str, Union[str, List[str]]] = {}
        if not file_path:
            return comments
        try:
            with open(file_path, "r") as f:
                content = f.read()

            # Preprocess to add colons for list-like indexes if they are missing
            # Matches "- 123" followed by a newline and an indented list item "- "
            content_fixed = re.sub(r"(^\s*-\s+\d+)\s*\n(?=\s+-)", r"\1:\n", content, flags=re.MULTILINE)

            data = yaml.safe_load(content_fixed)
            if data is None:
                return comments

            if isinstance(data, dict):
                for k, v in data.items():
                    comments[str(k)] = v
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        for k, v in item.items():
                            comments[str(k)] = v
                    else:
                        logger.warning(f"Unexpected item type in comment file: {item}")
            else:
                logger.warning(f"Unexpected root type in comment file: {type(data)}")
        except FileNotFoundError:
            logger.error(f"Comment file not found: {file_path}")
        except Exception as e:
            logger.error(f"Error reading comment file {file_path}: {e}")
        return comments


class Parser:
    """
    Parse file name produced by shadowplayer recording and lossless cut
    program, and probe dictionary from ffmpeg.probe(), convert to struct
    and output concated video with updated metadate containing chapter
    information
    """

    def __init__(self) -> None:
        self.patterns = [Basic()]
        self._index_counters = {}

    def files(self, base: path.Path):
        files = base.listdir()
        files = [path.Path(f) for f in files if re.match(r".*\.mp4$", str(f))]
        return files

    def clips(
        self, files: List[path.Path], comment_map: Dict[str, Union[str, List[str]]]
    ) -> Clips:
        self._index_counters = {}
        clips = [
            self.parse(file=file, comment_map=comment_map) for file in files
        ]
        clips = [clip for clip in clips if clip is not None]
        return Clips(clips)

    def parse_info(
        self,
        file: path.Path,
    ) -> Optional[Tuple[ClipInfo, Union[str, Cut]]]:
        no_match = True
        for p in self.patterns:
            try:
                clip_info, cut = p.parse(str(file.basename()))
                no_match = False
                continue
            except ValueError:
                no_match = True

        if no_match:
            logger.warning(f"{file} is not a match")
            return None
        return clip_info, cut

    def parse(
        self, file: path.Path, comment_map: Optional[Dict[str, Union[str, List[str]]]] = None
    ) -> Optional[Clip]:
        """Parse file name to Clip"""
        # discard first element which is an empty string
        probe = ffmpeg.probe(file)
        info = self.parse_info(file=file)
        if info is None:
            return None
        clip_info, cut = info

        # length is in sec
        length: float = float(probe["format"]["duration"])
        
        comment = ""
        if comment_map is not None:
            if not hasattr(self, "_index_counters"):
                self._index_counters = {}
            sub_index = self._index_counters.get(clip_info.index, 0)
            self._index_counters[clip_info.index] = sub_index + 1
            
            val = comment_map.get(clip_info.index)
            if isinstance(val, list):
                if sub_index < len(val):
                    comment = val[sub_index]
            elif isinstance(val, str):
                if sub_index == 0:
                    comment = val
            elif val is not None:
                if sub_index == 0:
                    comment = str(val)

        chapter = Chapter(
            name=clip_info.name,
            date=clip_info.date,
            time=clip_info.time,
            length=timedelta(seconds=length),
            index=clip_info.index,
            cut=cut,
            comment=comment,
        )
        clip = Clip(path=file, probe=probe, ch=chapter)
        return clip


@dataclass
class CompressionConfig:
    enable: bool = False
    bitrate: int = 0


class Output:
    def __init__(
        self,
        clips: Clips,
        base: str = "./",
        out_dir=None,
        compress: CompressionConfig = CompressionConfig(),
        template_path=None,
    ):
        self.clips = clips
        self.base = path.Path(base)
        self.compress = compress
        self.template_path = (
            "./"
            if template_path is None
            else path.Path(template_path).dirname()
        )
        self.template_name = (
            "ffmpeg_command.sh.jinja"
            if template_path is None
            else self.template_path.basename()
        )
        self.out_dir = self.base if out_dir is None else path.Path(out_dir)
        self.out_dir = self.out_dir.joinpath(self.clips.title)
        self.input_path = self.out_dir.joinpath("inputs.txt")
        self.meta_path = self.out_dir.joinpath("chapter.ffmetadata")
        self.text_path = self.out_dir.joinpath("chapter.txt")
        self.index_chapter_path = self.out_dir.joinpath("chapter_index.txt")
        self.script_path = self.out_dir.joinpath(f"script.sh")
        self.output_path = self.out_dir.joinpath(f"{self.clips.title}.mp4")
        try:
            self.out_dir.mkdir(mode=711)
        except FileExistsError:
            pass

    def inputs(self) -> None:
        with open(self.input_path, "w") as file:
            for c in self.clips:
                basename = c.path.basename()
                # escape literal quote to be '\''
                # refer to FFmpeg's concat Demuxer Format
                # EX: abc'efg needs to be enclosed in quote
                #     'abc'eft'
                #     then the single quote inside the original must be
                #     escaped, so separate the orignal string around
                #     the quote
                #     'abc'''eft'
                #     then escape the middle quote
                #     'abc'\''eft'
                # now to output this string from python, the back slash
                # needs to be escaped, thus '\\''
                basename = basename.replace("'", "'\\''")
                file.write(f"file '{basename}'\n")

    def meta(self) -> None:
        with open(self.meta_path, "w") as file:
            file.write(f"title={self.clips.title}\n")
            meta = self.clips.meta()
            file.write("".join(meta))

    def text(self) -> None:
        with open(self.text_path, "w") as file:
            file.write(f"{self.clips.title}\n")
            text = self.clips.text()
            file.write("".join(text))
        with open(self.index_chapter_path, "w") as file:
            text = self.clips.text_with_index()
            file.write("".join(text))

    def script(self):
        env = Environment(
            loader=FileSystemLoader(self.template_path),
            trim_blocks=True,
            autoescape=select_autoescape(),
        )
        tmpl = env.get_template(self.template_name)
        with open(self.script_path, "w") as file:
            file.write(tmpl.render(output=self))

    def move(self):
        for c in self.clips:
            c.path = c.path.move(self.out_dir.joinpath(c.path.basename()))

    def copy(self):
        for c in self.clips:
            c.path = c.path.copy(self.out_dir.joinpath(c.path.basename()))

    def project(self):
        self.inputs()
        self.meta()
        self.text()
        self.script()

    def run(self):
        subprocess.run(
            args=["sh", "script.sh"],
            cwd=self.out_dir,
        )


class Test:
    pass


class Interactive:
    def __init__(self, args: object):
        self.args = args
        if self.args.standby:
            return
        self.output = self.read()

    def compress_all(self) -> None:
        # base = self.args.base.replace(" ", "\\ ")
        base = self.args.base
        subprocess.run(
            args=[
                "bash",
                "compress.sh",
                base,
                f"{self.args.bitrate}",
            ],
        )

    def read(self, base: Optional[str] = None) -> Output:
        parser = Parser()
        if base is None:
            base = self.args.base

        files = parser.files(path.Path(base))
        comment_map: Dict[str, Union[str, List[str]]] = CommentParser().parse(
            file_path=self.args.comment_file
        )
        clips = parser.clips(files=files, comment_map=comment_map)

        output = Output(
            clips=clips,
            base=base,
            out_dir=self.args.out_dir,
            compress=CompressionConfig(
                enable=self.args.compress,
                bitrate=self.args.bitrate,
            ),
        )
        return output

    def reread(self) -> None:
        self.output = self.read()

    def copy(self) -> None:
        self.output.copy()
        self.output.project()

    def move(self) -> None:
        self.output.move()
        self.output.project()

    def run(self) -> None:
        self.output.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        prog="VideoConcat",
        description=(
            "Produce chapter metadata and text from video filenames "
            "generated by Shadowplay and processed by LosslessCut. "
            "This script helps in creating chapter information for video files."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-s",
        "--standby",
        action="store_true",
        help="Don't read files under base during setup",
    )
    parser.add_argument(
        "-b",
        "--base",
        action="store",
        help="The base directory containing input video files.",
    )
    parser.add_argument(
        "-o",
        "--out_dir",
        action="store",
        help="The directory to save output files.",
    )
    parser.add_argument(
        "-c",
        "--compress",
        action="store_true",
        help="Enable HEVC NVENC compression.",
    )
    parser.add_argument(
        "--bitrate",
        action="store",
        default=4,
        help="Compression bitrate (default: 4).",
    )
    parser.add_argument(
        "-m",
        "--move",
        action="store_true",
        default=False,
        help="If specified, move videos and start processing.",
    )
    parser.add_argument(
        "-cf",
        "--comment-file",
        action="store",
        help="Path to the YAML comment file.",
    )
    args = parser.parse_args()
    interactive = Interactive(args)
    if args.move:
        interactive.move()
        interactive.run()
        exit(0)

    read = interactive.read
    reread = interactive.reread
    copy = interactive.copy
    move = interactive.move
    run = interactive.run
    compress = interactive.compress_all
