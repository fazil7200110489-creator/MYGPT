"""Role-Based Access Control (RBAC) and Department Permission Manager for Company AI.
"""

from typing import Dict, Any, List, Optional, Set, Union
from loguru import logger

from backend.app.schemas.department import DepartmentEnum
from backend.app.schemas.security import UserRoleEnum, SecurityLevelEnum


class PermissionManager:
    """Enterprise Permission Manager governing department-scoped access and document security levels."""

    def __init__(self):
        # Department domain access rights per role
        self._role_department_access: Dict[UserRoleEnum, Set[DepartmentEnum]] = {
            UserRoleEnum.ADMIN: {
                DepartmentEnum.TECH,
                DepartmentEnum.HR,
                DepartmentEnum.FINANCE,
                DepartmentEnum.GENERAL
            },
            UserRoleEnum.TECH_ADMIN: {
                DepartmentEnum.TECH,
                DepartmentEnum.GENERAL
            },
            UserRoleEnum.HR_MANAGER: {
                DepartmentEnum.HR,
                DepartmentEnum.GENERAL
            },
            UserRoleEnum.FINANCE_MANAGER: {
                DepartmentEnum.FINANCE,
                DepartmentEnum.GENERAL
            },
            UserRoleEnum.EMPLOYEE: {
                DepartmentEnum.GENERAL,
                DepartmentEnum.TECH,
                DepartmentEnum.HR,
                DepartmentEnum.FINANCE
            }
        }

        # Maximum security level accessible by role in their primary department
        self._role_max_security: Dict[UserRoleEnum, SecurityLevelEnum] = {
            UserRoleEnum.ADMIN: SecurityLevelEnum.CONFIDENTIAL,
            UserRoleEnum.TECH_ADMIN: SecurityLevelEnum.CONFIDENTIAL,
            UserRoleEnum.HR_MANAGER: SecurityLevelEnum.CONFIDENTIAL,
            UserRoleEnum.FINANCE_MANAGER: SecurityLevelEnum.CONFIDENTIAL,
            UserRoleEnum.EMPLOYEE: SecurityLevelEnum.INTERNAL
        }

        # Security hierarchy numeric weights
        self._security_weights: Dict[SecurityLevelEnum, int] = {
            SecurityLevelEnum.PUBLIC: 1,
            SecurityLevelEnum.INTERNAL: 2,
            SecurityLevelEnum.RESTRICTED: 3,
            SecurityLevelEnum.CONFIDENTIAL: 4
        }

    def can_access_department(
        self,
        role: Union[UserRoleEnum, str],
        target_department: Union[DepartmentEnum, str],
        is_confidential: bool = False
    ) -> bool:
        """Evaluates whether a user role is permitted to interact with a department's knowledge base."""
        role_enum = self._normalize_role(role)
        dept_enum = self._normalize_dept(target_department)

        if role_enum == UserRoleEnum.ADMIN:
            return True

        if dept_enum == DepartmentEnum.GENERAL:
            return True

        # Department manager / admin dedicated access
        if role_enum == UserRoleEnum.TECH_ADMIN and dept_enum == DepartmentEnum.TECH:
            return True
        if role_enum == UserRoleEnum.HR_MANAGER and dept_enum == DepartmentEnum.HR:
            return True
        if role_enum == UserRoleEnum.FINANCE_MANAGER and dept_enum == DepartmentEnum.FINANCE:
            return True

        # General Employee: allowed to query general non-confidential department info
        if role_enum == UserRoleEnum.EMPLOYEE:
            return not is_confidential

        return False

    def can_access_chunk(
        self,
        role: Union[UserRoleEnum, str],
        target_department: Union[DepartmentEnum, str],
        chunk_security_level: Union[SecurityLevelEnum, str],
        role_required: Optional[List[Union[UserRoleEnum, str]]] = None
    ) -> bool:
        """Strict chunk-level security validator checking department, security level, and role constraints."""
        role_enum = self._normalize_role(role)
        dept_enum = self._normalize_dept(target_department)
        sec_enum = self._normalize_security(chunk_security_level)

        # 1. Admin bypass
        if role_enum == UserRoleEnum.ADMIN:
            return True

        # 2. Public chunks are accessible to everyone
        if sec_enum == SecurityLevelEnum.PUBLIC:
            return True

        # 3. Explicit role_required check if specified
        if role_required:
            req_roles = [self._normalize_role(r) for r in role_required]
            if role_enum in req_roles:
                return True

        # 4. Department boundary check for restricted/confidential
        if sec_enum in [SecurityLevelEnum.RESTRICTED, SecurityLevelEnum.CONFIDENTIAL]:
            if dept_enum == DepartmentEnum.TECH and role_enum == UserRoleEnum.TECH_ADMIN:
                return True
            if dept_enum == DepartmentEnum.HR and role_enum == UserRoleEnum.HR_MANAGER:
                return True
            if dept_enum == DepartmentEnum.FINANCE and role_enum == UserRoleEnum.FINANCE_MANAGER:
                return True
            # Cross-department or general employee access to restricted/confidential is strictly DENIED
            return False

        # 5. Internal chunks are accessible if role has department access
        if sec_enum == SecurityLevelEnum.INTERNAL:
            return self.can_access_department(role_enum, dept_enum, is_confidential=False)

        return False

    def _normalize_role(self, role: Union[UserRoleEnum, str]) -> UserRoleEnum:
        if isinstance(role, UserRoleEnum):
            return role
        try:
            return UserRoleEnum(role.upper())
        except (ValueError, AttributeError):
            return UserRoleEnum.EMPLOYEE

    def _normalize_dept(self, dept: Union[DepartmentEnum, str]) -> DepartmentEnum:
        if isinstance(dept, DepartmentEnum):
            return dept
        try:
            return DepartmentEnum(dept.upper())
        except (ValueError, AttributeError):
            return DepartmentEnum.GENERAL

    def _normalize_security(self, sec: Union[SecurityLevelEnum, str]) -> SecurityLevelEnum:
        if isinstance(sec, SecurityLevelEnum):
            return sec
        try:
            return SecurityLevelEnum(sec.upper())
        except (ValueError, AttributeError):
            return SecurityLevelEnum.INTERNAL


# Global singleton instance
permission_manager = PermissionManager()
