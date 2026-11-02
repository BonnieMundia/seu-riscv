"""Print the programs `make lockstep` runs for a study: its workloads, then the platform tests."""
import argparse

from programs import load

ap = argparse.ArgumentParser()
ap.add_argument("--study", default="seu")
workloads, tests = load(ap.parse_args().study)
print(" ".join([*workloads, *tests]))
