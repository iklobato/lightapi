from lightapi.pagination import Paginator
from sqlalchemy import select

def test_paginator_limits_results(test_model, db_session):
    # Setup
    db_session.bulk_save_objects([test_model(name=f"Item {i}") for i in range(1, 21)])
    db_session.commit()
    
    # Test
    paginator = Paginator(limit=5)
    query = select(test_model).order_by(test_model.id)
    results = db_session.scalars(paginator.paginate(query)).all()
    
    # Assert
    assert len(results) == 5
    assert [item.name for item in results] == ["Item 1", "Item 2", "Item 3", "Item 4", "Item 5"]

def test_paginator_respects_offset(test_model, db_session):
    # Setup
    db_session.bulk_save_objects([test_model(name=f"Item {i}") for i in range(1, 21)])
    db_session.commit()
    
    # Test
    paginator = Paginator(limit=5, offset=10)
    query = select(test_model).order_by(test_model.id)
    results = db_session.scalars(paginator.paginate(query)).all()
    
    # Assert
    assert len(results) == 5
    assert results[0].name == "Item 11"

