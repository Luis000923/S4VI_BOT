from flask import Flask
from threading import Thread

# Crea el servidor web sencillo
app = Flask('')

@app.route('/')
def home():
    return "Bot en linea!"

def run():
    # El bot corre en el puerto 8080 (comun para estos servicios)
    app.run(host='0.0.0.0', port=8080)

# Funcion para que el bot no se apague nunca
def keep_alive():
    t = Thread(target=run)
    t.start()
