"""
Corre este script UNA VEZ por cada canal que quieras automatizar.

Uso:
    python authorize.py "NombreDelCanal"

Va a abrir tu navegador para que inicies sesion con la cuenta de
Google dueña de ese canal y apruebes los permisos. El token queda
guardado en credentials/token_<nombre>.pickle y se reutiliza despues
automaticamente en cada ejecucion del worker (no hay que repetir esto
salvo que revoques el acceso manualmente desde tu cuenta de Google).
"""

import sys
from youtube_api import autorizar_canal

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('Uso: python authorize.py "NombreDelCanal"')
        print(
            "El nombre debe coincidir EXACTO con el campo 'nombre' "
            "que pusiste para ese canal en el panel web."
        )
        sys.exit(1)

    canal_nombre = sys.argv[1]
    print(f"Autorizando canal: {canal_nombre}")
    print("Se va a abrir tu navegador. Inicia sesion con la cuenta de Google")
    print("dueña de ESE canal especifico y acepta los permisos solicitados.\n")

    autorizar_canal(canal_nombre)
    print("\nListo. Ya puedes correr el worker normalmente.")