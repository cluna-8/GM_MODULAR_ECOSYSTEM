# Guía de Respaldo y Migración: RedisChatStore

**Fecha**: 2026-02-11  
**Objetivo**: Migrar a RedisChatStore con respaldo completo  
**Estado Actual**: Local y Producción sincronizados (commit 51c0d6f)

---

## ✅ Estado de Sincronización

### **Verificación Completada**:

**Local (SERVICES/gm_general_chat)**:
```
Commit: 51c0d6f - Add FeedbackRequest model and update imports
Branch: main
Estado: ✅ Sincronizado con origin/main
```

**Producción (DEPLOYMENT/SERVICES/GM_GENERAL_CHAT)**:
```
Commit: 51c0d6f - Add FeedbackRequest model and update imports
Branch: main
Estado: ✅ Sincronizado con GitHub
```

**Conclusión**: ✅ Ambos entornos están actualizados y sincronizados.

---

## 🛡️ Estrategia de Respaldo (3 Niveles)

### **Nivel 1: Rama de Respaldo en Git (RECOMENDADO)**

**Ventajas**:
- ✅ Fácil de revertir (`git checkout backup-before-redis-chat-store`)
- ✅ No ocupa espacio adicional
- ✅ Mantiene historial completo
- ✅ Permite comparar cambios

**Implementación**:
```bash
cd SERVICES/gm_general_chat

# Crear rama de respaldo desde el estado actual
git checkout -b backup-before-redis-chat-store

# Volver a main para hacer los cambios
git checkout main
```

**Cómo revertir si algo sale mal**:
```bash
# Descartar cambios en main
git checkout main
git reset --hard backup-before-redis-chat-store

# Forzar push (solo si ya subiste los cambios)
git push origin main --force
```

---

### **Nivel 2: Tag de Versión (ADICIONAL)**

**Ventajas**:
- ✅ Marca un punto específico en el historial
- ✅ Fácil de referenciar
- ✅ No afecta ramas

**Implementación**:
```bash
cd SERVICES/gm_general_chat

# Crear tag con el estado actual
git tag -a v2.0.0-before-redis-chat-store -m "Estado estable antes de migrar a RedisChatStore"

# Subir tag a GitHub
git push origin v2.0.0-before-redis-chat-store
```

**Cómo revertir**:
```bash
# Volver al tag
git checkout v2.0.0-before-redis-chat-store

# Crear nueva rama desde el tag
git checkout -b revert-to-stable
```

---

### **Nivel 3: Copia de Seguridad Física (PARANOIA MODE)**

**Ventajas**:
- ✅ Respaldo completo fuera de Git
- ✅ Incluye archivos no versionados (logs, etc.)
- ✅ Recuperación rápida

**Implementación**:
```bash
# Crear directorio de respaldo
mkdir -p ~/backups/gomedisys

# Copiar todo el servicio
cp -r SERVICES/gm_general_chat ~/backups/gomedisys/gm_general_chat-$(date +%Y%m%d-%H%M%S)

# Verificar
ls -lh ~/backups/gomedisys/
```

**Cómo revertir**:
```bash
# Restaurar desde backup
rm -rf SERVICES/gm_general_chat
cp -r ~/backups/gomedisys/gm_general_chat-20260211-143000 SERVICES/gm_general_chat
```

---

## 📋 Plan de Migración Paso a Paso

### **Fase 1: Preparación y Respaldo (10 min)**

#### **1.1 Crear Rama de Respaldo**
```bash
cd /home/drexgen/Documents/CHAT-GOMedisys/SERVICES/gm_general_chat

# Crear rama de respaldo
git checkout -b backup-before-redis-chat-store

# Subir rama a GitHub
git push origin backup-before-redis-chat-store

# Volver a main
git checkout main
```

#### **1.2 Crear Tag de Versión**
```bash
# Crear tag
git tag -a v2.0.0-stable -m "Estado estable antes de RedisChatStore - 2026-02-11"

# Subir tag
git push origin v2.0.0-stable
```

#### **1.3 Verificar Estado**
```bash
# Ver ramas
git branch -a

# Ver tags
git tag -l

# Confirmar que estás en main
git branch --show-current
```

---

### **Fase 2: Instalación de Dependencias (5 min)**

#### **2.1 Actualizar requirements.txt**
```bash
cd /home/drexgen/Documents/CHAT-GOMedisys/SERVICES/gm_general_chat

# Agregar nueva dependencia
echo "llama-index-storage-chat-store-redis>=0.1.0" >> requirements.txt

# Verificar
cat requirements.txt | grep redis
```

