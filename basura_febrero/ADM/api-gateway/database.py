# database.py - Database Configuration and Setup (CLEAN VERSION)
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import os
import sqlite3
from typing import Generator
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/healthcare_gateway.db")

# Create engine based on database type
if DATABASE_URL.startswith("sqlite"):
    # SQLite configuration
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "check_same_thread": False,
            "timeout": 20
        },
        poolclass=StaticPool,
        echo=False  # Set to True for SQL debugging
    )
    
    # Enable foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
        cursor.close()

elif DATABASE_URL.startswith("mssql") or DATABASE_URL.startswith("azure"):
    # SQL Server / Azure SQL configuration  
    engine = create_engine(
        DATABASE_URL,
        pool_size=20,
        max_overflow=0,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False
    )
else:
    # Generic configuration
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        echo=False
    )

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# ============================================================================
# DATABASE UTILITIES
# ============================================================================

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get database session
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def init_database():
    """Initialize database - simple and safe version"""
    try:
        logger.info("🔄 Initializing database...")
        
        # Import models to register them
        from models import User, Token, Session as DBSession, APIRequest
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        logger.info("✅ Database tables created successfully")
        logger.info("ℹ️ Database initialization completed")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False

def create_tables():
    """Create all tables in the database"""
    try:
        # Import models to ensure they are registered
        from models import User, Token, Session as DBSession, APIRequest
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        return False

def drop_tables():
    """Drop all tables (use with caution!)"""
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("🗑️ All tables dropped")
        return True
    except Exception as e:
        logger.error(f"❌ Error dropping tables: {e}")
        return False

def test_connection():
    """Test database connection"""
    try:
        db = SessionLocal()
        # Use text() for raw SQL in SQLAlchemy 2.0
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False

def get_database_info():
    """Get information about the current database"""
    try:
        info = {
            "database_url": DATABASE_URL,
            "engine": str(engine.url),
            "driver": engine.url.drivername,
            "database": engine.url.database
        }
        
        # Get table count using raw SQL instead of ORM
        try:
            db = SessionLocal()
            
            # Check if tables exist first
            tables_exist = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")).fetchone()
            
            if tables_exist:
                user_count = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
                token_count = db.execute(text("SELECT COUNT(*) FROM tokens")).scalar()
                session_count = db.execute(text("SELECT COUNT(*) FROM sessions")).scalar()
                request_count = db.execute(text("SELECT COUNT(*) FROM api_requests")).scalar()
                
                info["tables"] = {
                    "users": user_count,
                    "tokens": token_count, 
                    "sessions": session_count,
                    "api_requests": request_count
                }
            else:
                info["tables"] = {
                    "users": 0,
                    "tokens": 0,
                    "sessions": 0,
                    "api_requests": 0
                }
            
            db.close()
            
        except Exception as e:
            info["tables"] = {"error": str(e)}
        
        return info
        
    except Exception as e:
        return {"error": str(e)}

def backup_database(backup_path: str = None):
    """Create a backup of SQLite database"""
    if not DATABASE_URL.startswith("sqlite"):
        raise ValueError("Backup only supported for SQLite databases")
    
    try:
        import shutil
        from datetime import datetime
        
        # Extract database path
        db_path = DATABASE_URL.replace("sqlite:///", "")
        
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{db_path}.backup_{timestamp}"
        
        shutil.copy2(db_path, backup_path)
        logger.info(f"✅ Database backed up to: {backup_path}")
        return backup_path
        
    except Exception as e:
        logger.error(f"❌ Database backup failed: {e}")
        raise

def vacuum_database():
    """Optimize SQLite database (reclaim space, reorganize)"""
    if not DATABASE_URL.startswith("sqlite"):
        logger.warning("VACUUM only supported for SQLite databases")
        return False
    
    try:
        db = SessionLocal()
        db.execute(text("VACUUM"))
        db.close()
        logger.info("✅ Database vacuumed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database vacuum failed: {e}")
        return False

def database_health_check():
    """Comprehensive database health check"""
    health_info = {
        "status": "unknown",
        "connection": False,
        "tables_exist": False,
        "data_integrity": False,
        "info": {}
    }
    
    try:
        # Test connection
        health_info["connection"] = test_connection()
        
        if health_info["connection"]:
            # Check tables exist using raw SQL (not ORM)
            db = SessionLocal()
            try:
                # Use raw SQL to check tables
                result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")).fetchone()
                health_info["tables_exist"] = result is not None
                
                if health_info["tables_exist"]:
                    # Basic counts using raw SQL
                    user_count = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
                    token_count = db.execute(text("SELECT COUNT(*) FROM tokens")).scalar()
                    
                    health_info["data_integrity"] = True
                    health_info["info"] = {
                        "users": user_count,
                        "tokens": token_count,
                        "database_type": engine.url.drivername
                    }
                else:
                    health_info["info"]["table_error"] = "Tables not found"
                    
            except Exception as e:
                health_info["info"]["table_error"] = str(e)
            finally:
                db.close()
        
        # Overall status
        if health_info["connection"] and health_info["tables_exist"]:
            health_info["status"] = "healthy"
        elif health_info["connection"]:
            health_info["status"] = "degraded"
        else:
            health_info["status"] = "unhealthy"
            
    except Exception as e:
        health_info["status"] = "error"
        health_info["info"]["error"] = str(e)
    
    return health_info