from __future__ import annotations

from sqlalchemy import select

from app.config import async_session
from app.models import Cabang, User, UserType
from app.utils import retry_query_on_error


def _to_int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _to_bool_flag(value) -> bool:
    try:
        return int(value) == 1
    except Exception:
        return bool(value)


def pick_current_user_id(current_user: dict | None) -> int | None:
    if not current_user:
        return None
    return _to_int(current_user.get("user_id") or current_user.get("id") or current_user.get("userid"))


def pick_current_usertype_id(current_user: dict | None) -> int | None:
    if not current_user:
        return None
    return _to_int(current_user.get("usertypeID"))


async def get_usertype_flags_by_id(usertype_id: int | None) -> dict:
    if usertype_id is None:
        return {"UserTypeID": None, "MasterF": False, "AdminF": False, "AllowedF": None}

    async with async_session() as session:
        stmt = (
            select(UserType.ID, UserType.MasterF, UserType.AdminF, UserType.AllowedF)
            .where(UserType.ID == int(usertype_id))
            .limit(1)
        )
        res = await retry_query_on_error(lambda: session.execute(stmt))
        row = res.first()
        if not row:
            return {"UserTypeID": int(usertype_id), "MasterF": False, "AdminF": False, "AllowedF": None}
        return {
            "UserTypeID": int(row[0]),
            "MasterF": _to_bool_flag(row[1]),
            "AdminF": _to_bool_flag(row[2]),
            "AllowedF": row[3],
        }


async def get_scope_context(current_user: dict | None) -> dict:
    current_user_id = pick_current_user_id(current_user)
    current_usertype_id = pick_current_usertype_id(current_user)
    flags = await get_usertype_flags_by_id(current_usertype_id)
    return {
        "current_user_id": current_user_id,
        "current_usertype_id": current_usertype_id,
        "is_MasterF": bool(flags.get("MasterF")),
        "is_AdminF": bool(flags.get("AdminF")),
    }


async def get_user_summary(user_id: int | None) -> dict | None:
    if user_id is None:
        return None

    async with async_session() as session:
        stmt = (
            select(
                User.ID,
                User.AllowedF,
                User.UserTypeID,
                User.CabangID,
                UserType.AllowedF,
                UserType.MasterF,
                UserType.AdminF,
            )
            .select_from(User)
            .outerjoin(UserType, UserType.ID == User.UserTypeID)
            .where(User.ID == int(user_id))
            .limit(1)
        )
        res = await retry_query_on_error(lambda: session.execute(stmt))
        row = res.first()
        if not row:
            return None
        return {
            "UserID": int(row[0]),
            "AllowedF": _to_bool_flag(row[1]),
            "UserTypeID": _to_int(row[2]),
            "CabangID": _to_int(row[3]),
            "UserTypeAllowedF": (_to_bool_flag(row[4]) if row[4] is not None else None),
            "MasterF": _to_bool_flag(row[5]),
            "AdminF": _to_bool_flag(row[6]),
        }


async def can_assign_usertype(current_user: dict | None, target_usertype_id: int | None) -> bool:
    if target_usertype_id is None:
        return False

    scope = await get_scope_context(current_user)

    if scope["is_MasterF"]:
        return True
    if scope["is_AdminF"]:
        current_usertype_id = scope.get("current_usertype_id")
        return current_usertype_id is not None and int(current_usertype_id) == int(target_usertype_id)

    current_usertype_id = scope.get("current_usertype_id")
    return current_usertype_id is not None and int(current_usertype_id) == int(target_usertype_id)


async def can_set_usertype_flags(current_user: dict | None, *, masterf: int | bool | None, adminf: int | bool | None) -> bool:
    scope = await get_scope_context(current_user)
    target_masterf = _to_bool_flag(masterf) if masterf is not None else False
    target_adminf = _to_bool_flag(adminf) if adminf is not None else False

    if scope["is_MasterF"]:
        return True
    if scope["is_AdminF"]:
        return not target_masterf
    return not target_masterf and not target_adminf


