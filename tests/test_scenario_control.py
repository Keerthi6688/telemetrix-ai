"""Scenario simulation (D-06): flagd config toggling for Normal/Degraded/
Recovering transitions. Had zero coverage - tests use a temp JSON file
standing in for the real flagd config, so no live flagd/Docker stack is
needed to validate the toggling logic itself.
"""

import json
import runpy
import sys

import pytest

import scenario_control as sc


@pytest.fixture
def flagd_config_path(tmp_path):
    config = {
        "flags": {
            "cartFailure": {"defaultVariant": "off", "variants": {"off": False, "100%": True}},
            "paymentFailure": {"defaultVariant": "off", "variants": {"off": False, "100%": True}},
            "recommendationCacheFailure": {"defaultVariant": "off", "variants": {"off": False, "100%": True}},
        }
    }
    path = tmp_path / "demo.flagd.json"
    path.write_text(json.dumps(config, indent=2))
    return str(path)


def test_get_active_flags_empty_when_all_off(flagd_config_path):
    assert sc.get_active_flags(flagd_config_path) == {}


def test_set_flags_degrade_checkout_activates_payment_failure(flagd_config_path):
    sc.set_flags(sc.PRESETS["degrade-checkout"], flagd_config_path)
    active = sc.get_active_flags(flagd_config_path)
    assert active == {"paymentFailure": "100%"}


def test_set_flags_degrade_cart_activates_cart_failure(flagd_config_path):
    sc.set_flags(sc.PRESETS["degrade-cart"], flagd_config_path)
    active = sc.get_active_flags(flagd_config_path)
    assert active == {"cartFailure": "100%"}


def test_restore_preset_turns_everything_off(flagd_config_path):
    sc.set_flags(sc.PRESETS["degrade-checkout"], flagd_config_path)
    sc.set_flags(sc.PRESETS["restore"], flagd_config_path)
    assert sc.get_active_flags(flagd_config_path) == {}


def test_set_flags_rejects_unknown_flag_name(flagd_config_path):
    with pytest.raises(KeyError):
        sc.set_flags({"notARealFlag": "100%"}, flagd_config_path)


def test_set_flags_persists_to_disk(flagd_config_path):
    sc.set_flags({"cartFailure": "100%"}, flagd_config_path)
    reloaded = sc.load_config(flagd_config_path)
    assert reloaded["flags"]["cartFailure"]["defaultVariant"] == "100%"


# ---------------------------------------------------------------------------
# CLI entry point (__main__) - run in-process via runpy with a patched
# argv, exercising the exact same code the real `python scenario_control.py
# <action>` invocation runs (and unlike a subprocess, still visible to
# coverage.py).
# ---------------------------------------------------------------------------

def _run_cli(action, flagd_config_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["scenario_control.py", action, "--flagd-config", flagd_config_path])
    runpy.run_path(sc.__file__, run_name="__main__")
    return capsys.readouterr()


def test_cli_status_reports_no_active_flags(flagd_config_path, monkeypatch, capsys):
    out = _run_cli("status", flagd_config_path, monkeypatch, capsys)
    assert "none" in out.out.lower()


def test_cli_degrade_checkout_sets_and_reports_flag(flagd_config_path, monkeypatch, capsys):
    _run_cli("degrade-checkout", flagd_config_path, monkeypatch, capsys)
    out = _run_cli("status", flagd_config_path, monkeypatch, capsys)
    assert "paymentFailure" in out.out
    assert "100%" in out.out
