from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    # Separador de argumentos al mostrar fórmulas de Excel: «;» en Argentina, «,» en México.
    formula_separador_argumentos: str = ";"
    secret_key: str
    gobernanza_password: str
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    google_genai_use_enterprise: bool = False
    google_cloud_project: Optional[str] = None
    google_cloud_location: str = "global"
    google_application_credentials: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    ollama_api_key: Optional[str] = None
    renderix_api_key: Optional[str] = None
    modelos_suspendidos: str = ""  # Identificadores separados por coma; no modifica credenciales.
    # Lector del cuadro (services/lector_mapa.py): apagado | observar (lee y guarda, sin señales) | activo.
    lector_ia: str = "apagado"
    # Lectoras del lector del cuadro y de la interpretación previa, separadas por coma. DeepSeek no lee por defecto:
    # se agrega a mano (LECTOR_LECTORAS=gpt,gemini,deepseek) y entonces hay que volver a declararlo en /privacidad.
    lector_lectoras: str = "gpt,gemini"
    renderix_model: str = "renderix-es:latest"
    renderix_base_url: str = "https://ia.plataformaialocal.com/local/v1"
    openai_model: str = "gpt-4.1-mini"
    # Verificación semántica de citas; configurable por separado del chat.
    openai_model_verificador_incubadora: str = "gpt-5.4-mini"
    anthropic_model: str = "claude-sonnet-4-6"
    gemini_model: str = "gemini-2.5-flash"
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    ollama_model: str = "llama3.1"
    ollama_base_url: str = "http://127.0.0.1:11434"
    monitoreo_proyecto_id: Optional[int] = None  # Piloto habilitado expresamente por el responsable.
    incubadora_ambito: str = "publico"  # «organizacion» adapta la tutora de la Incubadora a empresas, cooperativas y ONG.
    limite_analisis_ia_dia: int = 20  # Análisis (y exploraciones) con IA por usuario en 24 h; 0 = sin tope.
    limite_mensajes_incubadora_dia: int = 150  # Mensajes a la IA de la Incubadora por usuario en 24 h; 0 = sin tope.
    alertas_email: str = ""  # Destinatario fijo de scripts/alerta_errores.py; si falta, el primer admin con correo.
    docente_aviso_email: str = ""  # Correos (separados por coma) que reciben el aviso de cada consulta al docente de la Incubadora.
    usuarios_excluidos_metricas: str = ""  # Correos separados por coma: cuentas de prueba fuera de las métricas.
    app_port: int = 6163
    admin_email: str = "admin@gobernanza.local"
    admin_name: str = "Administrador"
    admin_password: Optional[str] = None
    public_base_url: str = "https://gobernanza.entornodepruebas.com.ar"
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    smtp_tls: bool = True
    smtp_ssl: bool = False

    def modelo_habilitado(self, modelo: str) -> bool:
        return modelo not in {m.strip().lower() for m in self.modelos_suspendidos.split(",") if m.strip()}


settings = Settings()  # type: ignore[call-arg]
