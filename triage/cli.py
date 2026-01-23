# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Command-line interface for AI Secretary."""

import os
import sys
import logging
from datetime import date
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv

from triage.jira_client import JiraClient, JiraConnectionError, JiraAuthError
from triage.task_classifier import TaskClassifier
from triage.plan_generator import PlanGenerator

# Load environment variables from .env file
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)


class Config:
    """Configuration management for AI Secretary."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        self.jira_base_url = os.environ.get('JIRA_BASE_URL', '')
        self.jira_email = os.environ.get('JIRA_EMAIL', '')
        self.jira_api_token = os.environ.get('JIRA_API_TOKEN', '')
        self.jira_project = os.environ.get('JIRA_PROJECT', '')  # Optional project filter
        self.admin_time_start = os.environ.get('ADMIN_TIME_START', '14:00')
        self.admin_time_end = os.environ.get('ADMIN_TIME_END', '15:30')
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate that required configuration is present.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.jira_base_url:
            return False, "JIRA_BASE_URL environment variable is required"
        
        if not self.jira_email:
            return False, "JIRA_EMAIL environment variable is required"
        
        if not self.jira_api_token:
            return False, "JIRA_API_TOKEN environment variable is required"
        
        return True, None


@click.group()
@click.version_option(version='0.1.0', prog_name='TrIAge')
@click.pass_context
def cli(ctx):
    """TrIAge - Sistema de soporte de ejecución para profesionales técnicos.
    
    TrIAge reduce la carga cognitiva generando planes diarios enfocados con
    un máximo de 3 prioridades reales. Trata a JIRA como la única fuente de
    verdad y opera de forma asíncrona.
    
    \b
    Características principales:
      • Generación automática de planes diarios
      • Clasificación inteligente de tareas
      • Detección de dependencias
      • Agrupación de tareas administrativas
      • Seguimiento de tasa de cierre
      • Descomposición de tareas largas
      • Re-planificación automática
    
    \b
    Configuración:
      Las credenciales se cargan automáticamente desde el archivo .env
      en la raíz del proyecto. Ver .env.example para referencia.
    
    \b
    Ejemplos:
      triage generate-plan              # Generar plan diario
      triage generate-plan -o plan.md   # Guardar en archivo
      triage generate-plan --debug      # Modo debug
      triage --help                     # Ver ayuda
    
    \b
    Documentación:
      https://github.com/your-org/triage
    """
    # Ensure context object exists
    ctx.ensure_object(dict)


@cli.command()
@click.option(
    '--output', '-o',
    type=click.Path(),
    metavar='PATH',
    help='Guardar plan en archivo (por defecto: stdout)'
)
@click.option(
    '--closure-rate',
    type=float,
    metavar='FLOAT',
    help='Tasa de cierre del día anterior (0.0-1.0, ej: 0.67 para 67%%)'
)
@click.option(
    '--debug',
    is_flag=True,
    help='Habilitar logging detallado para debugging'
)
@click.pass_context
def generate_plan(ctx, output: Optional[str], closure_rate: Optional[float], debug: bool):
    """Generar un plan diario desde las tareas actuales de JIRA.
    
    Este comando obtiene tus tareas activas de JIRA, las clasifica, y genera
    un plan diario estructurado con hasta 3 tareas prioritarias y tareas
    administrativas agrupadas.
    
    \b
    El plan incluye:
      • Hasta 3 tareas prioritarias (cerrable en el mismo día)
      • Bloque administrativo (máximo 90 minutos)
      • Otras tareas activas (para referencia)
      • Tasa de cierre del día anterior (si se proporciona)
    
    \b
    Configuración (variables de entorno en .env):
    
    \b
    Requeridas:
      JIRA_BASE_URL     URL de tu instancia JIRA
                        Ejemplo: https://empresa.atlassian.net
      
      JIRA_EMAIL        Tu email de cuenta JIRA
                        Ejemplo: usuario@empresa.com
      
      JIRA_API_TOKEN    Tu token de API de JIRA
                        Generar en: https://id.atlassian.com/manage-profile/security/api-tokens
    
    \b
    Opcionales:
      JIRA_PROJECT      Filtrar tareas por proyecto (ej: PROJ)
                        Dejar vacío para ver todos los proyectos
      
      ADMIN_TIME_START  Hora de inicio del bloque admin (por defecto: 14:00)
      ADMIN_TIME_END    Hora de fin del bloque admin (por defecto: 15:30)
    
    \b
    Criterios de selección de prioridades:
      ✓ Sin dependencias de terceros
      ✓ Esfuerzo estimado ≤ 1 día
      ✓ No son tareas administrativas
      ✓ No son tareas bloqueantes (van por flujo de re-planificación)
    
    \b
    Ejemplos:
    
    \b
      # Generar plan a consola
      $ triage generate-plan
    
    \b
      # Guardar plan en archivo
      $ triage generate-plan -o daily-plan.md
      $ triage generate-plan --output plan-2026-01-23.md
    
    \b
      # Incluir tasa de cierre del día anterior
      $ triage generate-plan --closure-rate 0.67
      # (2 de 3 tareas completadas = 67%)
    
    \b
      # Modo debug con logging detallado
      $ triage generate-plan --debug
      $ triage generate-plan --debug 2> debug.log
    
    \b
      # Combinación de opciones
      $ triage generate-plan --debug -o plan.md --closure-rate 0.75
    
    \b
    Salida:
      El plan se genera en formato Markdown con:
      - Encabezado con fecha
      - Tasa de cierre del día anterior (si disponible)
      - Sección de prioridades (máximo 3)
      - Bloque administrativo con horario
      - Otras tareas activas para referencia
    
    \b
    Troubleshooting:
      • Error de autenticación: Verifica JIRA_EMAIL y JIRA_API_TOKEN
      • Sin tareas elegibles: Usa --debug para ver criterios de filtrado
      • Error de conexión: Verifica JIRA_BASE_URL y conectividad
      • Ver logs: Usa --debug y redirige stderr a archivo
    
    \b
    Ver también:
      • Guía de logging: docs/LOGGING_GUIDE.md
      • Diagnóstico JIRA: python examples/diagnose-jira-connection.py
      • Validación MVP: python examples/validate_mvp.py
    """
    # Configure logging
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger.info("Starting TrIAge plan generation")
    
    # Load configuration
    config = Config()
    
    # Validate configuration
    is_valid, error_message = config.validate()
    if not is_valid:
        logger.error(f"Configuration validation failed: {error_message}")
        click.echo("❌ " + click.style("Error de Configuración", fg='red', bold=True), err=True)
        click.echo(f"   {error_message}", err=True)
        click.echo("\n" + click.style("Configuración Requerida:", fg='yellow', bold=True), err=True)
        click.echo("   Crea un archivo .env en la raíz del proyecto con:", err=True)
        click.echo("", err=True)
        click.echo("   " + click.style("JIRA_BASE_URL", fg='cyan') + "='https://tu-empresa.atlassian.net'", err=True)
        click.echo("   " + click.style("JIRA_EMAIL", fg='cyan') + "='tu-email@empresa.com'", err=True)
        click.echo("   " + click.style("JIRA_API_TOKEN", fg='cyan') + "='tu-token-aqui'", err=True)
        click.echo("", err=True)
        click.echo("   Ver .env.example para más opciones.", err=True)
        click.echo("", err=True)
        click.echo("   " + click.style("Generar token:", fg='yellow'), err=True)
        click.echo("   https://id.atlassian.com/manage-profile/security/api-tokens", err=True)
        sys.exit(1)
    
    # Validate closure rate if provided
    if closure_rate is not None:
        if not 0.0 <= closure_rate <= 1.0:
            logger.error(f"Invalid closure rate: {closure_rate}")
            click.echo("❌ " + click.style("Error", fg='red', bold=True) + ": Tasa de cierre inválida", err=True)
            click.echo(f"   El valor debe estar entre 0.0 y 1.0 (recibido: {closure_rate})", err=True)
            click.echo("", err=True)
            click.echo("   " + click.style("Ejemplos:", fg='yellow'), err=True)
            click.echo("   --closure-rate 0.67  (2 de 3 tareas = 67%)", err=True)
            click.echo("   --closure-rate 1.0   (3 de 3 tareas = 100%)", err=True)
            click.echo("   --closure-rate 0.33  (1 de 3 tareas = 33%)", err=True)
            sys.exit(1)
    
    try:
        # Initialize components
        click.echo("🔄 " + click.style("Conectando a JIRA...", fg='cyan'), err=True)
        logger.info(f"Initializing JIRA client for {config.jira_base_url}")
        jira_client = JiraClient(
            base_url=config.jira_base_url,
            email=config.jira_email,
            api_token=config.jira_api_token,
            project=config.jira_project if config.jira_project else None
        )
        
        classifier = TaskClassifier()
        
        # Update admin time if configured
        admin_time = f"{config.admin_time_start}-{config.admin_time_end}"
        plan_generator = PlanGenerator(jira_client, classifier)
        plan_generator.DEFAULT_ADMIN_TIME = admin_time
        
        # Generate plan
        if config.jira_project:
            click.echo(f"📋 Obteniendo tareas del proyecto " + click.style(config.jira_project, fg='green', bold=True) + "...", err=True)
            logger.info(f"Generating plan for project: {config.jira_project}")
        else:
            click.echo("📋 " + click.style("Obteniendo y clasificando tareas...", fg='cyan'), err=True)
            logger.info("Generating plan for all projects")
        
        plan = plan_generator.generate_daily_plan(previous_closure_rate=closure_rate)
        
        # Format as markdown
        markdown_output = plan.to_markdown()
        
        # Output to file or stdout
        if output:
            output_path = Path(output)
            output_path.write_text(markdown_output)
            click.echo("", err=True)
            click.echo("✅ " + click.style("Plan guardado en:", fg='green', bold=True) + f" {output_path}", err=True)
            logger.info(f"Plan written to file: {output_path}")
        else:
            click.echo()  # Blank line before output
            click.echo(markdown_output)
            logger.debug("Plan written to stdout")
        
        # Print summary to stderr
        click.echo("", err=True)
        click.echo("📊 " + click.style("Resumen del Plan", fg='blue', bold=True) + f" - {plan.date}", err=True)
        click.echo(f"   • Prioridades: " + click.style(str(len(plan.priorities)), fg='green', bold=True) + " tareas", err=True)
        click.echo(f"   • Admin: " + click.style(str(len(plan.admin_block.tasks)), fg='yellow') + f" tareas ({plan.admin_block.time_allocation_minutes} min)", err=True)
        click.echo(f"   • Otras: " + click.style(str(len(plan.other_tasks)), fg='white') + " tareas", err=True)
        
        if plan.previous_closure_rate is not None:
            rate_pct = int(plan.previous_closure_rate * 100)
            rate_color = 'green' if rate_pct >= 67 else 'yellow' if rate_pct >= 33 else 'red'
            click.echo(f"   • Cierre anterior: " + click.style(f"{rate_pct}%", fg=rate_color, bold=True), err=True)
        
        click.echo("", err=True)
        
        logger.info("Plan generation completed successfully")
        
    except JiraAuthError as e:
        logger.error(f"Authentication error: {e}")
        click.echo("", err=True)
        click.echo("❌ " + click.style("Error de Autenticación", fg='red', bold=True), err=True)
        click.echo(f"   {str(e)}", err=True)
        click.echo("", err=True)
        click.echo(click.style("Verifica:", fg='yellow', bold=True), err=True)
        click.echo("   • JIRA_EMAIL es correcto", err=True)
        click.echo("   • JIRA_API_TOKEN es válido", err=True)
        click.echo("   • El token tiene los permisos necesarios", err=True)
        click.echo("", err=True)
        click.echo(click.style("Generar nuevo token:", fg='yellow'), err=True)
        click.echo("   https://id.atlassian.com/manage-profile/security/api-tokens", err=True)
        sys.exit(1)
    
    except JiraConnectionError as e:
        logger.error(f"Connection error: {e}")
        click.echo("", err=True)
        click.echo("❌ " + click.style("Error de Conexión", fg='red', bold=True), err=True)
        click.echo(f"   {str(e)}", err=True)
        click.echo("", err=True)
        click.echo(click.style("Verifica:", fg='yellow', bold=True), err=True)
        click.echo("   • Tu conexión a internet", err=True)
        click.echo("   • JIRA_BASE_URL es correcto", err=True)
        click.echo("   • El servicio JIRA está disponible", err=True)
        click.echo("", err=True)
        click.echo(click.style("Diagnóstico:", fg='yellow'), err=True)
        click.echo("   python examples/diagnose-jira-connection.py", err=True)
        sys.exit(1)
    
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        click.echo("", err=True)
        click.echo("❌ " + click.style("Error Inesperado", fg='red', bold=True), err=True)
        click.echo(f"   {str(e)}", err=True)
        click.echo("", err=True)
        click.echo(click.style("Para más información:", fg='yellow'), err=True)
        click.echo("   • Ejecuta con --debug para ver logs detallados", err=True)
        click.echo("   • Reporta el issue con los logs completos", err=True)
        click.echo("", err=True)
        if not debug:
            click.echo(click.style("Tip:", fg='cyan') + " Ejecuta con --debug para más detalles", err=True)
        sys.exit(1)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == '__main__':
    main()
