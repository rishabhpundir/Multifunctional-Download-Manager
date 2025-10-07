from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import os


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db.sqlite3")
engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", future=True)
Session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase): pass

async def init_db():
    from .models import Download
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


