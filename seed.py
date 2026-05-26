import asyncio
from app.database.session import SessionLocal
from app.models.base import Role

async def seed_roles():
    print("Connecting to the database...")
    async with SessionLocal() as db:
        # 1. FREE TIER ($0)
        free_role = Role(
            name="free",
            description="Default tier. 500 credits/mo.",
            permissions={
                "tools": ["chat"], 
                "admin_access": False
            }
        )
        
        # 2. STARTER TIER ($12)
        starter_role = Role(
            name="starter",
            description="Starter tier. 3,000 credits/mo.",
            permissions={
                "tools": ["chat", "short_content"], 
                "admin_access": False
            }
        )

        # 3. PRO TIER ($39)
        pro_role = Role(
            name="pro",
            description="Pro tier. 12,000 credits/mo.",
            permissions={
                "tools": ["chat", "short_content", "image_generation", "long_form_content"],
                "admin_access": False
            }
        )

        # 4. ENTERPRISE TIER (Custom)
        enterprise_role = Role(
            name="enterprise",
            description="Unlimited custom tier.",
            permissions={
                "tools": ["chat", "short_content", "image_generation", "long_form_content"],
                "admin_access": True 
            }
        )

        # Add them to the session and commit to Supabase
        db.add_all([free_role, starter_role, pro_role, enterprise_role])
        await db.commit()
        print("✅ Successfully seeded Free, Starter, Pro, and Enterprise roles!")

if __name__ == "__main__":
    # This tells Python to actually execute the async function when you run the file
    asyncio.run(seed_roles())