"""Entry point: python -m finance_pipeline --mode morning|evening"""
import argparse
import asyncio
from finance_pipeline.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Finance market report pipeline")
    parser.add_argument(
        "--mode",
        choices=["morning", "evening"],
        required=True,
        help="morning = pre-A-share (08:00 BJT), evening = pre-US (21:30 BJT)",
    )
    args = parser.parse_args()
    result = asyncio.run(run(args.mode))
    if not result.get("success"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
