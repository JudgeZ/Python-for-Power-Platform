from __future__ import annotations

from pacx.cli.profile import MASK_PLACEHOLDER, _mask_sensitive_fields


def test_mask_sensitive_fields_redacts_tokens() -> None:
    profile_data = {
        "name": "secure",
        "access_token": "access-token",  # noqa: S105
        "refresh_token": "refresh-token",  # noqa: S105
        "use_device_code": True,
    }

    masked = _mask_sensitive_fields(profile_data)

    assert masked["access_token"] == MASK_PLACEHOLDER
    assert masked["refresh_token"] == MASK_PLACEHOLDER
    assert masked["use_device_code"] is True
    # Ensure original dictionary is not mutated
    assert profile_data["access_token"] == "access-token"  # noqa: S105
    assert profile_data["refresh_token"] == "refresh-token"  # noqa: S105
