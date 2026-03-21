from database.db_handler import DatabaseHandler


def test_add_task_and_fetch_by_id(tmp_path):
    db_file = tmp_path / "bot.db"
    db = DatabaseHandler(str(db_file))

    task_id = db.add_task("Matemática", "Guía 1", "18/03/2026 12:00", 100, 200)
    task = db.get_task_by_id(task_id)

    assert task is not None
    assert task[0] == task_id
    assert task[1] == "Matemática"
    assert task[2] == "Guía 1"


def test_update_task_partial_keeps_other_fields(tmp_path):
    db_file = tmp_path / "bot.db"
    db = DatabaseHandler(str(db_file))

    task_id = db.add_task("Matemática", "Guía 1", "18/03/2026 12:00", 100, 200)
    updated = db.update_task(task_id, title="Guía 1 - Actualizada")
    task = db.get_task_by_id(task_id)

    assert updated is True
    assert task[2] == "Guía 1 - Actualizada"
    assert task[3] == "18/03/2026 12:00"


def test_mark_reminder_sent_is_idempotent_with_unique_constraint(tmp_path):
    db_file = tmp_path / "bot.db"
    db = DatabaseHandler(str(db_file))

    task_id = db.add_task("Ética", "Foro", "19/03/2026 18:00", 100, 200)
    db.mark_reminder_sent(task_id, "24h")

    try:
        db.mark_reminder_sent(task_id, "24h")
    except Exception:
        pass

    reminders = db.get_sent_reminders_for_tasks([task_id])
    assert (task_id, "24h") in reminders


def test_enrollment_snapshot_and_delivered_pairs(tmp_path):
    db_file = tmp_path / "bot.db"
    db = DatabaseHandler(str(db_file))

    guild_id = 999
    db.set_enrollments(1, ["Matemática", "Ética"], guild_id)
    db.set_enrollments(2, ["Matemática"], guild_id)

    task_id = db.add_task("Matemática", "Laboratorio", "20/03/2026 10:00", 100, guild_id)
    db.mark_as_delivered(task_id, 2, guild_id)

    snapshot = db.get_enrollment_snapshot(guild_id)
    delivered = db.get_delivered_pairs_for_tasks(guild_id, [task_id])

    assert snapshot["subjects_by_user"][1] == {"Matemática", "Ética"}
    assert snapshot["subjects_by_user"][2] == {"Matemática"}
    assert (task_id, 2) in delivered
