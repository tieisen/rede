from datetime import datetime
from sqlalchemy.orm import Session
from src.rede.database.models import Token

class TokenService:

    def __init__(self, db: Session):
        """
            Parametros:
                db: sessão do SQLAlchemy
        """

        self.db = db 
        
    def salvarToken(
        self,
        sistema: str,
        accessToken: str,
        expiresAt: datetime | None = None,
    ):
        """
            Grava o token do sistema na tabela tokens.
            Atualiza a linha se o sistema já existir, senão cria uma nova.

            Parametros:
                sistema: 'rede' | 'sankhya'
                accessToken: token de acesso
                expiresAt?: data/hora de expiração

            Retorno: registro Token salvo
        """

        token = (
            self.db.query(Token)
            .filter(Token.sistema == sistema)
            .first()
        )

        if token:
            token.access_token = accessToken
            token.expires_at = expiresAt
        else:
            token = Token(
                sistema=sistema,
                access_token=accessToken,
                expires_at=expiresAt,
            )
            self.db.add(token)

        self.db.commit()
        self.db.refresh(token)
        return token
    
    def obterToken(self, sistema: str) -> Token | None:
        """
            Busca o token salvo de um sistema.

            Parametros:
                sistema: 'rede' | 'sankhya'

            Retorno: registro Token ou None se não existir
        """

        return (
            self.db.query(Token)
            .filter(Token.sistema == sistema)
            .first()
        )