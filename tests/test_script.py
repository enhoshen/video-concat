# Contributors
# ---------------------------
# En-Ho Shen <enhoshen@gmail.com>, 2026

from path import Path
from datetime import datetime, timedelta
from video_concat import lib
from unittest.mock import patch


class TestParse:
    def test_names(self):
        dut = lib.Parser()
        f1 = Path("/abc/cde/Project Zomboid 2025.07.13 - 02.09.03.696.DVR.mp4")
        f2 = Path(
            "/abc/cde/Project Zomboid 2025.07.13 - 03.39.22.704.DVR.mp4-00.00.23.029-00.00.31.281.mp4"
        )
        assert dut.parse_info(file=f1) is not None

        clip, cut = dut.parse_info(file=f1)
        assert clip.name == "Project Zomboid"
        assert clip.date == datetime(2025, 7, 13)
        assert clip.time == timedelta(hours=2, minutes=9, seconds=3)
        assert clip.index == "696"
        assert cut is None

        clip, cut = dut.parse_info(file=f2)
        assert clip.name == "Project Zomboid"
        assert clip.date == datetime(2025, 7, 13)
        assert clip.time == timedelta(hours=3, minutes=39, seconds=22)
        assert clip.index == "704"
        assert cut is not None
        assert cut.start == timedelta(seconds=23, milliseconds=29)
        assert cut.end == timedelta(seconds=31, milliseconds=281)


