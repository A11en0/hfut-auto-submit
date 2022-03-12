#!/usr/bin/env python
# coding: utf-8

from Crypto.Cipher import AES
from requests.exceptions import HTTPError
import requests
import base64
import time
import json
from datetime import datetime, timedelta, timezone
import smtplib
from email.mime.text import MIMEText
import yaml


def printLog(text: str) -> None:
    """Print log

    Print log with date and time and update last log,
    For example:

    #>>> printLog('test')
    [21-01-18 08:08:08]: test

    """
    global lastLog
    print(f'[{"%.2d-%.2d-%.2d %.2d:%.2d:%.2d" % time.localtime()[:6]}]: {text}')
    lastLog = text


# 加载配置文件
def getYmlConfig(yaml_file='config.yml'):
    file = open(yaml_file, 'r', encoding="utf-8")
    file_data = file.read()
    file.close()
    config = yaml.load(file_data, Loader=yaml.FullLoader)

    return dict(config)


def encryptPassword(password: str, key: str) -> str:
    """Encrypt password

    Encrypt the password in ECB mode, PKCS7 padding, then Base64 encode the password

    Args:
      password:
        The password to encrypt
      key:
        The encrypt key for encryption

    Return:
      encryptedPassword:
        Encrypted password

    """
    # add padding
    blockSize = len(key)
    padAmount = blockSize - len(password) % blockSize
    padding = chr(padAmount) * padAmount
    encryptedPassword = password + padding

    # encrypt password in ECB mode
    aesEncryptor = AES.new(key.encode('utf-8'), AES.MODE_ECB)
    encryptedPassword = aesEncryptor.encrypt(encryptedPassword.encode('utf-8'))

    # base64 encode
    encryptedPassword = base64.b64encode(encryptedPassword)

    return encryptedPassword.decode('utf-8')


def login(username: str, password: str, requestSession) -> bool:
    """Log in to cas of HFUT

    Try to log in with username and password. Login operation contains many jumps,
    there may be some unhandled problems, FUCK HFUT!

    Args:
      username:
        Username for HFUT account
      password:
        Password for HFUT account

    Return:
      True if logged in successfully

    Raises:
      HTTPError: When you are unlucky

    """
    # get cookie: SESSION
    ignore = requestSession.get('https://cas.hfut.edu.cn/cas/login')
    ignore.raise_for_status()

    # get cookie: JSESSIONID
    ignore = requestSession.get('https://cas.hfut.edu.cn/cas/vercode')
    ignore.raise_for_status()

    # get encryption key
    timeInMillisecond = round(time.time() * 10000)
    responseForKey = requestSession.get(
        url='https://cas.hfut.edu.cn/cas/checkInitVercode',
        params={'_': timeInMillisecond})
    responseForKey.raise_for_status()

    encryptionKey = responseForKey.cookies['LOGIN_FLAVORING']

    # check if verification code is required
    if responseForKey.json():
        printLog('需要验证码，过一会再试试吧。')
        return False

    # try to login
    encryptedPassword = encryptPassword(password, encryptionKey)
    checkIdResponse = requestSession.get(
        url='https://cas.hfut.edu.cn/cas/policy/checkUserIdenty',
        params={'_': (timeInMillisecond + 1), 'username': username, 'password': encryptedPassword})
    checkIdResponse.raise_for_status()

    checkIdResponseJson = checkIdResponse.json()
    if checkIdResponseJson['msg'] != 'success':
        # login failed
        if checkIdResponseJson['data']['mailRequired'] or checkIdResponseJson['data']['phoneRequired']:
            # the problem may be solved manually
            printLog('需要进行手机或邮箱认证，移步: https://cas.hfut.edu.cn/')
            return False
        printLog(f'处理checkUserIdenty时出现错误：{checkIdResponseJson["msg"]}')
        return False
    requestSession.headers.update({'Content-Type': 'application/x-www-form-urlencoded'})

    loginResponse = requestSession.post(
        url='https://cas.hfut.edu.cn/cas/login',
        data={
            'username': username,
            'capcha': '',
            'execution': 'e1s1',
            '_eventId': 'submit',
            'password': encryptedPassword,
            'geolocation': "",
            'submit': "登录"
        })
    loginResponse.raise_for_status()

    requestSession.headers.pop('Content-Type')
    if 'cas协议登录成功跳转页面。' not in loginResponse.text:
        # log in failed
        printLog('登录失败')
        return False
    # log in success
    printLog('登录成功')
    return True


