"""Small, explicit interface for binary action/outcome streams.

Each JSON-lines request is either {"op":"predict","action":0},
{"op":"observe","action":0,"outcome":1}, {"op":"snapshot"}, or
{"op":"reset"}. A reset creates a fresh model with the selected policy.
The interface performs no network access or tool execution.
"""
from __future__ import annotations
import argparse
import json
import sys
from .engine import GovernedBitworkV14, FullBitworkV14
from .serialization import json_safe


def serve(input_stream, output_stream, mode="governed"):
    factory = GovernedBitworkV14 if mode == "governed" else FullBitworkV14
    model = factory()
    for line in input_stream:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request must be a JSON object")
            operation = request.get("op")
            if operation == "predict":
                action = request.get("action")
                if type(action) is not int or action not in (0, 1):
                    raise ValueError("action must be integer 0 or 1")
                result = {"probability_one": model.predict(action)}
            elif operation == "observe":
                action, outcome = request.get("action"), request.get("outcome")
                if any(type(x) is not int or x not in (0, 1) for x in (action, outcome)):
                    raise ValueError("action and outcome must be integer 0 or 1")
                model.observe(action, outcome)
                result = {"observations": len(model.history)}
            elif operation == "snapshot":
                result = model.snapshot()
            elif operation == "reset":
                model = factory()
                result = {"observations": 0}
            else:
                raise ValueError("op must be predict, observe, snapshot, or reset")
            response = {"ok": True, "version": "1.4.0", "result": result}
        except (ValueError, RuntimeError, TypeError) as error:
            response = {"ok": False, "error": str(error)}
        output_stream.write(json.dumps(json_safe(response), sort_keys=True, allow_nan=False) + "\n")
        output_stream.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("governed", "full"), default="governed")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if args.demo:
        from bgr110.worlds import trace
        factory = GovernedBitworkV14 if args.mode == "governed" else FullBitworkV14
        model = factory()
        for action, outcome in trace(140004, "four_lag_outside", 84):
            model.predict(action)
            model.observe(action, outcome)
        print(json.dumps(json_safe(model.snapshot()), indent=2, sort_keys=True, allow_nan=False))
    else:
        serve(sys.stdin, sys.stdout, args.mode)


if __name__ == "__main__":
    main()
