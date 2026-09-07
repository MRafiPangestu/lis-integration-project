import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.integration.instruments import (
    InstrumentConfigError,
    resolve_instrument_id,
)
from app.models import Instrument
from app.models.base import Base


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine, tables=[Instrument.__table__])
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


def test_exactly_one_match_returns_id(session):
    session.add(Instrument(nama_mesin="Mindray BC-5150"))
    session.commit()

    resolved = resolve_instrument_id(session, "Mindray BC-5150")

    assert resolved == session.query(Instrument).one().id_instrument


def test_zero_matches_fails_clearly(session):
    with pytest.raises(InstrumentConfigError) as exc:
        resolve_instrument_id(session, "Sysmex XN-550")
    assert "No instrument row" in str(exc.value)
    assert "Sysmex XN-550" in str(exc.value)


def test_duplicate_nama_mesin_fails_clearly(session):
    session.add_all([Instrument(nama_mesin="Dup"), Instrument(nama_mesin="Dup")])
    session.commit()

    with pytest.raises(InstrumentConfigError) as exc:
        resolve_instrument_id(session, "Dup")
    assert "ambiguous" in str(exc.value)
