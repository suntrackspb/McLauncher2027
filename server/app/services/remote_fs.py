"""Доступ к файлам игрового сервера: FTP/FTPS (хостинг с панелью) и SFTP
(свой сервер по SSH) за одним интерфейсом.

Код синхронный (ftplib/paramiko) — из async-роутов вызывается через
asyncio.to_thread. Пути — POSIX, относительные от корня сервера.
"""

import ftplib
import io
import posixpath
import socket
from dataclasses import dataclass

import paramiko
import paramiko.sftp

TIMEOUT = 20


class RemoteError(Exception):
    pass


@dataclass
class RemoteEntry:
    name: str
    is_dir: bool
    size: int


@dataclass
class ConnectionParams:
    protocol: str  # ftp / ftps / sftp
    host: str
    port: int
    username: str
    password: str | None
    private_key: str | None
    host_key: str | None
    server_dir: str


class RemoteFS:
    """Базовый интерфейс. Все пути — относительно server_dir."""

    def __init__(self, root: str):
        self._root = root.rstrip("/") or "/"

    def _abs(self, path: str) -> str:
        return posixpath.join(self._root, path) if path else self._root

    def list_dir(self, path: str) -> list[RemoteEntry]:
        raise NotImplementedError

    def read(self, path: str) -> bytes:
        raise NotImplementedError

    def write(self, path: str, content: bytes) -> None:
        raise NotImplementedError

    def rename(self, src: str, dst: str) -> None:
        raise NotImplementedError

    def mkdirs(self, path: str) -> None:
        raise NotImplementedError

    def exists(self, path: str) -> bool:
        parent, name = posixpath.split(path)
        try:
            return any(e.name == name for e in self.list_dir(parent))
        except RemoteError:
            return False

    def close(self) -> None:
        pass

    # Для SFTP после первого подключения — чтобы запомнить ключ хоста.
    host_key: str | None = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FtpFS(RemoteFS):
    def __init__(self, params: ConnectionParams):
        super().__init__(params.server_dir)
        ftp = ftplib.FTP_TLS(timeout=TIMEOUT) if params.protocol == "ftps" else ftplib.FTP(timeout=TIMEOUT)
        try:
            ftp.connect(params.host, params.port)
            ftp.login(params.username, params.password or "")
            if isinstance(ftp, ftplib.FTP_TLS):
                ftp.prot_p()
        except (OSError, ftplib.Error) as exc:
            raise RemoteError(f"FTP: не удалось подключиться: {exc}") from exc
        self._ftp = ftp

    def _call(self, fn, *args):
        try:
            return fn(*args)
        except (OSError, ftplib.Error) as exc:
            raise RemoteError(f"FTP: {exc}") from exc

    def list_dir(self, path: str) -> list[RemoteEntry]:
        target = self._abs(path)
        try:
            return [
                RemoteEntry(name, facts.get("type") == "dir", int(facts.get("size", 0) or 0))
                for name, facts in self._ftp.mlsd(target, facts=["type", "size"])
                if facts.get("type") in ("file", "dir")
            ]
        except ftplib.error_perm as exc:
            if not str(exc).startswith("500") and not str(exc).startswith("502"):
                raise RemoteError(f"FTP: {target}: {exc}") from exc
        except (OSError, ftplib.Error) as exc:
            raise RemoteError(f"FTP: {target}: {exc}") from exc
        # Старые серверы без MLSD: NLST + SIZE (папка, если SIZE не отвечает).
        entries = []
        for full in self._call(self._ftp.nlst, target):
            name = posixpath.basename(full.rstrip("/"))
            if name in (".", ".."):
                continue
            try:
                self._ftp.voidcmd("TYPE I")
                size = self._ftp.size(posixpath.join(target, name))
                entries.append(RemoteEntry(name, False, size or 0))
            except ftplib.error_perm:
                entries.append(RemoteEntry(name, True, 0))
        return entries

    def read(self, path: str) -> bytes:
        buf = io.BytesIO()
        self._call(self._ftp.retrbinary, f"RETR {self._abs(path)}", buf.write)
        return buf.getvalue()

    def write(self, path: str, content: bytes) -> None:
        self._call(self._ftp.storbinary, f"STOR {self._abs(path)}", io.BytesIO(content))

    def rename(self, src: str, dst: str) -> None:
        self._call(self._ftp.rename, self._abs(src), self._abs(dst))

    def mkdirs(self, path: str) -> None:
        current = ""
        for part in path.split("/"):
            if not part:
                continue
            current = posixpath.join(current, part)
            try:
                self._ftp.mkd(self._abs(current))
            except ftplib.error_perm:
                pass  # уже есть
            except (OSError, ftplib.Error) as exc:
                raise RemoteError(f"FTP: {exc}") from exc

    def close(self) -> None:
        try:
            self._ftp.quit()
        except (OSError, ftplib.Error):
            self._ftp.close()


