"""Tests for the `create` CLI command.

These tests exist because the previous validation layer (the `sigma` decorator)
silently dropped the wrapped command's return value and read positional arguments
via `kwargs.get(...)`, which Typer doesn't populate. The command therefore
no-op'd on every invocation. The tests below cover both paths:

  * the success path — mocked DepositApi, the command actually runs, exits 0,
    and prints the deposit id.
  * the validation path — bad inputs raise ValueError before any API call is
    attempted.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from nextdep_dsp.cli import app

runner = CliRunner()


# --------------------------------------------------------------------------
# Success path
# --------------------------------------------------------------------------


def _mock_deposit(dep_id: str = "D_8000000123") -> MagicMock:
    deposit = MagicMock()
    deposit.dep_id = dep_id
    return deposit


def test_create_xray_success_prints_dep_id():
    with patch("nextdep_dsp.cli.DepositApi") as mock_cls:
        mock_api = MagicMock()
        mock_cls.return_value = mock_api
        mock_api.create_xray_deposition.return_value = _mock_deposit("D_8000000111")

        result = runner.invoke(
            app,
            [
                "create",
                "xray",
                "user@example.org",
                "United States",
                "--user",
                "0000-0001-2345-6789",
            ],
        )

    assert result.exit_code == 0, result.stderr
    assert "D_8000000111" in result.stdout
    mock_api.create_xray_deposition.assert_called_once()


def test_create_em_success_dispatches_with_subtype_and_coords():
    with patch("nextdep_dsp.cli.DepositApi") as mock_cls:
        mock_api = MagicMock()
        mock_cls.return_value = mock_api
        mock_api.create_em_deposition.return_value = _mock_deposit("D_8000000222")

        result = runner.invoke(
            app,
            [
                "create",
                "em",
                "user@example.org",
                "United States",
                "--user",
                "0000-0001-2345-6789",
                "--subtype",
                "single",
                "--coords",
            ],
        )

    assert result.exit_code == 0, result.stderr
    assert "D_8000000222" in result.stdout
    call = mock_api.create_em_deposition.call_args
    assert call.kwargs["coordinates"] is True
    assert call.kwargs["subtype"].value == "single"


# --------------------------------------------------------------------------
# Validation failures (run before any DepositApi instantiation)
# --------------------------------------------------------------------------


def test_create_rejects_invalid_email():
    result = runner.invoke(
        app,
        [
            "create",
            "xray",
            "not-an-email",
            "United States",
            "--user",
            "0000-0001-2345-6789",
        ],
    )
    assert result.exit_code != 0
    assert "Invalid email format" in str(result.exception)


def test_create_rejects_invalid_orcid():
    result = runner.invoke(
        app,
        [
            "create",
            "xray",
            "user@example.org",
            "United States",
            "--user",
            "0000-0001-NOTANORCID",
        ],
    )
    assert result.exit_code != 0
    assert "Invalid ORCID format" in str(result.exception)


def test_create_rejects_unknown_country():
    result = runner.invoke(
        app,
        [
            "create",
            "xray",
            "user@example.org",
            "Atlantis",
            "--user",
            "0000-0001-2345-6789",
        ],
    )
    assert result.exit_code != 0
    assert "Invalid country" in str(result.exception)


def test_create_em_requires_subtype():
    result = runner.invoke(
        app,
        [
            "create",
            "em",
            "user@example.org",
            "United States",
            "--user",
            "0000-0001-2345-6789",
            # no --subtype
        ],
    )
    assert result.exit_code != 0
    assert "subtype is required for EM deposition" in str(result.exception)


def test_create_xray_rejects_no_coords_flag():
    result = runner.invoke(
        app,
        [
            "create",
            "xray",
            "user@example.org",
            "United States",
            "--user",
            "0000-0001-2345-6789",
            "--no-coords",
        ],
    )
    assert result.exit_code != 0
    assert "coordinates are required for xray, fiber, and neutron diffraction" in str(result.exception)


def test_create_rejects_sf_only_outside_ec():
    result = runner.invoke(
        app,
        [
            "create",
            "xray",
            "user@example.org",
            "United States",
            "--user",
            "0000-0001-2345-6789",
            "--sf-only",
        ],
    )
    assert result.exit_code != 0
    assert "sf-only is only valid for EC deposition" in str(result.exception)


def test_create_ec_requires_sf_only_flag():
    result = runner.invoke(
        app,
        [
            "create",
            "ec",
            "user@example.org",
            "United States",
            "--user",
            "0000-0001-2345-6789",
            "--coords",
        ],
    )
    assert result.exit_code != 0
    assert "sf-only/no-sf-only is required for EC deposition" in str(result.exception)