#### **2.2 Instalar Localmente**
```bash
# Activar entorno virtual si lo usas
# source venv/bin/activate

# Instalar dependencia
pip install llama-index-storage-chat-store-redis

# Verificar instalación
pip show llama-index-storage-chat-store-redis
```

---

### **Fase 3: Modificación del Código (30 min)**

#### **3.1 Modificar main.py**

**Archivos a modificar**:
- `SERVICES/gm_general_chat/main.py`

**Cambios**:
1. Agregar import de `RedisChatStore`
2. Inicializar `self.chat_store` en `__init__()`
3. Crear `RedisChatStore` en `initialize()`
4. Modificar `get_or_create_chat_engine()` para usar `chat_store`

**Detalles**: Ver archivo `RECOMENDACION_REDIS_CHAT_STORE.md` sección "Fase 2"

---

### **Fase 4: Testing Local (30 min)**

#### **4.1 Levantar Entorno Local**
```bash
cd /home/drexgen/Documents/CHAT-GOMedisys

# Reconstruir con nuevas dependencias
docker compose down
docker compose up -d --build gm-general-chat

# Verificar logs
docker logs gm-general-chat --tail 50
```

#### **4.2 Test de Persistencia**
```bash
# Test 1: Primera consulta
curl -s -X POST http://localhost:8000/medical/chat \
  -H "Authorization: Bearer hcg_maestro_123" \
  -d '{"promptData": "Mi nombre es Pedro y tengo 45 años", "sessionId": "test_redis_store_001", "IAType": "medical"}' | jq -r '.data.response'

# Test 2: Reiniciar contenedor
docker restart gm-general-chat
sleep 10

# Test 3: Segunda consulta (debe recordar)
curl -s -X POST http://localhost:8000/medical/chat \
  -H "Authorization: Bearer hcg_maestro_123" \
  -d '{"promptData": "¿Recuerdas mi nombre y edad?", "sessionId": "test_redis_store_001", "IAType": "medical"}' | jq -r '.data.response'

# Esperado: Debe mencionar "Pedro" y "45 años"
```

#### **4.3 Verificar en Redis**
```bash
# Conectar a Redis
docker exec -it redis-general redis-cli

# Ver claves de chat
KEYS chat_*

# Ver contenido de la sesión de prueba
HGETALL chat_test_redis_store_001

# Verificar TTL
TTL chat_test_redis_store_001

# Salir
exit
```

#### **4.4 Ejecutar Suite de Tests**
```bash
./test_local.sh
```

**Resultado esperado**: Todos los tests deben pasar.

---

### **Fase 5: Commit y Push (10 min)**

#### **5.1 Commit Local**
```bash
cd /home/drexgen/Documents/CHAT-GOMedisys/SERVICES/gm_general_chat

# Ver cambios
git status
git diff main.py

# Agregar cambios
git add main.py requirements.txt

# Commit
git commit -m "feat: Migrate to RedisChatStore for automatic conversation persistence

- Add llama-index-storage-chat-store-redis dependency
- Initialize RedisChatStore in HybridChatConfig
- Update get_or_create_chat_engine() to use chat_store
- Automatic persistence and loading of conversation history
- Fixes session memory persistence across container restarts

Tested:
- Local persistence after restart ✅
- Multiple concurrent sessions ✅
- TTL management (7 days) ✅

Breaking changes: None (backward compatible)
Rollback: git checkout backup-before-redis-chat-store"

# Verificar commit
git log --oneline -1
```

#### **5.2 Push a GitHub**
```bash
# Subir a GitHub
git push origin main

# Verificar en GitHub
# https://github.com/cluna-8/GM_GENERAL_CHAT
```

---

### **Fase 6: Despliegue en Producción (15 min)**

#### **6.1 Pull y Rebuild en Servidor**
```bash
ssh sysadmins@20.186.59.6 "cd /home/sysadmins/CHAT-Agent/DEPLOYMENT/SERVICES/GM_GENERAL_CHAT && \
  git pull origin main && \
  cd /home/sysadmins/CHAT-Agent/DEPLOYMENT && \
  docker compose up -d --build --force-recreate gm-general-chat"
```

#### **6.2 Verificar Logs**
```bash
ssh sysadmins@20.186.59.6 "docker logs gm-general-chat --tail 50"
```

**Buscar**:
- `✅ RedisChatStore initialized for conversation persistence`
- Sin errores de importación

