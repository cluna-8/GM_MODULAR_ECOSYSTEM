from database import SessionLocal
import models


def seed():
    db = SessionLocal()
    # Crear usuario
    user = db.query(models.User).filter(models.User.username == "admin").first()
    if not user:
        user = models.User(username="admin", role="admin")
        db.add(user)
        db.commit()
        db.refresh(user)

    # Crear Token Maestro para la prueba
    token = (
        db.query(models.Token).filter(models.Token.token == "hcg_maestro_123").first()
    )
    if not token:
        token = models.Token(
            token="hcg_maestro_123", user_id=user.id, name="Token de Prueba"
        )
        db.add(token)
        db.commit()
        print("\n🚀 Gateway Inicializado")
        print("-----------------------")
        print("Token Maestro: hcg_maestro_123")
        print("Endpoint: http://localhost:8000/v1/chat1/chat")
    db.close()


if __name__ == "__main__":
    seed()
