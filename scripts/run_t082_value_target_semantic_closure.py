"""Run the T082 audit against the retained T064 root."""
from pathlib import Path
import argparse
from sts_combat_rl.t082_value_target_semantic_closure import audit_t064

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_t064(args.manifest, args.output)
    print(report["classification"])

if __name__ == "__main__":
    main()
