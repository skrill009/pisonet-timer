"""
Shared message protocol between parent and child apps.
All messages are JSON over TCP, newline-delimited.
"""
import json

# Commands parent -> child
CMD_ADD_TIME      = "ADD_TIME"      # {"cmd":"ADD_TIME","seconds":int}
CMD_SET_TIME      = "SET_TIME"      # {"cmd":"SET_TIME","seconds":int}
CMD_END_SESSION   = "END_SESSION"   # {"cmd":"END_SESSION"}
CMD_GET_STATUS    = "GET_STATUS"    # {"cmd":"GET_STATUS"}
CMD_SHUTDOWN      = "SHUTDOWN"      # {"cmd":"SHUTDOWN"}
CMD_SEND_MESSAGE  = "SEND_MESSAGE"  # {"cmd":"SEND_MESSAGE","message":str,"title":str}
CMD_SET_SCHEDULE  = "SET_SCHEDULE"  # {"cmd":"SET_SCHEDULE","enabled":bool,"opening_hours":str,"closing_hours":str,"warning_minutes":int,"warning_message":str}

# Commands child -> parent
CMD_HEARTBEAT     = "HEARTBEAT"     # {"cmd":"HEARTBEAT","pc_name":str,"ip":str,"port":int,"status":dict}

# User sync commands (child <-> parent)
CMD_SAVE_USER     = "SAVE_USER"     # {"cmd":"SAVE_USER","username":str,"seconds":int,"pc_name":str}
CMD_LOAD_USER     = "LOAD_USER"     # {"cmd":"LOAD_USER","username":str,"pc_name":str}
CMD_REGISTER_USER = "REGISTER_USER" # {"cmd":"REGISTER_USER","username":str,"password":str}
CMD_LOGIN_USER    = "LOGIN_USER"    # {"cmd":"LOGIN_USER","username":str,"password":str}

# Responses
RESP_STATUS = "STATUS"
RESP_OK     = "OK"
RESP_ERROR  = "ERROR"
RESP_USER   = "USER"   # {"type":"USER","seconds":int,"username":str}

def encode(obj: dict) -> bytes:
    return (json.dumps(obj) + "\n").encode("utf-8")

def decode(data: bytes) -> dict:
    return json.loads(data.decode("utf-8").strip())
