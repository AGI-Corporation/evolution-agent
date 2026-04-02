#!/usr/bin/env python3
# voice_agent.py
# Entry point for the Voice Coding Agent.
#
# Usage:
#   python voice_agent.py                  # run from project root
#   python voice_agent.py /path/to/project # specify project root
#   python voice_agent.py --seconds 15     # extend recording window
#
# Environment:
#   OPENAI_API_KEY  — required for Whisper, GPT-4o, and TTS

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Voice Coding Agent — speak your coding requests, get working code back."
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=os.getcwd(),
        help="Path to the project root (default: current directory)",
    )
    parser.add_argument(
        "--seconds",
        type=int,
        default=10,
        help="Recording window in seconds per push-to-talk press (default: 10)",
    )
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("[voice_agent] ERROR: OPENAI_API_KEY environment variable is not set.")
        sys.exit(1)

    from evolution.voice_interface import VoiceCodingAgent

    agent = VoiceCodingAgent(
        project_root=os.path.abspath(args.project_root),
        record_seconds=args.seconds,
    )
    agent.run()


if __name__ == "__main__":
    main()
