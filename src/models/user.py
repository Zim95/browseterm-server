from sqlalchemy.orm.decl_api import DeclarativeMeta
from sqlalchemy.orm.session import Session
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


class UsersModelOps(model.BasicModelOps):

    def __init__(
        self,
        model: model.decl.DeclarativeMeta,
        session: model.sql_orm.Session
    ) -> None:
        super().__init__(model, session)

    def insert_or_update_user(
        self,
        user_info: dict,
        return_record: bool=False
    ) -> None | model.decl.DeclarativeMeta:
        try:
            record: model.decl.DeclarativeMeta = self.find(
                find_dict={"name": user_info.get("name", "")})
            if not record:
                # insert
                result: None | model.decl.DeclarativeMeta = self.insert(
                    insert_dict=user_info,
                    return_record=return_record
                )
                return result
            else:
                # update
                self.update(
                    find_dict={"id": record.id},
                    update_dict=user_info
                )
                return record if return_record else None
        except Exception as e:
            raise Exception(e)

