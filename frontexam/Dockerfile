FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

RUN npm run build

EXPOSE 4321
CMD ["npx", "astro", "preview", "--host", "0.0.0.0", "--port", "4321"]