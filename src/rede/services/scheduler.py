import os
from datetime import date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from src.rede.services.rotina import RotinaService
from src.rede.utils.log import set_logger
from dotenv import load_dotenv

load_dotenv()
logger = set_logger(__name__)

class SchedulerService:

    def __init__(self):
        self.scheduler = None

    def start_scheduler(self):
        self.inicializar_tarefas()
        self.scheduler.start()
        logger.info("APScheduler iniciado. O job 'atualizar_dados_pagamento' será executado diariamente à 01:00.")

    def stop_scheduler(self):
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
            logger.info("APScheduler encerrado.")

    def job_atualizar_dados_pagamento(self):
        """
        Job que executa a rotina de atualização de dados de pagamento da Rede.
        Busca os pagamentos do dia anterior para as empresas configuradas.
        """
        logger.info("Iniciando job de atualização de dados de pagamento.")
        
        company_numbers_str = os.getenv("COMPANY_NUMBERS")
        if not company_numbers_str:
            logger.error("Variável de ambiente COMPANY_NUMBERS não configurada. O job não será executado.")
            return

        try:
            company_numbers = [int(cn.strip()) for cn in company_numbers_str.split(',')]
        except ValueError:
            logger.error(f"Valor inválido para COMPANY_NUMBERS: '{company_numbers_str}'. Deve ser uma lista de números separados por vírgula.")
            return
        
        # A rotina é executada para o dia anterior.
        yesterday = date.today() - timedelta(days=1)
        start_date = yesterday
        end_date = yesterday

        rotina = RotinaService()

        for company_number in company_numbers:
            logger.info(f"Processando pagamentos para a empresa {company_number} para o período de {start_date} a {end_date}.")
            try:
                result = rotina.atualizar_dados_pagamento(
                    companyNumber=company_number,
                    startDate=start_date,
                    endDate=end_date
                )
                if result.get("sucesso"):
                    logger.info(f"Sucesso ao atualizar pagamentos para a empresa {company_number}.")
                else:
                    logger.error(f"Falha ao atualizar pagamentos para a empresa {company_number}: {result.get('mensagem')}")
            except Exception as e:
                logger.error(f"Erro inesperado ao processar empresa {company_number}: {e}", exc_info=True)

        logger.info("Job de atualização de dados de pagamento finalizado.")

        return True


    def inicializar_tarefas(self):
        """
        Inicia o agendador de tarefas (scheduler).
        """

        executors = {
            "default": ThreadPoolExecutor(1)
        }

        job_defaults = {
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 3600
        }

        self.scheduler = BackgroundScheduler(
            executors=executors,
            job_defaults=job_defaults,
            timezone="America/Sao_Paulo"
        )

        self.scheduler.add_job(
            self.job_atualizar_dados_pagamento,
            trigger="cron",
            hour=1,
            minute=0,
            id="job_atualizar_dados_pagamento",
            replace_existing=True
        )

        return True