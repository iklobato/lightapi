import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

class Database:
    def __init__(self):
        self._engine = None
        self._session_factory = None
        self.Base = declarative_base()

    @property
    def engine(self):
        if not self._engine:
            db_url = os.getenv('DATABASE_URL', 'sqlite:///:memory:')
            
            engine_args = {
                'echo': bool(os.getenv('DB_ECHO', False)),
                'connect_args': {'check_same_thread': False} if 'sqlite' in db_url else {}
            }

            if not db_url.startswith('sqlite'):
                engine_args.update({
                    'poolclass': QueuePool,
                    'pool_size': int(os.getenv('DB_POOL_SIZE', 5)),
                    'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', 10)),
                    'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', 3600)),
                    'pool_pre_ping': True
                })
            else:
                if '::memory:' in db_url:
                    engine_args['poolclass'] = StaticPool

            self._engine = create_engine(db_url, **engine_args)
            
        return self._engine

    @property
    def session_factory(self):
        if not self._session_factory:
            self._session_factory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False
            )
        return self._session_factory

    def create_session(self):
        return self.session_factory()

database = Database()
Base = database.Base
