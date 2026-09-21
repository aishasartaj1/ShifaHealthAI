"""CLI entrypoint for the batch pipeline.

    python run.py --project shifahealthai --quarantine-bucket shifahealthai-quarantine

Runs on DirectRunner by default (real reads/writes against BigQuery + GCS, just executed locally
instead of on managed Dataflow workers - appropriate at this data volume; see docs/DEVLOG.md).
Pass --runner DataflowRunner --temp-location gs://... --staging-location gs://... to submit as an
actual Dataflow job instead; the pipeline code itself doesn't change.
"""

from __future__ import annotations

import argparse

from pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--quarantine-bucket", required=True)
    parser.add_argument("--runner", default="DirectRunner")
    parser.add_argument("--region", default="us-central1")
    parser.add_argument("--temp-location", default=None)
    parser.add_argument("--staging-location", default=None)
    args = parser.parse_args()

    pipeline_args = [f"--project={args.project}", f"--runner={args.runner}", f"--region={args.region}"]
    if args.temp_location:
        pipeline_args.append(f"--temp_location={args.temp_location}")
    if args.staging_location:
        pipeline_args.append(f"--staging_location={args.staging_location}")

    run(project=args.project, quarantine_bucket=args.quarantine_bucket, pipeline_args=pipeline_args)


if __name__ == "__main__":
    main()
