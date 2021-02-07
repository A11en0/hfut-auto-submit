# -*- coding: utf-8 -*-
import sys
import requests
import json
import yaml
from datetime import datetime, timedelta, timezone
from urllib3.exceptions import InsecureRequestWarning
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

# debug模式
debug = False
if debug:
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


headers = {
        'Connection': 'keep-alive',
        'Accept': '*/*',
        'DNT': '1',
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 4.4.4; OPPO R11 Plus Build/KTU84P) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/33.0.0.0 Safari/537.36 yiban/8.1.11 cpdaily/8.1.11 wisedu/8.1.11',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': 'http://stu.hfut.edu.cn',
        'Referer': 'http://stu.hfut.edu.cn/xsfw/sys/xsyqxxsjapp/*default/index.do',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
}

# 读取yml配置
def getYmlConfig(yaml_file='config.yml'):
    file = open(yaml_file, 'r', encoding="utf-8")
    file_data = file.read()
    file.close()
    config = yaml.load(file_data, Loader=yaml.FullLoader)
    return dict(config)

# 全局配置
config = getYmlConfig(yaml_file='config.yml')

# 获取当前utc时间，并格式化为北京时间
def getTimeStr():
    utc_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
    bj_dt = utc_dt.astimezone(timezone(timedelta(hours=8)))
    return bj_dt.strftime("%Y-%m-%d %H:%M:%S")


# 输出调试信息，并及时刷新缓冲区
def log(content):
    print(getTimeStr() + ' ' + str(content))
    sys.stdout.flush()


# 登陆并返回session
def getSession(user, loginUrl):
    user = user['user']
    params = {
        'login_url': loginUrl,
        # 保证学工号和密码正确下面两项就不需要配置
        'needcaptcha_url': '',
        'captcha_url': '',
        'username': user['username'],
        'password': user['password']
    }

    cookies = {}
    # 借助上一个项目开放出来的登陆API，模拟登陆
    res = requests.post(config['login']['api'], params, verify=not debug)
    cookieStr = str(res.json()['cookies'])
    log("Cookie: " + cookieStr)

    if cookieStr == 'None':
        log(res.json())
        return None

    # 解析cookie
    for line in cookieStr.split(';'):
        name, value = line.strip().split('=', 1)
        cookies[name] = value
    session = requests.session()
    session.cookies = requests.utils.cookiejar_from_dict(cookies)

    # 获取疫情填报App
    appconfig_url = 'http://stu.hfut.edu.cn/xsfw/sys/swpubapp/indexmenu/getAppConfig.do?appId=5811258723206966&appName=xsyqxxsjapp'
    res = session.get(appconfig_url)
    session.cookies.set("_WEU", dict(res.cookies)["_WEU"])
    return session


# 查询表单
def queryForm(session, apis):
    # 获取服务器当前时间
    getDate_url = 'http://stu.hfut.edu.cn/xsfw/sys/xsyqxxsjapp/mrbpa/getDateTime.do'
    res = session.post(getDate_url, headers=headers, data="")
    dqrq = res.json()['data']["DQRQ"]
    info = {
        'TBSJ': '%s' % dqrq
    }
    # hasFilled = False

    # 判断是否已经填报
    checkFilled_url = 'http://stu.hfut.edu.cn/xsfw/sys/xsyqxxsjapp/mrbpa/checkFilled.do'
    res = session.post(checkFilled_url, headers=headers, data={'data': '%s' % info})
    if len(res.json()['data']):
        # hasFilled = True
        log("已填报.")
        # log("已填报，请勿重复填报!")
        # exit(-1)

    # 基本信息表单，保存下来用于后续提交
    getjbxx_url = 'http://stu.hfut.edu.cn/xsfw/sys/xsyqxxsjapp/mrbpa/getJbxx.do'
    res = session.post(getjbxx_url, headers=headers, data="data={}")
    jbxx = res.json()['data']
    # WID参数用于查询`mrqkbd.do`表单内容，暂未用到
    # WID = res.json()["data"]["WID"]
    # print(jbxx)

    # 每日报平安表单，保存下来用于后续提交
    mrbpabd_url = 'http://stu.hfut.edu.cn/xsfw/sys/xsyqxxsjapp/modules/mrbpa/mrbpabd.do'
    res = session.post(mrbpabd_url, headers=headers, data="")
    mrbpabd = res.json()['datas']['mrbpabd']['rows'][0] # 基本信息表单
    if mrbpabd["LXDH"] == None:
        log("请至少在APP中填报一次，才能开始自动填报！")
        exit(-1)
    # print(mrbpabd)

    # 获取最新表单中的内容，保存下来用于后续提交
    getZxpaxx_url = 'http://stu.hfut.edu.cn/xsfw/sys/xsyqxxsjapp/mrbpa/getZxpaxx.do'
    res = session.post(getZxpaxx_url, headers=headers, data="data={}")
    getZxpaxx = res.json()['data']
    # print(getZxpaxx)

    # if hasFilled:
    #     getZxpaxx_url = 'http://stu.hfut.edu.cn/xsfw/sys/xsyqxxsjapp/mrbpa/getZxpaxx.do'
    #     res = session.post(getZxpaxx_url, headers=headers, data="data={}")
    #     getZxpaxx = res.json()['data']
    #     print(getZxpaxx)
    #
    # else:
    #     # 已填报，直接查看`每日情况`表单
    #     mrqkbd_url = 'http://stu.hfut.edu.cn/xsfw/sys/xsyqxxsjapp/modules/mrbpa/mrqkbd.do'
    #     res = session.post(mrqkbd_url, headers=headers, data={"WID": WID})
    #     mrqk = res.json()['datas']['mrqkbd']['rows'][0]
    #     # bug，传空值，返回所有数据
    #     # res = session.post(mrqkbd_url, headers=headers, data="")
    #     # print(len(res.json()))
    #     # mrqk = res.json()['datas']['mrqkbd']['rows']

    # 偷懒做法，直接俄合并三个查询表单，下一步中填充使用
    form = {**getZxpaxx, **jbxx, **mrbpabd}

    # 替换None值为空字符
    for k, v in form.items():
        if v == 'None':
            form[k] = ''

    # 在表单中更新填报时间
    # 此处通过修改WID可以控制提交到列表中的哪个表项
    form['TBSJ'] = dqrq # 十分重要，用于查找最新的表单信息
    # form['TBSJ'] = "2021-02-07"
    # form['WID'] = '6497987c5cca47228bc71cfb5e8e449c'
    # print(form)
    return form

