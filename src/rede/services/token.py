from datetime import datetime
from sqlalchemy.orm import Session
from src.rede.database.models import Token

class TokenService:

    def __init__(self, db: Session):
        self.db = db 
        
    def salvarToken(
        self,
        sistema: str,
        accessToken: str,
        expiresAt: datetime | None = None,
    ):

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
        return (
            self.db.query(Token)
            .filter(Token.sistema == sistema)
            .first()
        )