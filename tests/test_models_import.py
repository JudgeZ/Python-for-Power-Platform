"""Smoke tests for the public ``pacx.models`` namespace."""


def test_models_exports_are_available() -> None:
    import pacx.models as models

    assert models.AdvisorAction is not None
    assert models.ApplicationPackageSummary is not None
    assert models.PolicyAsyncOperation is not None
    assert models.TenantSettings is not None
    assert models.AdminRoleAssignment is not None