def fillForm(session, form):
    JBXX = {
           "XH": "", # 学号
           "XM": "", # 姓名
           "DWDM_DISPLAY": "", # 院系
           "DWDM": "",
           "XBDM_DISPLAY": "", #性别
           "XBDM": "",
           "LXDH": "", # 联系电话
           "GJDQ_DISPLAY": "", # 国家地区
           "GJDQ": "", #
           "SZDQ_DISPLAY": "",
           "SZDQ": "",
           "RYLB_DISPLAY": "", # 人员类别
           "RYLB": "",
           "JJLXR": "", # 紧急联系人
           "JJLXRDH": "", # 紧急联系人电话
           "JJLXRJG_DISPLAY": "", # 紧急联系人籍贯
           "JJLXRJG": "",
           "JQQK_DISPLAY": "", # 近期情况
           "JQQK": "",
           "GCKSRQ": "",
           "GCJSRQ": "",
           "SFDFHB_DISPLAY": "", # 是否到访高风险地区
           "SFDFHB": "",
           "DFHTJHBSJ": "",
           "ZDRQJCQK": "",
           "XXDZ": "", # 详细地址
           "JTXXDZ": "", # 家庭详细地址
           "JTXC": "",
           "JQQTQK": "",
           "XSBH": "" # 学生编号
    }

    MRQK = {
           "WID": "", # 查询ID
           "XSBH": "", # 学生编号
           "DZ_TBDZ": "", # 填报地址
           "TW": "",
           "BRJKZT_DISPLAY": "",
           "BRJKZT": "",
           "SFJZ_DISPLAY": "",
           "SFJZ": "",
           "JTCYJKZK_DISPLAY": "",
           "JTCYJKZK": "",
           "XLZK_DISPLAY": "",
           "XLZK": "",
           "QTQK": "",
           "TBSJ": "", # 填报时间
           "DZ_SFZX_DISPLAY": "", # 今天是否在校
           "DZ_SFZX": "",
           "DZ_TWSFZC_DISPLAY": "", # 今天体温是否正常（腋温<37.3...)
           "DZ_TWSFZC": "",
           "DZ_YWKS_DISPLAY": "", # 今天你有无咳嗽、呼吸困难、腹泻症状？
           "DZ_YWKS": "",
           "DZ_SFGR_DISPLAY": "", # 你是否曾被诊断为新冠肺炎确诊病例?
           "DZ_SFGR": "",
           "DZ_YWJCS_DISPLAY": "", # 近14天你有无与新冠肺炎确诊病例接触?
           "DZ_YWJCS": "",
           "DZ_YWJWLJS_DISPLAY": "", # 近14天你有无新冠肺炎疫情中高风险或境外旅居史？
           "DZ_YWJWLJS": "",
           "DZ_SZDQ_DISPLAY": "", # 你当前所在地区
           "DZ_SZDQ": "",
           "DZ_SFSB": "1", # 是否上报
           "BY1": "1"
    }

    # 将是否上报置为1
    # mrqk["DZ_SFSB"] = "1"
    # mrqk["BY1"] = "1"

    for k in JBXX:
        if k in form:
            # val = form[k]
            # if val == 'None':
            #     val = ''
            JBXX[k] = form[k]

    for k in MRQK:
        if k in form:
            MRQK[k] = form[k]

    info = {
        'JBXX': "%s" % JBXX,
        'MRQK': "%s" % MRQK
    }

    return {'data': '%s' % info}

def submitForm(session, payload):
    save_url = 'http://stu.hfut.edu.cn/xsfw/sys/xsyqxxsjapp/mrbpa/saveMrbpa.do'
    res = session.post(save_url, headers=headers, data=payload)
    msg = res.json()['msg']
    return msg

