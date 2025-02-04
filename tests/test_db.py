from sqlalchemy import inspect


def test_database_creates_tables(test_model, db_session, db_engine):
    inspector = inspect(db_engine)
    assert inspector.has_table(test_model.__tablename__)

def test_session_crud_operations(test_model, db_session):
    new_item = test_model(name="Test Item")
    db_session.add(new_item)
    db_session.commit()
    
    item = db_session.get(test_model, 1)
    assert item.name == "Test Item"
    
    item.name = "Updated Item"
    db_session.commit()
    updated_item = db_session.get(test_model, 1)
    assert updated_item.name == "Updated Item"
    
    db_session.delete(updated_item)
    db_session.commit()
    assert db_session.get(test_model, 1) is None
