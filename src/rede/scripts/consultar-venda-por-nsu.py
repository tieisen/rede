import os, sys, asyncio, requests

from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rede.services.rede import AutenticacaoService as Auth

async def consultar_vendas_por_nsu():
    auth = Auth()
    token: str = auth.logar()['access_token']
    company_number = os.getenv("COMPANY_NUMBER_LIST")

    # sales_url = f"{os.getenv('URL_SP')}/v1/sales/{company_number}/daily?startDate=2026-07-29&endDate=2026-08-31&nsu=376505085"
    payments_url = f"{os.getenv('URL_SP')}/v1/payments/credit-orders?parentCompanyNumber={company_number}&subsidiaries={company_number}&startDate=2026-08-31&endDate=2026-08-31"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    request = requests.get(payments_url, headers=headers)

    if request.status_code == 200:
        print("Consulta realizada com sucesso!")
        print(request.json())


if __name__ == "__main__":
    asyncio.run(consultar_vendas_por_nsu())