title_text = '今日校园疫结果通知'

# 发送邮件通知
def sendMessage(send, msg):
    if send != '':
        log('正在发送邮件通知...')
        res = requests.post(url='http://www.zimo.wiki:8080/mail-sender/sendMail',
                            data={'title': title_text, 'content': getTimeStr() + str(msg), 'to': send})

        code = res.json()['code']
        if code == 0:
            log('发送邮件通知成功...')
        else:
            log('发送邮件通知失败...')
            log(res.json())


def sendEmail(send, msg):
    my_sender = config['Info']['Email']['account']  # 发件人邮箱账号
    my_pass = config['Info']['Email']['password']  # 发件人邮箱密码
    my_user = send  # 收件人邮箱账号，我这边发送给自己
    try:
        msg = MIMEText(getTimeStr() + " " + str(msg), 'plain', 'utf-8')
        msg['From'] = formataddr(["FromHFUT", my_sender])  # 括号里的对应发件人邮箱昵称、发件人邮箱账号
        msg['To'] = formataddr(["FK", my_user])  # 括号里的对应收件人邮箱昵称、收件人邮箱账号
        msg['Subject'] = title_text  # 邮件的主题，也可以说是标题

        server = smtplib.SMTP_SSL(config['Info']['Email']['server'],
                                  config['Info']['Email']['port'])  # 发件人邮箱中的SMTP服务器，端口是25
        server.login(my_sender, my_pass)  # 括号中对应的是发件人邮箱账号、邮箱密码
        server.sendmail(my_sender, [my_user, ], msg.as_string())  # 括号中对应的是发件人邮箱账号、收件人邮箱账号、发送邮件
        server.quit()  # 关闭连接
    except Exception as e:  # 如果 try 中的语句没有执行，则会执行下面的 ret=False
        print(e)
        log("邮件发送失败")
    else:
        print("邮件发送成功")


# server酱通知
def sendServerChan(msg):
    log('正在发送Server酱...')
    res = requests.post(url='https://sc.ftqq.com/{0}.send'.format(config['Info']['ServerChan']),
                        data={'text': title_text, 'desp': getTimeStr() + "n" + str(msg)})
    code = res.json()['errmsg']
    if code == 'success':
        log('发送Server酱通知成功...')
    else:
        log('发送Server酱通知失败...')
        log('Server酱返回结果' + code)


# Qmsg酱通知
def sendQmsgChan(msg):
    log('正在发送Qmsg酱...')
    res = requests.post(url='https://qmsg.zendee.cn:443/send/{0}'.format(config['Info']['Qsmg']),
                        data={'msg': title_text + 'n时间：' + getTimeStr() + "n 返回结果：" + str(msg)})
    code = res.json()['success']
    if code:
        log('发送Qmsg酱通知成功...')
    else:
        log('发送Qmsg酱通知失败...')
        log('Qmsg酱返回结果' + code)


# 综合提交
def InfoSubmit(msg, send=None):
    if (None != send):
        if (config['Info']['Email']['enable']):
            sendEmail(send, msg)
        else:
            sendMessage(send, msg)
    if (config['Info']['ServerChan']): sendServerChan(msg)
    if (config['Info']['Qsmg']): sendQmsgChan(msg)


def main_handler(event, context):
    try:
        for user in config['users']:
            log('当前用户：' + str(user['user']['username']))
            apis = 'http://auth.hfut.edu.cn/amp-auth-adapter/login?service=http%3A%2F%2Fstu.hfut.edu.cn%2Fxsfw%2Fsys%2Femapfunauth%2FcasValidate.do%3Fservice%3Dhttp%253A%252F%252Fstu.hfut.edu.cn%252F'
            log('脚本开始执行...')
            log('开始模拟登陆...')
            session = getSession(user, apis)
            if session != None:
                log('模拟登陆成功...')
                log('正在查询最新待填写问卷...')
                form = queryForm(session, apis)
                # print(form)
                # if str(form) == 'None':
                #     # log('获取最新待填写问卷失败，可能是辅导员还没有发布...')
                #     log('获取最新表单失败，可能辅导员还未发布...')
                #     InfoSubmit('没有新问卷')
                #     exit(-1)
                log('查询最新待填写问卷成功...')
                log('正在自动填写问卷...')
                payload = fillForm(session, form)
                log('填写问卷成功...')
                log('正在自动提交...')
                msg = submitForm(session, payload=payload)
                if msg == '成功':
                    log('自动提交成功！')
                    InfoSubmit('自动提交成功！', user['user']['email'])
                else:
                    log('自动提交失败...')
                    log('错误是' + msg)
                    InfoSubmit('自动提交失败！错误是' + msg, user['user']['email'])
                    # exit(-1)
            else:
                log('模拟登陆失败...')
                log('原因可能是学号或密码错误，请检查配置后，重启脚本...')
                # exit(-1)
    except Exception as e:
        InfoSubmit("出现问题了！" + str(e))
        raise e
    else:
        return 'success'


# 配合Windows计划任务等使用
if __name__ == '__main__':
    print(main_handler({}, {}))
    # for user in config['users']:
    #     log(getCpdailyApis(user))
