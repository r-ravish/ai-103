import asyncio
import sys
import os
from dotenv import load_dotenv

# Ensure we can import from app and db
sys.path.insert(0, os.path.abspath('.'))
load_dotenv('.env')

from app.security import hash_password
from db.database import AsyncSessionLocal
from db.models import User, UserRole
from sqlalchemy import select

async def create():
    async with AsyncSessionLocal() as session:
        # 1. Employee Account
        emp_email = "employee@company.com"
        emp_password = "password123"
        existing_emp = (await session.execute(select(User).where(User.email == emp_email))).scalar_one_or_none()
        if existing_emp:
            existing_emp.password_hash = hash_password(emp_password)
            existing_emp.role = UserRole.employee
            print(f"Updated employee: {emp_email} / {emp_password}")
        else:
            user = User(
                name="Demo Employee",
                email=emp_email,
                password_hash=hash_password(emp_password),
                role=UserRole.employee
            )
            session.add(user)
            print(f"Created employee: {emp_email} / {emp_password}")

        # 2. Admin Account
        admin_email = "admin@company.com"
        admin_password = "adminpassword"
        existing_admin = (await session.execute(select(User).where(User.email == admin_email))).scalar_one_or_none()
        if existing_admin:
            existing_admin.password_hash = hash_password(admin_password)
            existing_admin.role = UserRole.admin
            print(f"Updated admin: {admin_email} / {admin_password}")
        else:
            user = User(
                name="System Admin",
                email=admin_email,
                password_hash=hash_password(admin_password),
                role=UserRole.admin
            )
            session.add(user)
            print(f"Created admin: {admin_email} / {admin_password}")
            
        await session.commit()

if __name__ == "__main__":
    asyncio.run(create())
