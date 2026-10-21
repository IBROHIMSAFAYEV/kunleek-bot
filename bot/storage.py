"""aiogram FSM holatini bazada saqlash: webhook rejimida har so'rov alohida jarayonda bo'lishi mumkin."""
from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from asgiref.sync import sync_to_async

from .models import FSMRecord


def _key(key: StorageKey):
    return ":".join(str(getattr(key, f, None)) for f in (
        "bot_id", "chat_id", "user_id", "thread_id", "business_connection_id", "destiny",
    ))


class DBStorage(BaseStorage):
    async def set_state(self, key, state=None):
        value = state.state if isinstance(state, State) else state
        await sync_to_async(FSMRecord.objects.update_or_create)(key=_key(key), defaults={"state": value})

    async def get_state(self, key):
        rec = await sync_to_async(FSMRecord.objects.filter(key=_key(key)).first)()
        return rec.state if rec else None

    async def set_data(self, key, data):
        await sync_to_async(FSMRecord.objects.update_or_create)(key=_key(key), defaults={"data": dict(data)})

    async def get_data(self, key):
        rec = await sync_to_async(FSMRecord.objects.filter(key=_key(key)).first)()
        return dict(rec.data) if rec else {}

    async def close(self):
        pass