def submit(location: str, requestSession) -> bool:
    """Submit using specific location

    submit today's form based on the form submitted last time using specific loaction

    Return:
      True if submitted successfully

    Args:
      location:
        Specify location information instead of mobile phone positioning

    Raises:
      HTTPError: Shit happens

    """
    ignore = requestSession.get(
        url='http://stu.hfut.edu.cn/xsfw/sys/swmxsyqxxsjapp/*default/index.do'
    )
    ignore.raise_for_status()

    requestSession.headers.update({
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest'
    })
    ignore = requestSession.post(
        url='http://stu.hfut.edu.cn/xsfw/sys/emapfunauth/welcomeAutoIndex.do'
    )
    ignore.raise_for_status()

    requestSession.headers.pop('Content-Type')
    requestSession.headers.pop('X-Requested-With')
    ignore = requestSession.get(
        url='http://stu.hfut.edu.cn/xsfw/sys/emapfunauth/casValidate.do',
        params={
            'service': '/xsfw/sys/swmjbxxapp/*default/index.do'
        }
    )
    ignore.raise_for_status()

    requestSession.headers.update({
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'http://stu.hfut.edu.cn/xsfw/sys/swmjbxxapp/*default/index.do'
    })
    ignore = requestSession.get(
        url='http://stu.hfut.edu.cn/xsfw/sys/emappagelog/config/swmxsyqxxsjapp.do'
    )
    ignore.raise_for_status()

    # get role config
    requestSession.headers.pop('X-Requested-With')
    requestSession.headers.update({
        'Content-Type': 'application/x-www-form-urlencoded'
    })
    configData = {
        'data': json.dumps({
            'APPID': '5811260348942403',
            'APPNAME': 'swmxsyqxxsjapp'
        })
    }
    roleConfigResponse = requestSession.post(
        url='http://stu.hfut.edu.cn/xsfw/sys/swpubapp/MobileCommon/getSelRoleConfig.do',
        data=configData
    )
    roleConfigResponse.raise_for_status()

    roleConfigJson = roleConfigResponse.json()
    if roleConfigJson['code'] != '0':
        # :(
        printLog(f'处理roleConfig时发生错误：{roleConfigJson["msg"]}')
        return False

    # get menu info
    menuInfoResponse = requestSession.post(
        url='http://stu.hfut.edu.cn/xsfw/sys/swpubapp/MobileCommon/getMenuInfo.do',
        data=configData
    )
    menuInfoResponse.raise_for_status()

    menuInfoJson = menuInfoResponse.json()

    if menuInfoJson['code'] != '0':
        # :(
        printLog(f'处理menuInfo时发生错误：{menuInfoJson["msg"]}')
        return False

    # get setting... for what?
    requestSession.headers.pop('Content-Type')
    settingResponse = requestSession.get(
        url='http://stu.hfut.edu.cn/xsfw/sys/swmxsyqxxsjapp/modules/mrbpa/getSetting.do',
        data={'data': ''}
    )
    settingResponse.raise_for_status()

    settingJson = settingResponse.json()

    # get the form submitted last time
    requestSession.headers.update({
        'Content-Type': 'application/x-www-form-urlencoded'
    })
    todayDateStr = "%.2d-%.2d-%.2d" % time.localtime()[:3]
    lastSubmittedResponse = requestSession.post(
        url='http://stu.hfut.edu.cn/xsfw/sys/swmxsyqxxsjapp/modules/mrbpa/getStuXx.do',
        data={'data': json.dumps({'TBSJ': todayDateStr})}
    )
    lastSubmittedResponse.raise_for_status()

    lastSubmittedJson = lastSubmittedResponse.json()

    if lastSubmittedJson['code'] != '0':
        # something wrong with the form submitted last time
        printLog('上次填报提交的信息出现了问题，本次最好手动填报提交。')
        return False

    # generate today's form to submit
    submitDataToday = lastSubmittedJson['data']
    submitDataToday.update({
        'BY1': '1',
        'DFHTJHBSJ': '',
        'DZ_SFSB': '1',
        'DZ_TBDZ': location,
        'GCJSRQ': '',
        'GCKSRQ': '',
        'TBSJ': todayDateStr
    })

    # try to submit
    submitResponse = requestSession.post(
        url='http://stu.hfut.edu.cn/xsfw/sys/swmxsyqxxsjapp/modules/mrbpa/saveStuXx.do',
        data={'data': json.dumps(submitDataToday)}
    )
    submitResponse.raise_for_status()

    submitResponseJson = submitResponse.json()

    if submitResponseJson['code'] != '0':
        # failed
        printLog(f'提交时出现错误：{submitResponseJson["msg"]}')
        return False

    # succeeded
    printLog('提交成功')
    requestSession.headers.pop('Referer')
    requestSession.headers.pop('Content-Type')
    return True


