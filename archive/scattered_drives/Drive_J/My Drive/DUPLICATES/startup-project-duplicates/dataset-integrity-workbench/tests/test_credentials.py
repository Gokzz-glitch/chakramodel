import pytest

from dataset_integrity.credentials import (
    Credential, CredentialProfile, MockCredentialProvider, ProviderUnavailable,
    RotationPlan, build_rotation_plan, redacted_metadata, verify_profile,
    WindowsCredentialManagerProvider,
)


def test_mock_retrieval_returns_only_redacted_metadata():
    profile = CredentialProfile("registry", "https://registry.example")
    provider = MockCredentialProvider({"registry": Credential("alice", b"super-secret", profile.target)})
    result = verify_profile(provider, profile)
    assert result["verified"] is True
    assert result["username_present"] is True
    assert "super-secret" not in str(result)
    assert provider.requested == ["registry"]


def test_network_verification_requires_explicit_matching_target():
    profile = CredentialProfile("registry", "https://registry.example")
    provider = MockCredentialProvider({"registry": Credential("a", b"x", profile.target)})
    with pytest.raises(ValueError):
        verify_profile(provider, profile, network=True)
    with pytest.raises(ValueError):
        verify_profile(provider, profile, network=True, source_target="https://other.example")


def test_windows_provider_is_unavailable_off_windows():
    provider = WindowsCredentialManagerProvider()
    if __import__("sys").platform != "win32":
        with pytest.raises(ProviderUnavailable):
            provider.retrieve(CredentialProfile("x", "target"))


def test_four_slot_rotation_plan_is_metadata_only():
    profiles = [CredentialProfile(f"key-{i}", f"target-{i}") for i in range(1, 5)]
    plan = build_rotation_plan(profiles, ["gemini-a", "gemini-a", "gemini-b"])
    assert isinstance(plan, RotationPlan)
    assert plan.as_dict()["models"] == ["gemini-a", "gemini-b"]
    assert plan.as_dict()["credential_values_accessed"] is False


def test_rotation_plan_rejects_more_than_four_profiles():
    profiles = [CredentialProfile(str(i), str(i)) for i in range(5)]
    with pytest.raises(ValueError):
        build_rotation_plan(profiles)
