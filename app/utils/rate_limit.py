from collections import defaultdict, deque
from datetime import datetime, timedelta


_export_rate_limit = defaultdict(deque)


def verificar_rate_limit_export(chave, limite=10, janela_segundos=60):
    agora = datetime.now()
    janela = timedelta(seconds=janela_segundos)

    acessos = _export_rate_limit[chave]

    while acessos and agora - acessos[0] > janela:
        acessos.popleft()

    if len(acessos) >= limite:
        return False

    acessos.append(agora)
    return True