"""Redefinicao local de senha do Evidencia+, sem exclusao de dados."""
import getpass
from pathlib import Path
from sqlalchemy.exc import SQLAlchemyError
from app.database import DATA_DIR, SessionLocal, engine
from app.models import User, AppSession, AppSession
from app.security import hash_password


def reset_password(email: str, new_password: str) -> bool:
    """Atualiza somente a senha do usuario existente. Nunca recria banco/atividades."""
    if len(new_password) < 12:
        raise ValueError('A senha deve ter no minimo 12 caracteres.')
    with SessionLocal() as db:
        user = db.query(User).filter(User.email.ilike(email.strip())).first()
        if user is None:
            return False
        user.password_hash = hash_password(new_password)
        db.query(AppSession).filter_by(user_id=user.id).delete()
        db.query(AppSession).filter_by(user_id=user.id).delete()
        db.commit()
    # O arquivo inicial pode conter senha antiga e passa a ser enganoso.
    initial_file = DATA_DIR / 'ACESSO_INICIAL.txt'
    if initial_file.exists():
        initial_file.unlink()
    return True


def main():
    print('\nEVIDENCIA+ | Redefinicao local de acesso')
    if engine.dialect.name == 'sqlite':
        db_path = Path(engine.url.database)
        if not db_path.exists():
            print('Banco de dados nao encontrado:', db_path)
            print('Primeiro execute INICIAR_WINDOWS.bat para criar a instalacao.')
            return 1
        print('Banco de dados:', db_path)
    try:
        with SessionLocal() as db:
            users = db.query(User).order_by(User.email).all()
    except SQLAlchemyError as exc:
        print('Erro ao consultar usuarios. Confira o banco e a configuracao DATABASE_URL.')
        print(type(exc).__name__)
        return 1
    if not users:
        print('Nenhum usuario cadastrado neste banco. Inicie a plataforma primeiro.')
        return 1
    print('Usuarios cadastrados:')
    for user in users:
        print('  ',user.email)
    email = users[0].email if len(users)==1 else input('E-mail a redefinir: ').strip()
    if not any(u.email.casefold() == email.casefold() for u in users):
        print('E-mail nao encontrado neste banco.')
        return 1
    print('Redefinindo a senha do usuario:', email)
    print('A senha digitada nao sera exibida.')
    pw = getpass.getpass('Nova senha (minimo 12 caracteres): ')
    check = getpass.getpass('Confirme a nova senha: ')
    if pw != check:
        print('As senhas nao coincidem. Nenhuma alteracao realizada.')
        return 1
    try:
        if not reset_password(email, pw):
            print('Usuario nao encontrado. Nenhuma alteracao realizada.')
            return 1
    except ValueError as exc:
        print(exc)
        return 1
    print('\nSenha atualizada no banco. Nenhuma atividade ou foto foi apagada.')
    print('Login:', email)
    print('Use a nova senha informada neste procedimento.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
