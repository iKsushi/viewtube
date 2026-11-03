FROM mcr.microsoft.com/playwright:v1.56.1-noble
WORKDIR /tests
RUN npm init -y && npm install --save-exact @playwright/test@1.56.1
COPY . .
CMD ["npx", "playwright", "test"]
