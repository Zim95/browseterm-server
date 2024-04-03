# builtins
import typing

# third party
import sqlalchemy as sql
import sqlalchemy.orm as sql_orm
import sqlalchemy.orm.decl_api as decl

# modules
import os


# postgres settings
psql_dialect: str = os.environ.get("PSQL_DIALECT")
psql_driver: str = os.environ.get("PSQL_DRIVER")
psql_username: str = os.environ.get("PSQL_USERNAME")
psql_password: str = os.environ.get("PSQL_PASSWORD")
psql_host: str = os.environ.get("PSQL_HOST")
psql_port: str = os.environ.get("PSQL_PORT")
psql_database: str = os.environ.get("PSQL_DATABASE")
# psql connection string
psql_connection_string: str = (
    f"{psql_dialect}+{psql_driver}://"
    f"{psql_username}:{psql_password}@{psql_host}:{psql_port}/{psql_database}"
)

# engine
engine: sql.engine.base.Engine = sql.create_engine(psql_connection_string)
# base
Base: decl.DeclarativeMeta = sql_orm.declarative_base()
# session
session: sql_orm.session.Session = sql_orm.Session(engine)


class BasicModelOps:
    """
    Basic Model operations.
    Does not deal with advanced queries: like matches or joins.
    Basic CRUD only supported.
    """

    def __init__(self, model: decl.DeclarativeMeta, session: sql_orm.session.Session) -> None:
        self.model: decl.DeclarativeMeta = model
        self.session: sql_orm.session.Session = session

    def insert(self, insert_dict: dict) -> None:
        try:
            record: decl.DeclarativeMeta = self.model(**insert_dict)
            self.session.add(record)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise Exception(e)

    def insert_many(self, insert_dicts: list[dict]) -> None:
        try:
            for insert_dict in insert_dicts:
                record: decl.DeclarativeMeta = self.model(**insert_dict)
                self.session.add(record)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise Exception(e)
    
    def find(self, find_dict: dict={}, format_dict=False) -> typing.Union[decl.DeclarativeMeta, dict]:
        record: decl.DeclarativeMeta = self.session.query(self.model).filter_by(
            **find_dict).first()
        if format_dict:
            return record.__dict__
        return record

    def find_many(self, find_dict: dict={}, format_dict=False) -> list[typing.Union[decl.DeclarativeMeta, dict]]:
        records: list[sql_orm.decl_api.DeclarativeMeta] = self.session.query(self.model).filter_by(
            **find_dict).all()
        if format_dict:
            return [r.__dict__ for r in records]
        return records

    def delete(self, find_dict: dict={}) -> None:
        try:
            record: decl.DeclarativeMeta = self.find(find_dict)
            self.session.delete(record)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise Exception(e)
    
    def delete_many(self, find_dict: dict={}) -> None:
        try:
            records: list[decl.DeclarativeMeta] = self.find_many(find_dict)
            for record in records:
                self.session.delete(record)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise Exception(e)