def test_basic_parse_from_input_file():
    basic = lib.Basic()
    with open("tests/input.txt", "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    # First line: with cut
    clip_info_1, cut_1 = basic.parse(lines[0])
    assert clip_info_1.name == "Abiotic Factor"
    assert clip_info_1.date == datetime(2026, 7, 11)
    assert clip_info_1.time == timedelta(hours=15, minutes=56, seconds=26)
    assert clip_info_1.index == "689"
    assert cut_1 is not None
    assert cut_1.start == timedelta(seconds=8, milliseconds=352)
    assert cut_1.end == timedelta(seconds=47, milliseconds=889)

    # Second line: without cut
    clip_info_2, cut_2 = basic.parse(lines[1])
    assert clip_info_2.name == "Abiotic Factor"
    assert clip_info_2.date == datetime(2026, 7, 11)
    assert clip_info_2.time == timedelta(hours=15, minutes=58, seconds=26)
    assert clip_info_2.index == "690"
    assert cut_2 is None


def test_chapter_to_text():
    basic = lib.Basic()
    line1 = "Abiotic Factor 2026.07.11 - 15.56.26.689.DVR.mp4-00.00.08.352-00.00.47.889.mp4"
    clip_info1, cut1 = basic.parse(line1)

    chapter1 = lib.Chapter(
        name=clip_info1.name,
        date=clip_info1.date,
        time=clip_info1.time,
        length=timedelta(seconds=120.0),
        index=clip_info1.index,
        cut=cut1,
        comment="Test Comment",
    )
    # start = 0 milliseconds
    text_out1 = chapter1.to_text(0)
    # date_start = datetime(2026, 7, 11)
    #   + timedelta(hours=15, minutes=56, seconds=26)
    #   + timedelta(seconds=8, milliseconds=352)
    #            = datetime(2026, 7, 11, 15, 56, 34, 352000)
    # strftime("%m.%d-%H.%M.%S") -> "07.11-15.56.34"
    # Expected: "00:00:00 07.11-15.56.34 Test Comment\n"
    assert text_out1 == "00:00:00 07.11-15.56.34 Test Comment\n"

    line2 = "Abiotic Factor 2026.07.11 - 15.58.26.690.DVR.mp4"
    clip_info2, cut2 = basic.parse(line2)
    chapter2 = lib.Chapter(
        name=clip_info2.name,
        date=clip_info2.date,
        time=clip_info2.time,
        length=timedelta(seconds=60.0),
        index=clip_info2.index,
        cut=cut2,
        comment="",
    )
    # start = 30000 milliseconds (30 seconds)
    text_out2 = chapter2.to_text(30000)
    # date_start = datetime(2026, 7, 11) + timedelta(hours=15, minutes=58, seconds=26) + timedelta(0)
    #            = datetime(2026, 7, 11, 15, 58, 26)
    # strftime("%m.%d-%H.%M.%S") -> "07.11-15.58.26"
    # Expected: "00:00:30 07.11-15.58.26\n"
    assert text_out2 == "00:00:30 07.11-15.58.26\n"


def test_datetime_crossing_boundaries():
    basic = lib.Basic()

    # 1. Crossing Day and Month: July 31st 23:59:55 + 10s (cut.start)
    # This should cross midnight and result in August 1st, 00:00:05
    line1 = "Abiotic Factor 2026.07.31 - 23.59.55.000.DVR.mp4-00.00.10.000-00.00.20.000.mp4"
    clip_info1, cut1 = basic.parse(line1)

    assert clip_info1.date == datetime(2026, 7, 31)
    assert clip_info1.time == timedelta(hours=23, minutes=59, seconds=55)
    assert cut1 is not None
    assert cut1.start == timedelta(seconds=10)

    chapter1 = lib.Chapter(
        name=clip_info1.name,
        date=clip_info1.date,
        time=clip_info1.time,
        length=timedelta(seconds=60.0),
        index=clip_info1.index,
        cut=cut1,
        comment="Boundary Month",
    )
    text_out1 = chapter1.to_text(0)
    # date_start = datetime(2026, 7, 31) + timedelta(hours=23, minutes=59, seconds=55) + timedelta(seconds=10)
    #            = datetime(2026, 8, 1, 0, 0, 5)
    # strftime("%m.%d-%H.%M.%S") -> "08.01-00.00.05"
    assert "08.01-00.00.05" in text_out1
    assert text_out1.startswith("00:00:00")

    # 2. Crossing Year: December 31st 23:59:55 + 10s (cut.start)
    # This should cross the year boundary and result in January 1st, 00:00:05
    line2 = "Abiotic Factor 2026.12.31 - 23.59.55.000.DVR.mp4-00.00.10.000-00.00.20.000.mp4"
    clip_info2, cut2 = basic.parse(line2)

    assert clip_info2.date == datetime(2026, 12, 31)
    assert clip_info2.time == timedelta(hours=23, minutes=59, seconds=55)
    assert cut2 is not None
    assert cut2.start == timedelta(seconds=10)

    chapter2 = lib.Chapter(
        name=clip_info2.name,
        date=clip_info2.date,
        time=clip_info2.time,
        length=timedelta(seconds=60.0),
        index=clip_info2.index,
        cut=cut2,
        comment="Boundary Year",
    )
    text_out2 = chapter2.to_text(0)
    # date_start = datetime(2026, 12, 31) + timedelta(hours=23, minutes=59, seconds=55) + timedelta(seconds=10)
    #            = datetime(2027, 1, 1, 0, 0, 5)
    # strftime("%m.%d-%H.%M.%S") -> "01.01-00.00.05"
    assert "01.01-00.00.05" in text_out2
    assert text_out2.startswith("00:00:00")


def test_yaml_comment_parser(tmp_path):
    comment_yaml = """
123:
  - comment 1
  - comment 2
456:  comment
689:
  - comment a
  - comment b
"""
    yaml_file = tmp_path / "comments.yaml"
    yaml_file.write_text(comment_yaml)

    parser = lib.CommentParser()
    comments = parser.parse(str(yaml_file))

    assert comments == {
        "123": ["comment 1", "comment 2"],
        "456": "comment",
        "689": ["comment a", "comment b"],
    }


@patch("ffmpeg.probe")
def test_parser_sub_indexing(mock_probe):
    mock_probe.return_value = {"format": {"duration": "120.0"}}

    # Create mock clip paths
    f1 = Path(
        "/abc/Abiotic Factor 2026.07.11 - 15.56.26.689.DVR.mp4-00.00.08.352-00.00.47.889.mp4"
    )
    f2 = Path(
        "/abc/Abiotic Factor 2026.07.11 - 15.56.26.689.DVR.mp4-00.01.53.352-00.02.30.889.mp4"
    )

    comment_map = {"689": ["comment a", "comment b"]}

    parser = lib.Parser()
    clips = parser.clips([f1, f2], comment_map=comment_map)

    assert len(clips.clips) == 2
    assert clips.clips[0].ch.comment == "comment a"
    assert clips.clips[1].ch.comment == "comment b"
