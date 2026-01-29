# keep_alive.py - Servidor Flask para mantener el bot activo
from flask import Flask
from threading import Thread

# Aplicación Flask para el monitoreo
app = Flask('')

@app.route('/')
def home():
    return "El bot está en línea."

def run():
    # Ejecutar el servidor web en el puerto 8080 o en el host especificado
    app.run(host='0.0.0.0', port=8080)

# Inicializar un hilo separado para ejecutar el servidor web
def keep_alive():
    t = Thread(target=run)
    t.start()
