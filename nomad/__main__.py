from .cognition import cycle

if __name__ == "__main__":
    import sys
    import json
    query = " ".join(sys.argv[1:]) or "cycle"
    print(json.dumps(cycle(query), indent=2))
