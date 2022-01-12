# hfut-auto-submit
合肥工业大学疫情信息收集脚本，本校未使用今日校园通用信息采集接口，单独开发了填报页面用于疫情信息收集，因此本项目只适用于合肥工业大学。

# 项目说明
- `config.yml` 默认配置文件
- `index.py` 完成自动提交的py脚本
- `requirements.txt` py依赖库以及版本说明文件
- `save_data.json` 提交保存的POST请求数据包
# 运行环境
- `python 3.x`

# 快速开始
1. 克隆本项目，并搭建好运行环境
    ```shell script
    git clone git@github.com:A11en0/hfut-auto-submit.git
    ```
2. 安装依赖程序
  `pip install -r requirements.txt`
3. 注册用于签到提醒的邮箱（建议使用163），并开启smtp功能。[如何开启smtp？](http://mail.163.com/html/mail5faq/130520/page/5R7P6CJ600753VB8.htm)
4. 填写config.yml中users/user中的字段，并将刚刚注册好的smtp邮箱填写到`config.yml`的Info当中。当然，你也可以通过配置多个user来开启多用户自动签到模式
5. 运行python index.py，查看邮件提醒

# 基本思路
- 从`今日校园APP/我的大学/疫情信息收集`页面抓取cas认证入口
- 登录cas，获取到session，用于后续操作
- 爬取需要的表单数据(通过之前手动在APP提交过的历史数据)
- 根据日期参数提交到当日最新的表单

# 定时执行脚本
### 使用Serverless云函数
参考Zimo的README，有详细步骤。
- https://github.com/ZimoLoveShuang/auto-submit

### 使用本地服务器
- Linux下的Cron程序
  `> crontab -e`
  
  编辑以下内容到文件尾:
  > 05 14 * * * python /MY_PATH/hfut-auto-summit/index.py > hfut-as.log 2>&1 &
  
- Windows定时任务程序

# 说明
- 本项目参考
  - https://github.com/ZimoLoveShuang/auto-submit
- 感谢Zimo提供的金智教务系统登录API
  - http://www.zimo.wiki:8080/wisedu-unified-login-api-v1.0/swagger-ui.html#/api-controller

*发现Bug请提交issue，我会在第一时间解决问题，感谢！*

