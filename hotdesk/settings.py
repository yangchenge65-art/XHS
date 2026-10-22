"""User-scoped Windows DPAPI for local API credentials; never store plain keys."""
import base64
import ctypes
import json
import os
import threading
from decimal import Decimal, InvalidOperation
from pathlib import Path


def windows_crypt(value, decrypt=False):
    if os.name != 'nt':
        raise ValueError('本机密钥保存仅支持 Windows；其他系统请使用 HOTDESK_OPENAI_API_KEY 环境变量')
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]

    raw = base64.b64decode(value, validate=True) if decrypt else value.encode('utf-8')
    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    result = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        function = crypt.CryptUnprotectData
        function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    else:
        function = crypt.CryptProtectData
        function.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise ValueError('Windows 密钥保护失败，请在当前 Windows 用户下重新配置')
    try:
        data = ctypes.string_at(result.pbData, result.cbData)
        return data.decode('utf-8') if decrypt else base64.b64encode(data).decode('ascii')
    finally:
        kernel.LocalFree(ctypes.cast(result.pbData, ctypes.c_void_p))


class Settings:
    def __init__(self, data_dir, environ=None, protect=None, unprotect=None):
        self.path = Path(data_dir) / 'openai-settings.json'
        self.environ = os.environ if environ is None else environ
        self.protect = protect or windows_crypt
        self.unprotect = unprotect or (lambda value: windows_crypt(value, decrypt=True))
        self.lock = threading.RLock()

    def read(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def key(self):
        cipher = self.read().get('api_key_encrypted')
        if cipher:
            try:
                return self.unprotect(cipher)
            except (ValueError, OSError):
                return ''
        return self.environ.get('HOTDESK_OPENAI_API_KEY', '')

    def cost(self):
        return str(self.read().get('cost') or self.environ.get('HOTDESK_GPT_COST_CNY', ''))

    def engine(self):
        return 'openai' if self.read().get('engine') == 'openai' else 'codex'

    def public(self):
        return dict(configured=bool(self.key()), model='gpt-5.1', cost=self.cost(),
                    engine=self.engine(),
                    local_save_supported=os.name == 'nt',
                    note='使用独立计费的 OpenAI API key；不是 ChatGPT 登录或订阅授权。')

    def save(self, api_key=None, cost=None, clear=False, engine=None):
        with self.lock:
            data = self.read()
            if engine is not None:
                if engine not in ('codex', 'openai'):
                    raise ValueError('不支持的调用方式')
                data['engine'] = engine
            if cost is not None:
                try:
                    amount = Decimal(str(cost))
                    if not amount.is_finite() or not 0 < amount <= 30:
                        raise ValueError()
                except (InvalidOperation, ValueError):
                    raise ValueError('单次预留金额须大于 0 且不超过 30 元') from None
                data['cost'] = str(amount)
            if clear:
                data.pop('api_key_encrypted', None)
            elif api_key:
                if not isinstance(api_key, str) or len(api_key) > 512 or any(c.isspace() for c in api_key):
                    raise ValueError('API key 格式无效')
                data['api_key_encrypted'] = self.protect(api_key)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix('.tmp')
            temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            os.replace(temp, self.path)
            return self.public()
