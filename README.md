# 🐳 SGPP CCO Tools

Ferramentas de correção, gestão e visualização de CCOs (Conta Custo Óleo).

## 📋 Índice

- [Pré-requisitos](#pré-requisitos)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Instalação e Configuração](#instalação-e-configuração)
- [Uso Básico](#uso-básico)
- [Comandos Make](#comandos-make)
- [Configuração Avançada](#configuração-avançada)
- [Troubleshooting](#troubleshooting)

## 🔧 Pré-requisitos

- **Docker**: versão 20.10 ou superior
- **Docker Compose**: versão 2.0 ou superior
- **Make**: para usar comandos facilitados (opcional)

### Instalação Docker

**Ubuntu/Debian:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

**Windows/Mac:** 
- Instalar [Docker Desktop](https://www.docker.com/products/docker-desktop)

Verificar instalação:
```bash
docker --version
docker-compose --version
```

## 📁 Estrutura do Projeto

```
sgpp-cco-tools/
├── app/                        # Código da aplicação Flask
│   ├── __init__.py
│   ├── routes/
│   ├── services/
│   └── utils/
├── init-scripts/               # Scripts de inicialização
│   └── init-mongo.js          # Inicialização MongoDB
├── cache/                      # Cache da aplicação (criado em runtime)
├── uploads/                    # Arquivos enviados (criado em runtime)
├── logs/                       # Logs da aplicação (criado em runtime)
├── Dockerfile                  # Definição da imagem Docker
├── docker-compose.yml          # Orquestração de containers
├── gunicorn.conf.py           # Configuração Gunicorn
├── wsgi.py                    # Entry point WSGI
├── requirements.txt           # Dependências Python
├── .env                       # Variáveis de ambiente (criar a partir do .env.example)
├── .env.example               # Template de variáveis de ambiente
├── .dockerignore              # Arquivos ignorados no build
└── Makefile                   # Comandos facilitados
```

## 🚀 Instalação e Configuração

### 1. Clonar o Repositório

```bash
git clone git@ssh.dev.azure.com:v3/sda-devops/PPSA%20-%20SGPP%20-%20Repositorio/sgpp-cco-tools
cd sgpp-cco-tools
```

### 2. Configurar Variáveis de Ambiente

```bash
# Copiar template
cp .env.example .env

# Editar com suas configurações
nano .env  # ou vim, code, etc.
```

**Variáveis importantes a configurar:**

```env
# Segurança - MUDAR EM PRODUÇÃO!
SECRET_KEY=your-super-secret-key-change-this-in-production
MONGO_ROOT_PASSWORD=your-strong-password

# MongoDB
MONGO_ROOT_USERNAME=admin
MONGO_DATABASE=sgppServices

# Aplicação
APP_PORT=5005
FLASK_ENV=production

#Eureka/Gateway
EUREKA_SERVER=http://admin:senha@localhost:8761/eureka/
URL_AUTH_GATEWAY=http://localhost:8080/api/authenticate
```

### 3. Criar Diretórios Necessários

```bash
mkdir -p init-scripts cache uploads logs
```

### 4. Criar Script de Inicialização MongoDB

Copiar o arquivo `init-mongo.js` para o diretório `init-scripts/`.

## 🎯 Uso Básico

### Usando Make (Recomendado)

```bash
# Ver todos os comandos disponíveis
make help

# Build e iniciar containers
make build
make up

# Ou fazer tudo de uma vez
make deploy
```

### Usando Docker Compose Diretamente

```bash
# Build das imagens
docker-compose build

# Iniciar containers
docker-compose up -d

# Ver logs
docker-compose logs -f

# Parar containers
docker-compose down
```

### Gateway

```bash
# Para navegar no sgpp-cco-tools é necessário que o projeto sgpp-gateway esteja rodando, ele é responsável pelo registro e autenticação da aplicação.
# Subir as seguintes imagens, presentes na pasta docker do gateway:

docker-compose -f src/main/docker/mongodb.yml up -d
docker-compose -f src/main/docker/jhipster-registry.yml up -d
docker-compose -f src/main/docker/kafka.yml up -d

# Então subir o gateway e depois o sgpp-cco-tools.
# Ao subir, o seguinte log aparecerá:
Registro no Eureka concluído com sucesso!

# É possível conferir se a aplicação está registrada com sucesso acessando o Eureka e verificando o "Instances Registered"
http://localhost:8761/

# Com isso é possível logar normalmente na aplicação sgpp-cco-tools por meio do Gateway:
http://localhost:8080/sgpp-cco-tools/

# Caso queira desabilitar a autenticação para testes, é necessário adicionar a variável no .env:
DISABLE_AUTH=True
# Depois é só acessar a aplicação diretamente
http://localhost:5006/
```


### Acessar a Aplicação

Após iniciar os containers:

- **SGPP CCO Tools**: http://localhost:5005
- **MongoDB**: localhost:27017
- **Mongo Express** (modo debug): http://localhost:8081

## 🛠 Comandos Make

### Gerenciamento de Containers

```bash
make build          # Build das imagens Docker
make build-fast     # Build rápido (usa cache)
make up             # Inicia containers
make up-debug       # Inicia com Mongo Express
make down           # Para containers
make restart        # Reinicia containers
make restart-app    # Reinicia apenas a aplicação
```

### Logs e Monitoramento

```bash
make logs           # Logs de todos os containers
make logs-app       # Logs da aplicação
make logs-db        # Logs do MongoDB
make status         # Status dos containers
make stats          # Estatísticas de uso em tempo real
make health         # Verifica saúde dos containers
```

### Acesso Shell

```bash
make shell          # Shell do container da aplicação
make db-shell       # MongoDB shell (admin)
make db-shell-app   # MongoDB shell (sgppServices)
```

### Operações de Banco de Dados

```bash
make db-backup      # Backup do MongoDB
make db-restore BACKUP=./backups/backup-20240101-120000  # Restaurar backup
make db-init        # Reinicializar banco (CUIDADO!)
```

### Limpeza

```bash
make clean          # Remove tudo (containers, volumes, imagens)
make clean-cache    # Remove apenas cache
make down-volumes   # Remove containers e dados (CUIDADO!)
```

## ⚙️ Configuração Avançada

### Ajustar Recursos dos Containers

Editar `docker-compose.yml`:

```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '4'      # Limite de CPUs
          memory: 4G     # Limite de memória
        reservations:
          cpus: '2'      # CPU reservada
          memory: 1G     # Memória reservada
```

### Configurar Gunicorn Workers

No arquivo `.env`:

```env
# Fórmula recomendada: (2 x número_de_cores) + 1
GUNICORN_WORKERS=9  # Para servidor de 4 cores

# Timeout para operações longas
GUNICORN_TIMEOUT=600  # 10 minutos

# Worker class
GUNICORN_WORKER_CLASS=sync  # ou gevent para I/O-bound
```

### Habilitar HTTPS

1. Obter certificados SSL
2. Configurar no `gunicorn.conf.py`:

```python
keyfile = "/path/to/key.pem"
certfile = "/path/to/cert.pem"
```

3. Montar volumes no `docker-compose.yml`:

```yaml
volumes:
  - ./certs:/certs:ro
```

### Configurar Proxy Reverso (Nginx)

Criar arquivo `nginx.conf`:

```nginx
upstream sgpp_cco_tools {
    server app:5005;
}

server {
    listen 80;
    server_name sgpp_cco_tools.exemplo.com;

    location / {
        proxy_pass http://sgpp_cco_tools;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Adicionar ao `docker-compose.yml`:

```yaml
nginx:
  image: nginx:latest
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx.conf:/etc/nginx/conf.d/default.conf
  depends_on:
    - app
```

## 🔍 Troubleshooting

### Container não inicia

```bash
# Verificar logs
make logs-app

# Verificar status
make status

# Remover e recriar
make down
make build
make up
```

### Erro de conexão com MongoDB

```bash
# Verificar se MongoDB está rodando
docker ps | grep mongodb

# Testar conexão
make db-shell

# Verificar variáveis de ambiente
docker exec sgpp-cco-tools-app env | grep MONGO
```

### Problemas de Performance

```bash
# Verificar uso de recursos
make stats

# Ajustar workers no .env
GUNICORN_WORKERS=8
GUNICORN_THREADS=4

# Reiniciar aplicação
make restart-app
```

### Cache corrompido

```bash
# Limpar cache
make clean-cache

# Reiniciar aplicação
make restart-app
```

### Porta já em uso

```bash
# Verificar processos na porta
lsof -i :5005

# Ou usar porta diferente no .env
APP_PORT=5006
```

### Logs estão muito grandes

```bash
# Limpar logs Docker
docker system prune -a

# Configurar rotação de logs no docker-compose.yml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

## 🔐 Segurança

### Checklist de Segurança

- [ ] Alterar `SECRET_KEY` no `.env`
- [ ] Usar senha forte para MongoDB
- [ ] Não commitar arquivo `.env`
- [ ] Usar usuário não-root nos containers (já configurado)
- [ ] Habilitar HTTPS em produção
- [ ] Configurar firewall adequadamente
- [ ] Manter imagens Docker atualizadas
- [ ] Fazer backups regulares

### Backup Automático

Criar script cron para backup diário:

```bash
# Adicionar ao crontab
0 2 * * * cd /path/to/sgpp-cco-tools && make db-backup
```

## 📊 Monitoramento

### Healthchecks

Os containers possuem healthchecks configurados:

```bash
# Verificar saúde
make health

# Ou manualmente
docker inspect sgpp-cco-tools-app | grep -A 10 Health
```

### Logs Estruturados

Logs são escritos em stdout/stderr e podem ser integrados com:

- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Grafana Loki**
- **Splunk**
- **CloudWatch** (AWS)

## 🚢 Deploy em Produção

### Usando Docker Swarm

```bash
# Inicializar swarm
docker swarm init

# Deploy
docker stack deploy -c docker-compose.yml sgpp-cco-tools
```

### Usando Kubernetes

Converter docker-compose para Kubernetes:

```bash
kompose convert
kubectl apply -f .
```

## 📝 Manutenção

### Atualização da Aplicação

```bash
# Pull código novo
git pull

# Rebuild e restart
make build
make restart
```

### Atualização de Dependências

```bash
# Editar requirements.txt
# Rebuild imagem
make build
make restart
```

## 📚 Recursos Adicionais

- [Documentação Docker](https://docs.docker.com/)
- [Documentação Docker Compose](https://docs.docker.com/compose/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [MongoDB Documentation](https://docs.mongodb.com/)

## 🆘 Suporte

Para problemas ou dúvidas:

1. Verificar seção [Troubleshooting](#troubleshooting)
2. Consultar logs: `make logs`
3. Contatar equipe de desenvolvimento

---

**Desenvolvido pela Equipe PPSA** 🛢️