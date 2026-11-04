"""Admin-only encrypted DeepSeek credentials and explicit daily-analysis opt-in.

Secrets remain encrypted in PostgreSQL with a separate Render environment key.
No secret plaintext, encrypted blob, or external provider response is returned
to clients or written to audit events.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from research_workbench.core import Base
from backend.team import add_audit

FAST_MODELS=("deepseek-flash",)
REASON_MODELS=("deepseek-v4-pro","deepseek-flash")

def timestamp():
    return datetime.now(timezone.utc)

class ModelCredential(Base):
    __tablename__="model_credentials"
    provider:Mapped[str]=mapped_column(String(32),primary_key=True)
    encrypted_key:Mapped[str]=mapped_column(Text,default="")
    fast_model:Mapped[str]=mapped_column(String(80),default="deepseek-flash")
    reason_model:Mapped[str]=mapped_column(String(80),default="deepseek-v4-pro")
    daily_enabled:Mapped[bool]=mapped_column(Boolean,default=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=timestamp)

def _vault():
    raw=os.getenv("MODEL_VAULT_KEY","").strip()
    if not raw:
        raise ValueError("加密服务未启用：请由服务器管理员配置 MODEL_VAULT_KEY")
    try:
        return Fernet(raw.encode())
    except (ValueError,TypeError) as exc:
        raise ValueError("模型密钥加密配置无效") from exc

def status(db):
    row=db.get(ModelCredential,"deepseek")
    return {"provider":"deepseek","configured":bool(row and row.encrypted_key),
            "vault_ready":bool(os.getenv("MODEL_VAULT_KEY","").strip()),
            "fast_model":row.fast_model if row else "deepseek-flash",
            "reason_model":row.reason_model if row else "deepseek-v4-pro",
            "daily_enabled":bool(row and row.daily_enabled),
            "key_storage":"server-encrypted" if row and row.encrypted_key else "none"}

def save(db,actor,key=None,fast_model=None,reason_model=None,daily_enabled=None):
    row=db.get(ModelCredential,"deepseek")
    if row is None:
        row=ModelCredential(provider="deepseek")
        db.add(row)
    if key is not None:
        key=key.strip()
        if not 12<=len(key)<=320 or any(x.isspace() for x in key):
            raise ValueError("API Key 格式不符合要求，请检查是否有空格或换行")
        # Server-held Fernet key never shares a storage location with ciphertext.
        row.encrypted_key=_vault().encrypt(key.encode()).decode()
    if fast_model is not None:
        if fast_model not in FAST_MODELS:raise ValueError("不支持的论文解析模型")
        row.fast_model=fast_model
    if reason_model is not None:
        if reason_model not in REASON_MODELS:raise ValueError("不支持的选题推理模型")
        row.reason_model=reason_model
    if daily_enabled is not None:
        if daily_enabled and not row.encrypted_key:
            raise ValueError("请先保存 DeepSeek API Key，再开启每日自动分析")
        row.daily_enabled=bool(daily_enabled)
    row.updated_at=timestamp()
    add_audit(db,"model_config.changed",actor,"deepseek",
              "key_updated="+str(key is not None)+" daily_enabled="+str(row.daily_enabled))
    db.commit()
    return status(db)

def remove_key(db,actor):
    row=db.get(ModelCredential,"deepseek")
    if row:
        row.encrypted_key=""
        row.daily_enabled=False
        row.updated_at=timestamp()
        add_audit(db,"model_config.key_removed",actor,"deepseek")
        db.commit()
    return status(db)

def load_key(db):
    row=db.get(ModelCredential,"deepseek")
    if not row or not row.encrypted_key:return None
    try:
        return _vault().decrypt(row.encrypted_key.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("密钥无法解密：服务器 MODEL_VAULT_KEY 已变化") from exc