def _load_private_key(text: str) -> paramiko.PKey:
    for cls in (paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.RSAKey):
        try:
            return cls.from_private_key(io.StringIO(text))
        except (paramiko.SSHException, ValueError):
            continue
    raise RemoteError("SSH: не удалось прочитать приватный ключ (нужен OpenSSH/PEM без пароля)")


class _PinnedHostKey(paramiko.MissingHostKeyPolicy):
    """Trust on first use: без сохранённого ключа принимаем и запоминаем,
    с сохранённым — требуем совпадения."""

    def __init__(self, expected: str | None):
        self.expected = expected
        self.seen: str | None = None

    def missing_host_key(self, client, hostname, key):
        self.seen = f"{key.get_name()} {key.get_base64()}"
        if self.expected and self.expected != self.seen:
            raise RemoteError(
                "SSH: ключ сервера изменился! Если сервер переустановлен — сбросьте ключ в настройках подключения."
            )


class SftpFS(RemoteFS):
    def __init__(self, params: ConnectionParams):
        super().__init__(params.server_dir)
        client = paramiko.SSHClient()
        policy = _PinnedHostKey(params.host_key)
        client.set_missing_host_key_policy(policy)
        pkey = _load_private_key(params.private_key) if params.private_key else None
        try:
            client.connect(
                params.host,
                port=params.port,
                username=params.username,
                password=params.password or None,
                pkey=pkey,
                timeout=TIMEOUT,
                allow_agent=False,
                look_for_keys=False,
            )
            self._sftp = client.open_sftp()
        except RemoteError:
            client.close()
            raise
        except paramiko.sftp.SFTPError as exc:
            client.close()
            # Типично: у пользователя shell nologin, и sshd вместо SFTP отдаёт
            # текст "This account is currently not available".
            raise RemoteError(
                "SSH: подключились, но SFTP не запустился. Если у пользователя shell nologin — "
                "включите для него internal-sftp (Match User … ForceCommand internal-sftp) в sshd_config"
            ) from exc
        except (OSError, socket.error, paramiko.SSHException) as exc:
            client.close()
            raise RemoteError(f"SSH: не удалось подключиться: {exc}") from exc
        self._client = client
        self.host_key = policy.seen or params.host_key

    def _call(self, fn, *args):
        try:
            return fn(*args)
        except (OSError, paramiko.SSHException, paramiko.sftp.SFTPError) as exc:
            raise RemoteError(f"SFTP: {args[0] if args else ''}: {exc}") from exc

    def list_dir(self, path: str) -> list[RemoteEntry]:
        import stat

        return [
            RemoteEntry(a.filename, stat.S_ISDIR(a.st_mode or 0), a.st_size or 0)
            for a in self._call(self._sftp.listdir_attr, self._abs(path))
        ]

    def read(self, path: str) -> bytes:
        buf = io.BytesIO()
        self._call(self._sftp.getfo, self._abs(path), buf)
        return buf.getvalue()

    def write(self, path: str, content: bytes) -> None:
        self._call(self._sftp.putfo, io.BytesIO(content), self._abs(path))

    def rename(self, src: str, dst: str) -> None:
        self._call(self._sftp.posix_rename, self._abs(src), self._abs(dst))

    def mkdirs(self, path: str) -> None:
        current = ""
        for part in path.split("/"):
            if not part:
                continue
            current = posixpath.join(current, part)
            try:
                self._sftp.stat(self._abs(current))
            except FileNotFoundError:
                self._call(self._sftp.mkdir, self._abs(current))

    def close(self) -> None:
        self._client.close()


def open_remote(params: ConnectionParams) -> RemoteFS:
    if params.protocol in ("ftp", "ftps"):
        return FtpFS(params)
    if params.protocol == "sftp":
        return SftpFS(params)
    raise RemoteError(f"Неизвестный протокол: {params.protocol}")
