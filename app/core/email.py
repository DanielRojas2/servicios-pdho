import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_smtp_email(to_email: str, subject: str, html_content: str, text_content: str) -> bool:
    """Envío síncrono de correo mediante SMTP (diseñado para ejecutarse en un hilo de trabajo)."""
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        logger.warning("Credenciales SMTP no configuradas. Correo omitido a: %s", to_email)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"PDHO Plataforma Hotelera <{settings.EMAIL_HOST_USER}>"
    msg["To"] = to_email

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=10) as server:
            if settings.EMAIL_USE_TLS:
                server.starttls()
            server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            server.send_message(msg)
            logger.info("Correo enviado exitosamente a: %s", to_email)
            return True
    except Exception as e:
        logger.error("Error al enviar correo SMTP a %s: %s", to_email, str(e))
        return False


async def send_user_credentials_email(
    to_email: str,
    full_name: str,
    plain_password: str,
    role_name: str,
) -> bool:
    """
    Envía las credenciales de acceso al correo institucional o personal del usuario.
    Se ejecuta de forma asíncrona sin bloquear el loop de FastAPI.
    """
    subject = "Credenciales de Acceso - Plataforma Hotelera Oruro (PDHO)"
    
    text_content = f"""Estimado(a) {full_name},

Se ha generado su cuenta de acceso para la Plataforma Hotelera Oruro (PDHO).

Detalles de la cuenta:
- Rol asignado: {role_name}
- Usuario / Correo: {to_email}
- Contraseña temporal: {plain_password}

Por motivos de seguridad, se recomienda cambiar su contraseña en el primer inicio de sesión conforme a las políticas institucionales de AGETIC.

Atentamente,
Gobierno Autónomo Departamental de Oruro
Dirección de Turismo y Cultura
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9; color: #333; margin: 0; padding: 20px; }}
    .container {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e1e4e8; overflow: hidden; }}
    .header {{ background-color: #B22222; color: #ffffff; padding: 24px; text-align: center; }}
    .header h1 {{ margin: 0; font-size: 20px; font-weight: 600; letter-spacing: 0.5px; }}
    .content {{ padding: 28px 24px; line-height: 1.6; font-size: 14px; }}
    .credentials-box {{ background-color: #f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid #087e8b; padding: 16px 20px; margin: 20px 0; border-radius: 4px; }}
    .credentials-box p {{ margin: 6px 0; font-size: 14px; }}
    .credentials-box strong {{ color: #1e293b; }}
    .badge {{ display: inline-block; padding: 4px 10px; font-size: 12px; font-weight: 600; border-radius: 12px; background-color: #e2e8f0; color: #0b3954; }}
    .footer {{ background-color: #f8fafc; color: #64748b; font-size: 12px; text-align: center; padding: 16px; border-top: 1px solid #e2e8f0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Plataforma Hotelera Oruro (PDHO)</h1>
      <p style="margin: 4px 0 0 0; font-size: 13px; opacity: 0.9;">Control y Estadísticas Departamentales</p>
    </div>
    <div class="content">
      <p>Estimado(a) <strong>{full_name}</strong>,</p>
      <p>Se ha creado exitosamente su cuenta de acceso en el sistema. A continuación encontrará sus credenciales:</p>
      
      <div class="credentials-box">
        <p><strong>Rol Asignado:</strong> <span class="badge">{role_name}</span></p>
        <p><strong>Usuario / Correo:</strong> {to_email}</p>
        <p><strong>Contraseña Temporal:</strong> <code>{plain_password}</code></p>
      </div>

      <p>Por normativas de seguridad de la información del Estado (AGETIC), le solicitamos no compartir estas credenciales y renovar su contraseña periódicamente.</p>
    </div>
    <div class="footer">
      <p>Dirección Departamental de Turismo - Gobierno Autónomo Departamental de Oruro</p>
      <p style="margin: 0;">Este es un mensaje automático, por favor no responda a este correo.</p>
    </div>
  </div>
</body>
</html>"""

    # Ejecutar en hilo de trabajo para no congelar el bucle asíncrono
    return await asyncio.to_thread(
        _send_smtp_email,
        to_email,
        subject,
        html_content,
        text_content,
    )