async def can_create_usertype(current_user: dict | None) -> bool:
    scope = await get_scope_context(current_user)
    return bool(scope["is_MasterF"])


async def can_access_usertype(current_user: dict | None, target_usertype_id: int | None) -> bool:
    if target_usertype_id is None:
        return False

    scope = await get_scope_context(current_user)
    target_flags = await get_usertype_flags_by_id(target_usertype_id)

    if scope["is_MasterF"]:
        return True
    if scope["is_AdminF"]:
        return not bool(target_flags.get("MasterF"))

    current_usertype_id = scope.get("current_usertype_id")
    return current_usertype_id is not None and int(current_usertype_id) == int(target_usertype_id)


async def can_manage_usertype(current_user: dict | None, target_usertype_id: int | None) -> bool:
    scope = await get_scope_context(current_user)
    if not scope["is_MasterF"]:
        return False
    return target_usertype_id is not None


async def can_assign_cabang(current_user: dict | None, target_cabang_id: int | None) -> bool:
    if target_cabang_id is None:
        return False

    scope = await get_scope_context(current_user)
    if scope["is_MasterF"]:
        return True

    if scope["is_AdminF"]:
        current_user_id = scope.get("current_user_id")
        summary = await get_user_summary(current_user_id)
        if not summary:
            return False
        current_cabang_id = summary.get("CabangID")
        return current_cabang_id is not None and int(current_cabang_id) == int(target_cabang_id)

    return False


async def can_access_user(current_user: dict | None, target_user_id: int | None) -> bool:
    if target_user_id is None:
        return False

    scope = await get_scope_context(current_user)
    target = await get_user_summary(target_user_id)
    if not target:
        return False

    if scope["is_MasterF"]:
        return True
    if scope["is_AdminF"]:
        current_user_id = scope.get("current_user_id")
        summary = await get_user_summary(current_user_id)
        current_cabang_id = _to_int(summary.get("CabangID")) if summary else None
        target_cabang_id = _to_int(target.get("CabangID"))
        return (
            current_cabang_id is not None
            and target_cabang_id is not None
            and current_cabang_id == target_cabang_id
            and not bool(target.get("MasterF"))
        )

    current_user_id = _to_int(scope.get("current_user_id"))
    return current_user_id is not None and current_user_id == int(target_user_id)


async def can_manage_user(current_user: dict | None, target_user_id: int | None) -> bool:
    scope = await get_scope_context(current_user)
    if scope["is_MasterF"]:
        return target_user_id is not None
    if scope["is_AdminF"]:
        return await can_access_user(current_user, target_user_id)
    return False


async def get_cabang_flags_by_id(cabang_id: int | None) -> dict:
    if cabang_id is None:
        return {"CabangID": None, "AllowedF": None}

    async with async_session() as session:
        stmt = select(Cabang.ID, Cabang.AllowedF).where(Cabang.ID == int(cabang_id)).limit(1)
        res = await retry_query_on_error(lambda: session.execute(stmt))
        row = res.first()
        if not row:
            return {"CabangID": int(cabang_id), "AllowedF": None}
        return {
            "CabangID": int(row[0]),
            "AllowedF": row[1],
        }


async def can_access_cabang(current_user: dict | None, target_cabang_id: int | None) -> bool:
    if target_cabang_id is None:
        return False

    scope = await get_scope_context(current_user)
    if scope["is_MasterF"]:
        return True

    current_user_id = scope.get("current_user_id")
    summary = await get_user_summary(current_user_id)
    if not summary:
        return False

    current_cabang_id = summary.get("CabangID")
    return current_cabang_id is not None and int(current_cabang_id) == int(target_cabang_id)


async def can_manage_cabang(current_user: dict | None, target_cabang_id: int | None) -> bool:
    scope = await get_scope_context(current_user)
    if target_cabang_id is None:
        return False
    if scope["is_MasterF"]:
        return True
    if scope["is_AdminF"]:
        return await can_access_cabang(current_user, target_cabang_id)
    return False
