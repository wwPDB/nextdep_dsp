"""nextdep_dsp — Deposition Software Provider library for OneDep."""

from nextdep_dsp.apis.deposit.enums import Status
from nextdep_dsp.apis.deposit.models import DepositError, DepositStatus
from nextdep_dsp.apis.deposit.types import ApiClient
from nextdep_dsp.auths.token import TokenStore
from nextdep_dsp.auths.types import AuthProvider
from nextdep_dsp.checks.report import CheckIssue, CheckReport, CheckSeverity, CifLocation
from nextdep_dsp.dsp import Deposition, deposit_init, deposit_resume, list_sessions
from nextdep_dsp.enums import Country, EMSubType, ExperimentType, FileType
from nextdep_dsp.exceptions import ApiError, DepositApiException, NextDepError

__all__ = [
    # factories / facade
    "deposit_init",
    "deposit_resume",
    "list_sessions",
    "Deposition",
    # check result types
    "CheckReport",
    "CheckIssue",
    "CheckSeverity",
    "CifLocation",
    # domain enums
    "Country",
    "EMSubType",
    "ExperimentType",
    "FileType",
    # API response models
    "DepositStatus",
    "DepositError",
    "Status",
    # exceptions
    "NextDepError",
    "ApiError",
    "DepositApiException",
    # auth
    "TokenStore",
    "AuthProvider",
    # protocols
    "ApiClient",
]
