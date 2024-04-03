import src.models.commons as model


class Users(model.Base):
    """
    User Table
    """
    __tablename__: str = "users"
    id: int  = model.sql.Column(model.sql.Integer, primary_key=True, autoincrement=True)
    name: str = model.sql.Column(model.sql.String, nullable=False, unique=True)
    email: str = model.sql.Column(model.sql.String, nullable=False, unique=True)
    birthday: str = model.sql.Column(model.sql.Date, nullable=True)
    gender: str = model.sql.Column(model.sql.String, nullable=True)
    profile_picture_url: str = model.sql.Column(model.sql.String, nullable=True)

    token = model.sql_orm.relationship(
        "Tokens", back_populates="user", uselist=False, passive_deletes=True)
