def test_database_creates_tables(test_model, db_engine):
    assert db_engine.has_table(test_model.__tablename__)

def test_session_crud_operations(test_model, db_session):
    # Create
    new_item = test_model(name="Test Item")
    db_session.add(new_item)
    db_session.commit()
    
    # Read
    item = db_session.get(test_model, 1)
    assert item.name == "Test Item"
    
    # Update
    item.name = "Updated Item"
    db_session.commit()
    updated_item = db_session.get(test_model, 1)
    assert updated_item.name == "Updated Item"
    
    # Delete
    db_session.delete(updated_item)
    db_session.commit()
    assert db_session.get(test_model, 1) is None
