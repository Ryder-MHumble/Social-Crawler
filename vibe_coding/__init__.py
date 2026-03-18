# -*- coding: utf-8 -*-
"""
Vibe Coding Module

Independent branch for collecting AI-coding / vibe-coding content from social media.
Saves to vibe_coding_raw_data table, separate from main crawler flow.
"""

from vibe_coding.store import VibeCodingStore
from vibe_coding.wrapper import VibeCodingStoreWrapper

__all__ = ["VibeCodingStore", "VibeCodingStoreWrapper"]
