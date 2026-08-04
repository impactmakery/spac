def test_record_audit_persists_row(db):
    from app.models import AuditLog, Municipality, User
    from app.services.audit import record_audit

    muni = Municipality(name="M")
    actor = User(email="a@x.org", role="system_admin", status="active")
    db.add_all([muni, actor])
    db.commit()

    record_audit(
        db,
        actor_id=actor.id,
        action="municipality.rename",
        entity_type="municipality",
        entity_id=str(muni.id),
        before={"name": "M"},
        after={"name": "N"},
    )
    db.commit()

    row = db.query(AuditLog).one()
    assert row.actor_id == actor.id
    assert row.action == "municipality.rename"
    assert row.before == {"name": "M"} and row.after == {"name": "N"}
