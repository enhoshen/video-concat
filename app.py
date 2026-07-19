import argparse
import sys
import argparse

from script import create_parser
from argparseui.core import App


if __name__ == "__main__":
    app_arg = argparse.ArgumentParser(
        prog="Web app wrapper for video concat",
    )
    app_arg.add_argument(
        "-p",
        "--port",
        help="Application port",
    )
    args = app_arg.parse_args()
    parser = create_parser()
    app = App(parser=parser)
    app.run(debug=True, host="0.0.0.0", port=args.port)
