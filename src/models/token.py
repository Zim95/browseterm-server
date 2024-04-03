import src.models.commons as model


class Token(model.Base):
    """
    Token Model
    """
    __tablename__: str = "token"
    id: int  = model.sql.Column(model.sql.Integer, primary_key=True, autoincrement=True)
    access_token: str = model.sql.Column(model.sql.String, nullable=False)
    id_token: str = model.sql.Column(model.sql.String, nullable=False)
    expires_in: str = model.sql.Column(model.sql.Integer, nullable=False)
    expires_at: str = model.sql.Column(model.sql.Integer, nullable=False)
    token_type: str = model.sql.Column(model.sql.String, nullable=False)

    user = model.sql_orm.relationship(
        "User", back_populates="token"
    )