emailConfig = getYmlConfig()['Email']

# 可使用邮箱自动
mail_host = emailConfig['server']
# 163用户名
mail_user = emailConfig['name']
# 密码(部分邮箱为授权码)
mail_pass = emailConfig['password']
# 邮件发送方邮箱地址
sender = emailConfig['account']


def sendMessage(receiver, msg):
    if receiver != '':
        # 邮件内容设置
        message = MIMEText(msg, 'plain', 'utf-8')
        # 邮件主题
        message['Subject'] = '%s.%s疫情信息收集结果' % (datetime.now().month, datetime.now().day)
        # 发送方信息
        message['From'] = sender
        # 接受方信息
        message['To'] = receiver
        receivers = [receiver]
        try:
            smtpObj = smtplib.SMTP()

            # 连接到服务器
            smtpObj.connect(mail_host, 25)
            # 登录到服务器
            smtpObj.login(mail_user, mail_pass)
            # 发送
            smtpObj.sendmail(
                sender, receivers, message.as_string())
            time.sleep(5)
            # 退出
            smtpObj.quit()
            printLog('发送邮件通知成功')
        except smtplib.SMTPException as e:
            printLog('发送邮件通知失败')


def main_handler(event, context):
    userConfig = getYmlConfig()['users']
    lastLog = ''
    for i in userConfig[:]:
        # create a new session
        requestSession = requests.session()
        requestSession.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9'
        })

        printLog(f'开始处理用户{i["user"]["username"]}')
        try:
            # login and submit
            if login(i['user']['username'], i['user']['password'], requestSession):
                if submit(i['user']['location'], requestSession):
                    # succeed
                    if i['user']['email']:
                        # has SCKEY, send success prompt
                        sendMessage(i['user']['email'], '今日校园疫情信息收集填报成功')
                        pass
                    printLog('当前用户处理成功')
                else:
                    # failed
                    if i['user']['email']:
                        # has SCKEY, send success prompt
                        sendMessage(i['user']['email'], '打卡失败，请手动打卡')
                        pass
                    printLog('发生错误，终止当前用户的处理')
            else:
                printLog('当前用户密码错误')
        except HTTPError as httpError:
            if i['user']['email']:
                # has SCKEY, send success prompt
                sendMessage(i['user']['email'], '打卡失败，请手动打卡')
                pass
            print(f'发生HTTP错误：{httpError}，终止当前用户的处理')
            # process next user
            continue
        time.sleep(1)
    printLog('所有用户处理结束')


if __name__ == '__main__':
    main_handler({}, {})