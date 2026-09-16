"""Toggle OTel Demo feature flags to trigger the RFP's 3 performance scenarios.

flagd (Layer 1) watches its JSON config file and hot-reloads on change, so
setting a flag's defaultVariant here takes effect within a few seconds with
no container restart needed. Used to script Normal -> Degraded -> Recovering
transitions reproducibly (RFP Section 6) instead of clicking a UI by hand.

Flag names in this OTel Demo build differ from the RFP proposal guide's
suggested names (cartServiceFailure / recommendationServiceCacheFailure) -
the demo actually ships cartFailure and recommendationCacheFailure. This
script uses the flags that actually exist.

Important interaction discovered empirically: cartFailure only takes effect
inside CartService.EmptyCart, which checkout calls only *after* a successful
payment. Combining cartFailure with paymentFailure=100% therefore means
cartFailure can never fire, since checkout aborts before reaching EmptyCart.
The two are exposed as separate presets so they can be run as sequential
sub-scenarios instead of one combined (and self-defeating) one.
"""

import argparse
import json
import os

DEFAULT_FLAGD_CONFIG = os.path.expanduser(
    "~/opentelemetry-demo/src/flagd/demo.flagd.json"
)

PRESETS = {
    "degrade-checkout": {"paymentFailure": "100%", "cartFailure": "off"},
    "degrade-cart": {"cartFailure": "100%", "paymentFailure": "off"},
    "restore": {"paymentFailure": "off", "cartFailure": "off"},
}


def load_config(path):
    with open(path) as f:
        return json.load(f)


def save_config(path, config):
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def set_flags(flags, path=DEFAULT_FLAGD_CONFIG):
    """Set defaultVariant for each {flag_name: variant} pair and save."""
    config = load_config(path)
    for name, variant in flags.items():
        if name not in config["flags"]:
            raise KeyError(f"Flag '{name}' not found in {path}")
        config["flags"][name]["defaultVariant"] = variant
    save_config(path, config)
    for name, variant in flags.items():
        print(f"Set {name} -> {variant}")


def get_active_flags(path=DEFAULT_FLAGD_CONFIG):
    config = load_config(path)
    return {
        name: flag["defaultVariant"]
        for name, flag in config["flags"].items()
        if flag["defaultVariant"] != "off"
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger TelemetrixAI scenarios via flagd")
    parser.add_argument("action", choices=list(PRESETS.keys()) + ["status"])
    parser.add_argument("--flagd-config", default=DEFAULT_FLAGD_CONFIG)
    args = parser.parse_args()

    if args.action == "status":
        active = get_active_flags(args.flagd_config)
        print("Active (non-off) flags:", active or "none")
    else:
        set_flags(PRESETS[args.action], args.flagd_config)
