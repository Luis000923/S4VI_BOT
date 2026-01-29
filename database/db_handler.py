# db_handler.py - Gestión de base de datos SQLite
import sqlite3
import datetime
import os

class DatabaseHandler:
    def __init__(self, db_path="database/bot.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

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
                    reminders_active INTEGER DEFAULT 1
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

            # Migración: Agregar columna reminders_active si no existe
            try:
                cursor.execute('ALTER TABLE tasks ADD COLUMN reminders_active INTEGER DEFAULT 1')
            except sqlite3.OperationalError:
                pass  # La columna ya existe o la tabla es nueva y ya la tiene
            
            conn.commit()

    # Registrar una nueva tarea en la base de datos
    def add_task(self, subject, title, due_date, created_by, guild_id, message_id=None, channel_id=None, reminders_active=1):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO tasks (subject, title, due_date, created_by, guild_id, message_id, channel_id, reminders_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                           (subject, title, due_date, created_by, guild_id, message_id, channel_id, reminders_active))
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
    def update_task(self, task_id, title=None, due_date=None, subject=None):
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

    # Marcar un recordatorio como enviado
    def mark_reminder_sent(self, task_id, reminder_type):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO sent_reminders (task_id, reminder_type) VALUES (?, ?)', (task_id, reminder_type))
            conn.commit()
