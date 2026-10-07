from flask import Blueprint, jsonify
from py_eureka_client import eureka_client
from app.config import Config

eureka_bp = Blueprint('eureka', __name__)

async def stop():
    await eureka_client.stop()

async def register():
    print(f"Iniciando registro do {Config.APP_NAME} no Eureka...")
        
    try:
        # Importante: use o init_async para evitar bloqueios
        await eureka_client.init_async(
            eureka_server=Config.EUREKA_SERVER,
            app_name=Config.APP_NAME,
            instance_port=Config.APP_PORT,
            instance_host=Config.INSTANCE_HOST,
            instance_id=f"{Config.APP_NAME}:{Config.APP_PORT}",
            status_page_url=f"http://{Config.INSTANCE_HOST}:{Config.APP_PORT}/info",
            health_check_url=f"http://{Config.INSTANCE_HOST}:{Config.APP_PORT}/health",
            home_page_url=f"http://{Config.INSTANCE_HOST}:{Config.APP_PORT}/",
            metadata={
                "zuul.sensitiveHeaders": "" 
            }
        )
        print("Registro no Eureka concluído com sucesso!")
    except Exception as e:
        print(f"Erro no registro do Eureka: {e}")

@eureka_bp.route('/health')
def health():
    return jsonify({"status": "UP"})

@eureka_bp.route('/info')
def info():
    return jsonify({"app": Config.APP_NAME, "status": "running"})