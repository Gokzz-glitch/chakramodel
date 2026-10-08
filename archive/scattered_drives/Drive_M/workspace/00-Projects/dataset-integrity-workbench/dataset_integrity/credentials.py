"""Safe credential-provider and profile boundaries.

Credential values are intentionally not serializable, printable, or logged by
this module.  The Windows implementation is isolated behind a small provider
interface so applications can inject a mock or an optional platform adapter.
"""
from __future__ import annotations

import ctypes
import hashlib
import sys
import base64
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Optional, Protocol, Sequence


class CredentialError(RuntimeError):
    """Base error for credential-provider failures."""


class ProviderUnavailable(CredentialError):
    """The selected provider is not available on this platform."""


@dataclass(frozen=True)
class CredentialProfile:
    name: str
    target: str
    provider: str = "windows-credential-manager"


@dataclass(frozen=True)
class Credential:
    username: str
    secret: bytes
    target: str

    def __repr__(self) -> str:  # pragma: no cover - defensive logging guard
        return "Credential(<redacted>)"


class CredentialProvider(Protocol):
    def retrieve(self, profile: CredentialProfile) -> Credential: ...


@dataclass(frozen=True)
class RotationPlan:
    """Non-secret four-slot rotation metadata.

    A plan contains profile references only. It never contains credential
    values and does not retrieve or save anything.
    """

    slots: tuple[CredentialProfile, ...]
    models: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "slots": [
                {"slot": index + 1, "profile": profile.name,
                 "provider": profile.provider, "target": profile.target}
                for index, profile in enumerate(self.slots)
            ],
            "models": list(self.models),
            "credential_values_accessed": False,
        }


def build_rotation_plan(
    profiles: Sequence[CredentialProfile],
    models: Sequence[str] = (),
) -> RotationPlan:
    if not 1 <= len(profiles) <= 4:
        raise ValueError("rotation requires between one and four profile references")
    if any(not profile.name or not profile.target for profile in profiles):
        raise ValueError("rotation profile names and targets must not be empty")
    normalized_models = tuple(dict.fromkeys(model.strip() for model in models if model.strip()))
    return RotationPlan(tuple(profiles), normalized_models)


def redacted_metadata(profile: CredentialProfile, credential: Optional[Credential] = None) -> dict:
    """Return diagnostics safe to put in CLI output and logs."""
    return {
        "profile": profile.name,
        "provider": profile.provider,
        "target": profile.target,
        "username_present": bool(credential and credential.username),
        "secret_present": bool(credential and credential.secret),
        "secret_length": len(credential.secret) if credential else 0,
    }


class WindowsCredentialManagerProvider:
    """Read generic credentials using the Windows Credential Manager API."""

    def __init__(self, profiles: Iterable[CredentialProfile] = ()):
        self._profiles = {profile.name: profile for profile in profiles}

    def list_profiles(self) -> tuple[CredentialProfile, ...]:
        return tuple(self._profiles[name] for name in sorted(self._profiles))

    def retrieve(self, profile: CredentialProfile) -> Credential:
        if sys.platform != "win32" or not hasattr(ctypes, "windll"):
            raise ProviderUnavailable("Windows Credential Manager is only available on Windows")
        if not profile.target:
            raise CredentialError("credential target must not be empty")

        class _CREDENTIAL(ctypes.Structure):
            _fields_ = [
                ("Flags", ctypes.c_uint32), ("Type", ctypes.c_uint32),
                ("TargetName", ctypes.c_wchar_p), ("Comment", ctypes.c_wchar_p),
                ("LastWritten", ctypes.c_byte * 8), ("CredentialBlobSize", ctypes.c_uint32),
                ("CredentialBlob", ctypes.c_void_p), ("Persist", ctypes.c_uint32),
                ("AttributeCount", ctypes.c_uint32), ("Attributes", ctypes.c_void_p),
                ("TargetAlias", ctypes.c_wchar_p), ("UserName", ctypes.c_wchar_p),
            ]

        pointer = ctypes.POINTER(_CREDENTIAL)()
        advapi = ctypes.windll.advapi32
        advapi.CredReadW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                     ctypes.POINTER(ctypes.POINTER(_CREDENTIAL))]
        advapi.CredReadW.restype = ctypes.c_bool
        advapi.CredFree.argtypes = [ctypes.c_void_p]
        if not advapi.CredReadW(profile.target, 1, 0, ctypes.byref(pointer)):
            error = ctypes.GetLastError()
            raise CredentialError("credential lookup failed (winerror={})".format(error))
        try:
            item = pointer.contents
            secret = ctypes.string_at(item.CredentialBlob, item.CredentialBlobSize)
            return Credential(item.UserName or "", bytes(secret), profile.target)
        finally:
            advapi.CredFree(pointer)


class MockCredentialProvider:
    """Deterministic provider for tests; values never appear in metadata."""

    def __init__(self, credentials: Mapping[str, Credential]):
        self.credentials = dict(credentials)
        self.requested: list[str] = []

    def retrieve(self, profile: CredentialProfile) -> Credential:
        self.requested.append(profile.name)
        try:
            return self.credentials[profile.name]
        except KeyError:
            raise CredentialError("mock credential not found for profile {!r}".format(profile.name))


def profile_fingerprint(profile: CredentialProfile) -> str:
    """Stable non-secret identifier useful for audit records."""
    return hashlib.sha256((profile.provider + "\0" + profile.target).encode()).hexdigest()[:16]


def verify_profile(
    provider: CredentialProvider,
    profile: CredentialProfile,
    *,
    network: bool = False,
    source_target: Optional[str] = None,
    network_verifier: Optional[Callable[[Credential, str], bool]] = None,
) -> dict:
    if network and not source_target:
        raise ValueError("network verification requires an explicit source target")
    credential = provider.retrieve(profile)
    result = redacted_metadata(profile, credential)
    result["fingerprint"] = profile_fingerprint(profile)
    result["verified"] = True
    if network:
        if source_target != profile.target:
            raise ValueError("source target must exactly match the profile target")
        if network_verifier is None:
            result["network_verified"] = False
            result["network_status"] = "not configured"
        else:
            result["network_verified"] = bool(network_verifier(credential, source_target))
    return result


def verify_https_source(credential: Credential, source_target: str, timeout: float = 10.0) -> bool:
    """Opt-in HTTP adapter; callers must explicitly choose this function."""
    if not source_target.lower().startswith("https://"):
        raise ValueError("network verification only permits HTTPS source targets")
    token = base64.b64encode(credential.username.encode("utf-8") + b":" + credential.secret).decode("ascii")
    request = urllib.request.Request(source_target, method="HEAD",
                                     headers={"Authorization": "Basic " + token})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 400
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return False


def parse_profiles(values: Iterable[str]) -> tuple[CredentialProfile, ...]:
    profiles = []
    for value in values:
        if "=" not in value:
            raise ValueError("profiles must use NAME=TARGET")
        name, target = value.split("=", 1)
        if not name or not target:
            raise ValueError("profile names and targets must not be empty")
        profiles.append(CredentialProfile(name, target))
    return tuple(profiles)
