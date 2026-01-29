import sqlite3
import datetime
import os

# Clase para manejar la base de datos
class DatabaseHandler:
    def __init__(self, db_path="database/bot.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    # Crea las tablas si no existen
    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Tabla de tareas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    title TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    created_by INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    message_id INTEGER,
                    channel_id INTEGER
                )
            ''')
            
            # Quien esta en que materia
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS enrollments (
                    user_id INTEGER NOT NULL,
                    subject TEXT NOT NULL,
                    guild_id INTEGER NOT NULL,
                    PRIMARY KEY (user_id, subject, guild_id)
                )
            ''')
            
            # Tareas ya entregadas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS deliveries (
                    task_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    delivery_date TEXT NOT NULL,
                    guild_id INTEGER NOT NULL,
                    PRIMARY KEY (task_id, user_id)
                )
            ''')
            
            # Para no repetir recordatorios
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sent_reminders (
                    task_id INTEGER NOT NULL,
                    reminder_type TEXT NOT NULL,
                    PRIMARY KEY (task_id, reminder_type)
                )
            ''')
            conn.commit()

    # Guarda una tarea nueva
    def add_task(self, subject, title, due_date, created_by, guild_id, message_id=None, channel_id=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO tasks (subject, title, due_date, created_by, guild_id, message_id, channel_id) VALUES (?, ?, ?, ?, ?, ?, ?)',
                           (subject, title, due_date, created_by, guild_id, message_id, channel_id))
            conn.commit()
            return cursor.lastrowid

    # Saca todas las tareas de un servidor
    def get_tasks(self, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tasks WHERE guild_id = ?', (guild_id,))
            return cursor.fetchall()

    # Busca una tarea por su ID
    def get_task_by_id(self, task_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
            return cursor.fetchone()

    # Borra la tarea y todo lo relacionado
    def delete_task(self, task_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
            cursor.execute('DELETE FROM sent_reminders WHERE task_id = ?', (task_id,))
            cursor.execute('DELETE FROM deliveries WHERE task_id = ?', (task_id,))
            
            # Si ya no quedan tareas, reiniciamos el contador a 1
            cursor.execute('SELECT COUNT(*) FROM tasks')
            if cursor.fetchone()[0] == 0:
                cursor.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'tasks'")
                
            conn.commit()

    # Inscribe a un usuario en materias
    def set_enrollments(self, user_id, subjects, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM enrollments WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
            for subject in subjects:
                cursor.execute('INSERT INTO enrollments (user_id, subject, guild_id) VALUES (?, ?, ?)',
                               (user_id, subject.strip(), guild_id))
            conn.commit()

    # Ve en que esta inscrito alguien
    def get_user_enrollments(self, user_id, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT subject FROM enrollments WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
            return [row[0] for row in cursor.fetchall()]

    # Mira si alguien debe recibir avisos de una materia
    def is_user_enrolled_in_subject(self, user_id, subject, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM enrollments WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
            has_enrollments = cursor.fetchone()
            if not has_enrollments:
                return True # Si no se ha inscrito a nada, recibe todo por defecto
            
            cursor.execute('SELECT 1 FROM enrollments WHERE user_id = ? AND subject = ? AND guild_id = ?', 
                           (user_id, subject, guild_id))
            return cursor.fetchone() is not None

    # Marca que alguien ya entrego
    def mark_as_delivered(self, task_id, user_id, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('INSERT OR REPLACE INTO deliveries (task_id, user_id, delivery_date, guild_id) VALUES (?, ?, ?, ?)',
                           (task_id, user_id, now, guild_id))
            conn.commit()

    # Ve si ya entrego
    def is_delivered(self, task_id, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM deliveries WHERE task_id = ? AND user_id = ?', (task_id, user_id))
            return cursor.fetchone() is not None

    # Mira si ya se mando un recordatorio
    def is_reminder_sent(self, task_id, reminder_type):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM sent_reminders WHERE task_id = ? AND reminder_type = ?', (task_id, reminder_type))
            return cursor.fetchone() is not None

    # Marca el recordatorio como enviado
    def mark_reminder_sent(self, task_id, reminder_type):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO sent_reminders (task_id, reminder_type) VALUES (?, ?)', (task_id, reminder_type))
            conn.commit()
