# conftest.py — 使 pytest 将本目录加入 sys.path
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
