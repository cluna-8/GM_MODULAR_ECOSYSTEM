from ADM_MODULAR.database import SessionLocal, engine
from ADM_MODULAR import models, auth

# Asegurar que las tablas existan
models.Base.metadata.create_all(bind=engine)

db = SessionLocal()

# 1. Crear Usuario Admin de prueba
admin_user = db.query(models.User).filter(models.User.username == "admin_demo").first()
if not admin_user:
    admin_user = models.User(username="admin_demo", role="admin", is_active=True)
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    print("✅ Usuario admin_demo creado")

# 2. Crear el primer Token HCG
test_token = (
    db.query(models.Token).filter(models.Token.name == "Token de Prueba Local").first()
)
if not test_token:
    token_str = "hcg_token_maestro_de_prueba_12345"  # Usamos uno fijo para la prueba
    test_token = models.Token(
        token=token_str, user_id=admin_user.id, name="Token de Prueba Local"
    )
    db.add(test_token)
    db.commit()
    print(f"🚀 Token Maestro Creado: {token_str}")
else:
    print(f"ℹ️ El token ya existe: {test_token.token}")

db.close()
