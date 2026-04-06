FROM node:22-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY server.mjs ./

ENV PORT=8090 \
    WS_URL=ws://localnet:9944 \
    FAUCET_SEED=//Alice

EXPOSE 8090

CMD ["node", "server.mjs"]
