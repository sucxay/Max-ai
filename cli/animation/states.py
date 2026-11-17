from enum import Enum


class MascotState(str, Enum):
    IDLE = "IDLE"
    WATCHING = "WATCHING"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    EXECUTING = "EXECUTING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    SLEEPING = "SLEEPING"
