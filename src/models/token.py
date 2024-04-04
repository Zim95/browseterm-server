import src.models.commons as model


class Tokens(model.Base):
    """
    Token Model
    """
    __tablename__: str = "tokens"
    id: int  = model.sql.Column(model.sql.Integer, primary_key=True, autoincrement=True)
    access_token: str = model.sql.Column(model.sql.String, nullable=False)
    id_token: str = model.sql.Column(model.sql.String, nullable=False)
    expires_in: str = model.sql.Column(model.sql.Integer, nullable=False)
    expires_at: str = model.sql.Column(model.sql.Integer, nullable=False)
    token_type: str = model.sql.Column(model.sql.String, nullable=False)
    user_id: int = model.sql.Column(
        model.sql.Integer,
        model.sql.ForeignKey(
            "users.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True,
        unique=True
    )

    user = model.sql_orm.relationship(
        "Users", back_populates="token"
    )


class TokensModelOps(model.BasicModelOps):

    def __init__(
        self,
        model: model.decl.DeclarativeMeta,
        session: model.sql_orm.Session
    ) -> None:
        super().__init__(model, session)

    def insert_or_update_token(self, user_id: int, token_info: dict) -> None:
        try:
            record: model.decl.DeclarativeMeta = self.find(
                find_dict={"user_id": user_id}
            )
            if record:
                self.update(
                    find_dict={"user_id": user_id},
                    update_dict=token_info
                )
            else:
                token_info["user_id"] = user_id
                self.insert(**token_info)
        except Exception as e:
            raise Exception(e)
