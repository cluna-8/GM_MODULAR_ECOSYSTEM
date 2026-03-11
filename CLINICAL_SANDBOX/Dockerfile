# Dockerfile para Clinical Sandbox
FROM node:20-alpine

WORKDIR /app

# Copiamos solo el package.json para aprovechar la caché de capas
COPY package*.json ./

RUN npm install

# Copiamos el resto del código
COPY . .

# Exponemos el puerto de Vite (por defecto 5173)
EXPOSE 5173

# Comando para desarrollo con hot-reload
CMD ["npm", "run", "dev", "--", "--host"]
