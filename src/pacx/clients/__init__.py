from .analytics import AnalyticsClient as AnalyticsClient
from .authorization import AuthorizationRbacClient as AuthorizationRbacClient
from .connectors import ConnectorsClient as ConnectorsClient
from .dataverse import DataverseClient as DataverseClient
from .policy import DataLossPreventionClient as DataLossPreventionClient
from .governance import GovernanceClient as GovernanceClient
from .licensing import LicensingClient as LicensingClient
from .power_platform import PowerPlatformClient as PowerPlatformClient
from .tenant_settings import TenantSettingsClient as TenantSettingsClient
from .pva import PVAClient as PVAClient
from .user_management import (
    UserManagementClient as UserManagementClient,
    UserManagementOperationHandle as UserManagementOperationHandle,
)

__all__ = [
    "AnalyticsClient",
    "AuthorizationRbacClient",
    "ConnectorsClient",
    "DataverseClient",
    "DataLossPreventionClient",
    "GovernanceClient",
    "LicensingClient",
    "PowerPlatformClient",
    "TenantSettingsClient",
    "PVAClient",
    "UserManagementClient",
    "UserManagementOperationHandle",
]
