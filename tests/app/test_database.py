def test_db_exists(db):
    assert len(db.get_all()) == 2

    results = db.get_by_query(lambda data: data["original"] == "Sncf")
    assert len(results) == 1

    key = list(results.keys())[0]
    assert results[key]["original"] == "Sncf"
    assert results[key]["adjusted"] == "SNCF"
