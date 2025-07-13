# Copyright (C) Ganzin Technology - All Rights Reserved
# ---------------------------
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
#
# Contributors
# ---------------------------
# En-Ho Shen <enho.shen@ganzin.com.tw>, 2025

from path import Path

import script


class TestParse:
    def test_names(self):
        dut = script.Parser()
        f1 = Path("/abc/cde/Project Zomboid 2025.07.13 - 02.09.03.696.DVR.mp4")
        f2 = Path(
            "/abc/cde/Project Zomboid 2025.07.13 - 03.39.22.704.DVR.mp4-00.00.23.029-00.00.31.281.mp4"
        )
        clip = dut.parse_info(file=f1)

        clip, cut = dut.parse_info(file=f1)
        assert clip.name == "Project Zomboid"
        assert clip.date == "2025.07.13"
        assert clip.time == "02.09.03"
        assert clip.index == "696"
        assert cut == ""
        clip, cut = dut.parse_info(file=f2)
        assert clip.name == "Project Zomboid"
        assert clip.date == "2025.07.13"
        assert clip.time == "03.39.22"
        assert clip.index == "704"
        assert cut.start.hr == 0
        assert cut.start.min == 0
        assert cut.start.sec == 23
        assert cut.start.msec == 29

        assert cut.end.hr == 0
        assert cut.end.min == 0
        assert cut.end.sec == 31
        assert cut.end.msec == 281