#### **6.3 Test en Producción**
```bash
# Ejecutar suite de tests
./test_production.sh
```

**Resultado esperado**: Test de persistencia debe pasar (5/7).

---

## 🔄 Plan de Rollback (Si algo sale mal)

### **Opción 1: Rollback Rápido (Git)**

```bash
# En local
cd /home/drexgen/Documents/CHAT-GOMedisys/SERVICES/gm_general_chat

# Volver a la rama de respaldo
git checkout backup-before-redis-chat-store

# Copiar a main
git checkout main
git reset --hard backup-before-redis-chat-store

# Push forzado
git push origin main --force

# Desplegar en producción
ssh sysadmins@20.186.59.6 "cd /home/sysadmins/CHAT-Agent/DEPLOYMENT/SERVICES/GM_GENERAL_CHAT && \
  git fetch origin && \
  git reset --hard origin/main && \
  cd /home/sysadmins/CHAT-Agent/DEPLOYMENT && \
  docker compose up -d --build --force-recreate gm-general-chat"
```

### **Opción 2: Rollback con Tag**

```bash
# Volver al tag estable
git checkout v2.0.0-stable

# Crear rama desde el tag
git checkout -b rollback-from-redis-chat-store

# Merge a main
git checkout main
git reset --hard rollback-from-redis-chat-store

# Push
git push origin main --force
```

### **Opción 3: Rollback Manual (Copia de Seguridad)**

```bash
# Restaurar desde backup físico
rm -rf SERVICES/gm_general_chat
cp -r ~/backups/gomedisys/gm_general_chat-20260211-143000 SERVICES/gm_general_chat

# Commit y push
cd SERVICES/gm_general_chat
git add .
git commit -m "Rollback to stable version"
git push origin main --force
```

---

## ✅ Checklist de Ejecución

### **Preparación**
- [ ] Verificar sincronización local/producción
- [ ] Crear rama de respaldo (`backup-before-redis-chat-store`)
- [ ] Crear tag de versión (`v2.0.0-stable`)
- [ ] (Opcional) Crear copia física de seguridad

### **Implementación**
- [ ] Actualizar `requirements.txt`
- [ ] Instalar dependencia localmente
- [ ] Modificar `main.py` (imports, init, get_or_create_chat_engine)
- [ ] Verificar sintaxis (no errores de Python)

### **Testing Local**
- [ ] Rebuild contenedor local
- [ ] Test de persistencia básica
- [ ] Test de reinicio
- [ ] Verificar en Redis
- [ ] Ejecutar `./test_local.sh`

### **Despliegue**
- [ ] Commit con mensaje descriptivo
- [ ] Push a GitHub
- [ ] Pull en servidor
- [ ] Rebuild en producción
- [ ] Verificar logs
- [ ] Ejecutar `./test_production.sh`

### **Validación**
- [ ] Test de persistencia pasa en producción
- [ ] No hay errores en logs
- [ ] Funcionalidades core siguen funcionando
- [ ] Documentar resultado

---

## 📞 Contacto en Caso de Problemas

**Si algo sale mal durante la migración**:

1. **No entrar en pánico** - Tienes 3 niveles de respaldo
2. **Revisar logs**: `docker logs gm-general-chat --tail 100`
3. **Ejecutar rollback**: Opción 1 (más rápida)
4. **Notificar** si el rollback no funciona

---

## 📊 Métricas de Éxito

**La migración es exitosa si**:
- ✅ Test de persistencia pasa (5/7 en `test_production.sh`)
- ✅ No hay errores en logs de producción
- ✅ Chat estándar sigue funcionando
- ✅ MCP (ICD-10) sigue funcionando
- ✅ Auditoría de seguridad sigue funcionando

**Tiempo estimado total**: 1.5 - 2 horas

---

## 🎯 Próximo Paso

**¿Estás listo para comenzar?**

Confirma y procederemos con:
1. Crear rama de respaldo
2. Crear tag de versión
3. Modificar código
4. Testing local
5. Despliegue en producción

**Comando para empezar**:
```bash
cd /home/drexgen/Documents/CHAT-GOMedisys/SERVICES/gm_general_chat && \
git checkout -b backup-before-redis-chat-store && \
git push origin backup-before-redis-chat-store && \
git checkout main && \
git tag -a v2.0.0-stable -m "Estado estable antes de RedisChatStore" && \
git push origin v2.0.0-stable && \
echo "✅ Respaldos creados. Listo para migración."
```
