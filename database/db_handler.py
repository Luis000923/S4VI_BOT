# db_handler.py - Gestión de base de datos SQLite
import sqlite3
import datetime

class DatabaseHandler:
    def __init__(self, db_path="database/bot.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=10000")
        except sqlite3.OperationalError:
            pass
        return conn

    # Inicializar las tablas de la base de datos si no existen
    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Definición de la tabla de tareas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    title TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    created_by INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    message_id INTEGER,
                    channel_id INTEGER,
                    reminders_active INTEGER DEFAULT 1,
                    source_url TEXT
                )
            ''')

            # Tabla para rastrear todos los mensajes relacionados con una tarea (anuncios, notificaciones, etc.)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS task_messages (
                    task_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks (id)
                )
            ''')
            
            # Mapeo de inscripciones de usuarios por materia
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS enrollments (
                    user_id INTEGER NOT NULL,
                    subject TEXT NOT NULL,
                    guild_id INTEGER NOT NULL,
                    PRIMARY KEY (user_id, subject, guild_id)
                )
            ''')
            
            # Seguimiento de entregas de tareas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS deliveries (
                    task_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    delivery_date TEXT NOT NULL,
                    guild_id INTEGER NOT NULL,
                    PRIMARY KEY (task_id, user_id)
                )
            ''')
            
            # Seguimiento de recordatorios enviados para evitar duplicados
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sent_reminders (
                    task_id INTEGER NOT NULL,
                    reminder_type TEXT NOT NULL,
                    PRIMARY KEY (task_id, reminder_type)
                )
            ''')

            # Registro de actividades detectadas en cursos virtuales (evita duplicados por hash)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS course_watch_items (
                    item_hash TEXT PRIMARY KEY,
                    course_name TEXT NOT NULL,
                    week_name TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    guild_id INTEGER NOT NULL,
                    first_seen TEXT NOT NULL
                )
            ''')

            # Contador diario global para comandos sensibles (rate limiting persistente)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_command_usage (
                    command_key TEXT NOT NULL,
                    usage_day TEXT NOT NULL,
                    usage_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (command_key, usage_day)
                )
            ''')

            # Migración: Agregar columna reminders_active si no existe
            try:
                cursor.execute('ALTER TABLE tasks ADD COLUMN reminders_active INTEGER DEFAULT 1')
            except sqlite3.OperationalError:
                pass  # La columna ya existe o la tabla es nueva y ya la tiene

            # Migración: Agregar columna source_url si no existe
            try:
                cursor.execute('ALTER TABLE tasks ADD COLUMN source_url TEXT')
            except sqlite3.OperationalError:
                pass

            # Índices para optimizar consultas frecuentes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_guild_id ON tasks (guild_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_task_messages_task_id ON task_messages (task_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_enrollments_guild_user ON enrollments (guild_id, user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_enrollments_guild_subject ON enrollments (guild_id, subject)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_deliveries_guild_task_user ON deliveries (guild_id, task_id, user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_course_watch_items_guild ON course_watch_items (guild_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_command_usage_day ON daily_command_usage (usage_day)')
            
            conn.commit()

    # Registrar una nueva tarea en la base de datos
    def add_task(self, subject, title, due_date, created_by, guild_id, message_id=None, channel_id=None, reminders_active=1, source_url=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO tasks (subject, title, due_date, created_by, guild_id, message_id, channel_id, reminders_active, source_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (subject, title, due_date, created_by, guild_id, message_id, channel_id, reminders_active, source_url),
            )
            conn.commit()
            return cursor.lastrowid

    # Registrar un mensaje asociado a una tarea
    def add_task_message(self, task_id, channel_id, message_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO task_messages (task_id, channel_id, message_id) VALUES (?, ?, ?)',
                           (task_id, channel_id, message_id))
            conn.commit()

    # Obtener todos los mensajes asociados a una tarea
    def get_task_messages(self, task_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT channel_id, message_id FROM task_messages WHERE task_id = ?', (task_id,))
            return cursor.fetchall()

    # Actualizar los atributos de una tarea existente
    def update_task(self, task_id, title=None, due_date=None, subject=None, source_url=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            if title:
                updates.append("title = ?")
                params.append(title)
            if due_date:
                updates.append("due_date = ?")
                params.append(due_date)
            if subject:
                updates.append("subject = ?")
                params.append(subject)
            if source_url is not None:
                updates.append("source_url = ?")
                params.append(source_url)
            
            if not updates:
                return False
                
            params.append(task_id)
            query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0

    # Obtener todas las tareas de un servidor específico
    def get_tasks(self, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tasks WHERE guild_id = ?', (guild_id,))
            return cursor.fetchall()

    # Obtener una sola tarea por su ID único
    def get_task_by_id(self, task_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
            return cursor.fetchone()

    # Eliminar una tarea y todos los registros asociados
    def delete_task(self, task_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
            cursor.execute('DELETE FROM sent_reminders WHERE task_id = ?', (task_id,))
            cursor.execute('DELETE FROM deliveries WHERE task_id = ?', (task_id,))
            cursor.execute('DELETE FROM task_messages WHERE task_id = ?', (task_id,))
            
            # Reiniciar la secuencia de autoincremento si no quedan tareas
            cursor.execute('SELECT COUNT(*) FROM tasks')
            if cursor.fetchone()[0] == 0:
                cursor.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'tasks'")
                
            conn.commit()

    # Administrar inscripciones de materias para usuarios
    def set_enrollments(self, user_id, subjects, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM enrollments WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
            for subject in subjects:
                cursor.execute('INSERT INTO enrollments (user_id, subject, guild_id) VALUES (?, ?, ?)',
                               (user_id, subject.strip(), guild_id))
            conn.commit()

    # Obtener las materias inscritas por un usuario específico
    def get_user_enrollments(self, user_id, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT subject FROM enrollments WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
            return [row[0] for row in cursor.fetchall()]

    # Snapshot de inscripciones para evaluación masiva en recordatorios
    def get_enrollment_snapshot(self, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, subject FROM enrollments WHERE guild_id = ?', (guild_id,))
            rows = cursor.fetchall()

        users_with_enrollments = set()
        subjects_by_user = {}
        for user_id, subject in rows:
            users_with_enrollments.add(user_id)
            subjects_by_user.setdefault(user_id, set()).add(subject)

        return {
            "users_with_enrollments": users_with_enrollments,
            "subjects_by_user": subjects_by_user,
        }

    # Entregas por tareas para evitar consultas repetidas por usuario
    def get_delivered_pairs_for_tasks(self, guild_id, task_ids):
        if not task_ids:
            return set()

        placeholders = ','.join('?' for _ in task_ids)
        query = f'SELECT task_id, user_id FROM deliveries WHERE guild_id = ? AND task_id IN ({placeholders})'

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, [guild_id, *task_ids])
            rows = cursor.fetchall()

        return {(task_id, user_id) for task_id, user_id in rows}

    # Verificar si un usuario está inscrito en una materia específica
    def is_user_enrolled_in_subject(self, user_id, subject, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM enrollments WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
            has_enrollments = cursor.fetchone()
            if not has_enrollments:
                # Por defecto es verdadero si el usuario no tiene inscripciones registradas
                return True 
            
            cursor.execute('SELECT 1 FROM enrollments WHERE user_id = ? AND subject = ? AND guild_id = ?', 
                           (user_id, subject, guild_id))
            return cursor.fetchone() is not None

    # Marcar una tarea como entregada para un usuario específico
    def mark_as_delivered(self, task_id, user_id, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('INSERT OR REPLACE INTO deliveries (task_id, user_id, delivery_date, guild_id) VALUES (?, ?, ?, ?)',
                           (task_id, user_id, now, guild_id))
            conn.commit()

    # Determinar si un usuario ha entregado una tarea específica
    def is_delivered(self, task_id, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM deliveries WHERE task_id = ? AND user_id = ?', (task_id, user_id))
            return cursor.fetchone() is not None

    # Verificar si ya se ha enviado un tipo específico de recordatorio
    def is_reminder_sent(self, task_id, reminder_type):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM sent_reminders WHERE task_id = ? AND reminder_type = ?', (task_id, reminder_type))
            return cursor.fetchone() is not None

    # Obtener recordatorios ya enviados para un conjunto de tareas
    def get_sent_reminders_for_tasks(self, task_ids):
        if not task_ids:
            return set()

        placeholders = ','.join('?' for _ in task_ids)
        query = f'SELECT task_id, reminder_type FROM sent_reminders WHERE task_id IN ({placeholders})'

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, task_ids)
            rows = cursor.fetchall()

        return {(task_id, reminder_type) for task_id, reminder_type in rows}

    # Marcar un recordatorio como enviado
    def mark_reminder_sent(self, task_id, reminder_type):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO sent_reminders (task_id, reminder_type) VALUES (?, ?)', (task_id, reminder_type))
            conn.commit()

    # Guardar actividad detectada por el monitor de cursos (si no existe previamente)
    def add_course_watch_item(self, item_hash, course_name, week_name, activity_type, title, url, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            first_seen = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                '''
                INSERT OR IGNORE INTO course_watch_items
                (item_hash, course_name, week_name, activity_type, title, url, guild_id, first_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (item_hash, course_name, week_name, activity_type, title, url, guild_id, first_seen)
            )
            conn.commit()
            return cursor.rowcount > 0

    # Obtener el uso diario de un comando global
    def get_daily_command_usage(self, command_key, usage_day):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT usage_count FROM daily_command_usage WHERE command_key = ? AND usage_day = ?',
                (command_key, usage_day),
            )
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    # Incrementar el contador diario de un comando global
    def increment_daily_command_usage(self, command_key, usage_day):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO daily_command_usage (command_key, usage_day, usage_count)
                VALUES (?, ?, 1)
                ON CONFLICT(command_key, usage_day)
                DO UPDATE SET usage_count = usage_count + 1
                ''',
                (command_key, usage_day),
            )
            conn.commit()
