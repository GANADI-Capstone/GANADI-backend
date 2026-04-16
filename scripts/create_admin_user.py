#!/usr/bin/env python3
"""관리자 User 행 생성 (role=admin). 백엔드 루트에서 실행:

  cd backend && python scripts/create_admin_user.py admin@example.com '비밀번호' '관리자'

기존 이메일이 있으면 종료합니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.security import get_password_hash  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402


def main() -> None:
    if len(sys.argv) < 4:
        print("사용법: python scripts/create_admin_user.py <이메일> <비밀번호> <이름>")
        sys.exit(1)
    email, password, name = sys.argv[1], sys.argv[2], sys.argv[3]
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            print("이미 등록된 이메일입니다.")
            sys.exit(1)
        user = User(
            email=email,
            password_hash=get_password_hash(password),
            name=name,
            role="admin",
        )
        db.add(user)
        db.commit()
        print(f"관리자 계정 생성 완료: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
