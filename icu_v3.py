# -*- coding: utf-8 -*-
# v3
# pip install requests beautifulsoup4 pyDes
import json
import os
import random
from configparser import ConfigParser
from datetime import datetime, timedelta
from time import sleep

import requests
from bs4 import BeautifulSoup
from pyDes import ECB, PAD_PKCS5, des


def getEnv(env, default="", required=False):
    if os.path.exists("config.ini"):
        config = ConfigParser()
        config.read("config.ini", encoding="utf-8")
        if config.has_option("CONFIG", env):
            return config["CONFIG"][env]
    if os.environ.get(env):
        return os.getenv(env)
    if required:
        raise Exception(f"Env {env} is required")
    return default



debug = getEnv("DEBUG", False)
username = getEnv("CAS_USERNAME", required=True)
password = getEnv("CAS_PASSWORD", required=True)



swos = "swos.ncu.edu.cn"
cas = "cas.ncu.edu.cn"
tpName = getEnv("")  # "https://{swos}/cs/star3/origin/" + tpName
time = datetime.now()
loginUrl = f"https://{cas}:8443/cas/login?service=https%3A%2F%2F{swos}%2Fsfrz%2Flogin219271"
authorize = f"https://{swos}/auth/connect/oauth2/authorize?appid=a8bb28edf51747e79b93bdcd57073683&redirect_uri=https%3A%2F%2F{swos}%2Fmobile%2F%23%2Flogin%3Fredirect%3D%2FroomCheck%2Flocation%26mappId%3D8913718%26appId%3Da8bb28edf51747e79b93bdcd57073683%26appKey%3Dqpd14k0dVSEb3u1B&response_type=code&scope=snsapi_base&state=219271"
ydLoginUrl = f"https://{swos}/pedestal/user/ydLogin?"
getStudentInfoUrl = f"https://{swos}/housemaster/sg/roomCheckPunch/getStudentInfo?cqfs=1"
clockInUrl = f"https://{swos}/housemaster/sg/roomCheckPunch/clockIn"
getStudentRecordUrl = f"https://{swos}/housemaster/sg/roomCheckStatisticsYD/getStudentRecord?cqksrq={time.date()-timedelta(days=7)}&cqjsrq={time.date()}"

session = requests.Session()
headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/120.0 Mobile/15E148 Safari/605.1.15",
    "connection": "close",
}
session.headers.update(headers)



def log(level, msg):
    if debug and level == "DEBUG":
        print(f"[{datetime.now()}] [DEBUG]: {msg}")
    else:
        print(f"[{datetime.now()}] [{level}]: {msg}")


def getXToken(username, password):
    response = session.get(loginUrl)
    soup = BeautifulSoup(response.text, "html.parser")

    data = {
        "username": username,
        "password": password,
        "rememberMe": False,
        "captcha": soup.find("input", {"name": "captcha"}).get("value"),
        "currentMenu": soup.find("input", {"name": "currentMenu"}).get("value"),
        "failN": soup.find("input", {"name": "failN"}).get("value"),
        "mfaState": soup.find("input", {"name": "mfaState"}).get("value"),
        "execution": soup.find("input", {"name": "execution"}).get("value"),
        "_eventId": soup.find("input", {"name": "_eventId"}).get("value"),
        "geolocation": soup.find("input", {"name": "geolocation"}).get("value"),
        "submit": soup.find("input", {"name": "submit"}).get("value"),
    }

    response = session.post(loginUrl, data=data)
    response = session.get(authorize, allow_redirects=False)
    log("DEBUG", f"authorize：{response.status_code}")
    location = response.headers.get("Location")
    log("DEBUG", location)

    session.headers.update({"Referer": f"https://{swos}/mobile/"})
    response = session.get(ydLoginUrl + location.split("?")[1].replace("/", "%2F"))
    log("DEBUG", response.text)

    return response.json()["data"]["token"]


def encode(plainText):
    return (
        des(b"QRCODENC", ECB, pad=None, padmode=PAD_PKCS5)
        .encrypt(plainText.encode("utf-8"))
        .hex()
    )


def clockIn():
    if tpName == "":
        raise Exception("tpName is empty")

    response = session.get(getStudentInfoUrl)
    log("DEBUG", response.text)

    if not response.json()["success"]:
        raise Exception("Get student info failed：" + response.json()["message"])

    data = response.json()["data"]
    if "result" in data and "sj" in data["result"]:
        print(f"[{datetime.now()}][INFO]: Already clocked in")
        return
    if data["batch"] is None:
        raise Exception("No batch")

    batch = data["batch"]
    rawJsonStr = {
        "jg": "1",
        "sj": f"{time.strftime('%Y-%m-%d %H:%M:%S')}",
        "rq": f"{time.date()}",
        "pcId": batch["id"],
        "ldId": batch["ldId"],
        "cwId": batch["cwId"],
        "xsId": batch["xsId"],
        "cqfs": "1",
        "tp": {
            "name": tpName,
            "url": f"https://{swos}/cs/star3/origin/{tpName}",
            "type": "jpg",
        },
    }

    jsonStr = encode(json.dumps(rawJsonStr, separators=(",", ":")))
    log("DEBUG", jsonStr)

    response = session.post(clockInUrl, headers=headers, json={"jsonStr": jsonStr})
    log("DEBUG", response.text)
    data = response.json()["data"]
    if "result" in data and "sj" in data["result"]:
        log("INFO", "Clock in successfully")
    else:
        log("ERROR", "Clock in failed!!!")


def getStudentRecord():
    response = session.get(getStudentRecordUrl)
    tp = response.json()["data"]["list"][-2]["tp"]
    log("DEBUG", tp)
    if tp is None:
        raise Exception("tp is None!!")
    return json.loads(tp)["name"]


if __name__ == "__main__":
    log("INFO", "BEGIN")
    random.seed()
    seconds = random.randint(5, 60) + random.random()
    log("INFO", f"Random Sleep {seconds}s")
    sleep(seconds)
    session.headers.update({"X-Token": getXToken(username, password)})
    if tpName == "":
        tpName = getStudentRecord()
    clockIn()
    log("INFO", "END")
