from datetime import datetime
from sqlalchemy.orm import Session
from src.rede.database.models import Token

class TokenService:

    def __init__(self, db: Session):
        self.db = db 
        
    def salvar_token(
        self,
        sistema: str,
        access_token: str,
        refresh_token: str | None = None,
        expires_at: datetime | None = None,
    ):

        token = (
            self.db.query(Token)
            .filter(Token.sistema == sistema)
            .first()
        )

        if token:
            token.access_token = access_token
            token.refresh_token = refresh_token
            token.expires_at = expires_at
        else:
            token = Token(
                sistema=sistema,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
            )
            self.db.add(token)

        self.db.commit()
        self.db.refresh(token)
        return token
    
    def obter_token(self, sistema: str) -> Token | None:
        return (
            self.db.query(Token)
            .filter(Token.sistema == sistema)
            .first()
        )