"""CLI entrypoint for the streaming pipeline.

    python run.py --project shifahealthai --subscription shifahealth-events-streaming-sub --run-for-seconds 60

A real Dataflow streaming job runs indefinitely; for local DEV runs this accepts --run-for-seconds
and cancels itself after that long, so it's demo-able (and testable) without needing a second
terminal to Ctrl+C it. Runs on DirectRunner by default; pass --runner DataflowRunner
--temp-location gs://... --staging-location gs://... to submit as an actual (indefinitely-running)
Dataflow job instead.
"""

from __future__ import annotations

import argparse
import time

from pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--runner", default="DirectRunner")
    parser.add_argument("--region", default="us-central1")
    parser.add_argument("--run-for-seconds", type=int, default=60)
    parser.add_argument("--temp-location", default=None)
    parser.add_argument("--staging-location", default=None)
    args = parser.parse_args()

    pipeline_args = [f"--project={args.project}", f"--runner={args.runner}", f"--region={args.region}"]
    if args.temp_location:
        pipeline_args.append(f"--temp_location={args.temp_location}")
    if args.staging_location:
        pipeline_args.append(f"--staging_location={args.staging_location}")

    result = run(project=args.project, subscription=args.subscription, pipeline_args=pipeline_args)
    print(f"Streaming pipeline running, will stop after {args.run_for_seconds}s ...")
    time.sleep(args.run_for_seconds)
    result.cancel()
    result.wait_until_finish(duration=30_000)
    print("Stopped.")


if __name__ == "__main__":
    main()
