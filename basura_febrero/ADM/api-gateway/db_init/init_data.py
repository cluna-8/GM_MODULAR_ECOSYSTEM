# db_init/init_data.py - Inicialización usando init.sql
import os
import logging
from sqlalchemy import text
from pathlib import Path

logger = logging.getLogger(__name__)

def initialize_database(db_session):
    """Inicializa la base de datos usando init.sql"""
    
    try:
        # PASO 1: Crear tablas usando ORM
        logger.info("🔧 Registrando modelos con ORM...")
        from database import Base, engine
        Base.metadata.create_all(bind=engine)
        
        # PASO 2: Ejecutar init.sql
        sql_file = Path(__file__).parent / "init.sql"
        
        if sql_file.exists():
            logger.info("📄 Ejecutando init.sql...")
            
            # Leer archivo SQL
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # Limpiar comentarios y dividir en declaraciones
            lines = sql_content.split('\n')
            clean_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('--') and not line.startswith('/*'):
                    clean_lines.append(line)
            
            clean_sql = ' '.join(clean_lines)
            statements = [stmt.strip() for stmt in clean_sql.split(';') if stmt.strip()]
            
            executed = 0
            for statement in statements:
                if statement:
                    try:
                        db_session.execute(text(statement))
                        executed += 1
                    except Exception as e:
                        # Ignorar errores de "ya existe"
                        if any(keyword in str(e).lower() for keyword in ['already exists', 'unique constraint', 'duplicate']):
                            continue
                        else:
                            logger.warning(f"⚠️ Error SQL: {e}")
            
            db_session.commit()
            logger.info(f"✅ Ejecutadas {executed} declaraciones SQL")
            
            # Mostrar tokens creados
            _show_tokens(db_session)
            return True
            
        else:
            logger.error("❌ Archivo init.sql no encontrado")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error inicializando base de datos: {e}")
        db_session.rollback()
        return False

def _show_tokens(db_session):
    """Mostrar tokens disponibles"""
    try:
        result = db_session.execute(text("""
            SELECT u.username, u.role, t.name, t.token
            FROM users u JOIN tokens t ON u.id = t.user_id
            WHERE t.status = 'active'
            ORDER BY u.role, u.username
        """))
        
        tokens = result.fetchall()
        
        if tokens:
            logger.info("🔑 Tokens disponibles:")
            for username, role, name, token in tokens:
                logger.info(f"   {username} ({role}): {token}")
        
    except Exception as e:
        logger.warning(f"⚠️ No se pudieron mostrar tokens: {e}")

def setup_database():
    """Función simple para llamar desde main.py"""
    try:
        from database import get_db
        
        db = next(get_db())
        try:
            return initialize_database(db)
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Error en setup_database: {e}")
        return False